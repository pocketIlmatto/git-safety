"""Disposable privacy scanner regressions, ported from the Hammerspoon suite."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest import mock

from git_safety import privacy


PRIVATE = b"/" + b"Users/" + b"audit-person/private"
EMAIL = b"audit.person" + b"@" + b"private.invalid"
SAFE = b"placeholder" + b"@" + b"example.com"
BEAR = b"bear://x-callback-url/open-note?id=12345678"


class PrivacyCheckTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="privacy-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        policy = self.root / ".git-safety"
        policy.mkdir()
        (policy / "privacy-patterns").write_bytes(
            b"bear://x-callback-url/open-note\\?id=[A-Za-z0-9-]{8,}\n"
        )
        (policy / "privacy-allowlist").write_bytes(
            b"^bear://x-callback-url/open-note\\?id=YOUR-BEAR-NOTE-ID$\n"
        )
        self.git("init", "-q")
        self.git("config", "user.name", "Scanner Test")
        self.git("config", "user.email", SAFE.decode())
        self.git("config", "core.hooksPath", "/dev/null")
        self.git("add", ".")
        self.git("commit", "-qm", "Initial scanner")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    def write(self, value, name="fixture.txt", stage=True):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
        if stage:
            self.git("add", "--", name)

    def scan(self, mode="staged", expected=0, env=None):
        stdout, stderr = StringIO(), StringIO()
        old = os.environ.copy()
        if env:
            os.environ.update(env)
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = privacy.scan(self.root, mode)
        finally:
            os.environ.clear()
            os.environ.update(old)
        output = (stdout.getvalue() + stderr.getvalue()).encode()
        self.assertEqual(result, expected, output)
        self.assertNotIn(PRIVATE, output)
        self.assertNotIn(EMAIL, output)
        return output

    def test_safe_placeholders(self):
        self.write(SAFE + b" /" + b"Users/username/ "
                   b"bear://x-callback-url/open-note?id=YOUR-BEAR-NOTE-ID\n")
        self.scan()
        self.scan("all")

    def test_safe_finding_does_not_allow_other_findings(self):
        self.write(SAFE + b" " + PRIVATE + b" " + EMAIL + b"\n")
        for mode in ("staged", "worktree", "all"):
            self.scan(mode, 1)

    def test_placeholder_domain_suffix_is_not_safe(self):
        self.write(SAFE + b".private.invalid\n")
        self.scan(expected=1)

    def test_multiple_findings_same_rule(self):
        self.write(SAFE + b" " + EMAIL)
        self.scan(expected=1)

    def test_unusual_filenames(self):
        for name in ("caf\u00e9.txt", "space name.txt", 'quote"name.txt', "tab\tname.txt",
                     "line\nname.txt", "--option.txt", "[glob].txt", "back\\slash.txt"):
            with self.subTest(name=name):
                self.write(PRIVATE, name)
                self.scan(expected=1)
                self.scan("worktree", 1)
                self.git("reset", "-q", "HEAD", "--", name)
                (self.root / name).unlink()

    def test_added_content_that_resembles_diff_headers(self):
        self.write(b"++ " + PRIVATE + b"\n")
        self.scan(expected=1)

    def test_partial_staging_only_reads_index(self):
        self.write(b"safe\n")
        self.write(PRIVATE, stage=False)
        self.scan()
        self.scan("worktree", 1)
        self.write(PRIVATE)
        self.write(b"safe\n", stage=False)
        self.scan(expected=1)
        self.scan("all", 1)

    def test_policy_is_read_from_current_worktree_in_both_partial_staging_directions(self):
        value = b"current-policy-123\n"
        rule = b"current-policy-[[:digit:]]+\n"
        public_rules = ".git-safety/privacy-patterns"
        self.write(rule, public_rules)
        self.write(b"# current policy deliberately has no custom rule\n", public_rules, stage=False)
        self.write(value)
        self.scan("staged")

        self.write(b"# index policy deliberately has no custom rule\n", public_rules)
        self.write(rule, public_rules, stage=False)
        self.write(value)
        self.scan("staged", 1)

    def test_deleting_private_line_is_permitted(self):
        self.write(PRIVATE + b"\nsafe\n")
        self.git("commit", "-qm", "Historical fixture")
        self.write(b"safe\n")
        self.scan()
        self.scan("history", 1)

    def test_removed_history_is_found(self):
        self.write(PRIVATE)
        self.git("commit", "-qm", "Historical fixture")
        self.git("rm", "-q", "fixture.txt")
        self.git("commit", "-qm", "Remove fixture")
        self.scan("worktree")
        self.scan("history", 1)
        self.scan("all", 1)

    def test_other_branch_history_is_found(self):
        initial = self.git("rev-parse", "HEAD").strip().decode()
        self.git("checkout", "-qb", "other")
        self.write(PRIVATE)
        self.git("commit", "-qm", "Branch fixture")
        self.git("checkout", "-q", "--detach", initial)
        self.scan("worktree")
        self.scan("history", 1)

    def test_history_deduplicates_identical_blobs(self):
        self.write(PRIVATE, "first.txt")
        self.git("commit", "-qm", "First copy")
        self.write(PRIVATE, "second.txt")
        self.git("commit", "-qm", "Second copy")
        output = self.scan("history", 1)
        self.assertEqual(output.count(b"private pattern matched"), 1)

    def test_ignored_files_and_untracked_files(self):
        self.write(b"ignored.txt\n", ".gitignore")
        self.write(PRIVATE, "ignored.txt", stage=False)
        self.scan("all")
        self.write(PRIVATE, "untracked.txt", stage=False)
        self.scan("staged")
        self.scan("worktree", 1)

    def test_binary_and_non_utf8_content(self):
        self.write(b"\x00\xff" + EMAIL)
        self.scan(expected=1)
        self.scan("worktree", 1)
        self.git("commit", "-qm", "Binary fixture")
        self.scan("history", 1)

    def test_symlink_does_not_follow_ignored_target(self):
        self.write(b"ignored.txt\n", ".gitignore")
        self.write(PRIVATE, "ignored.txt", stage=False)
        (self.root / "link").symlink_to("ignored.txt")
        self.git("add", "link")
        self.scan("all")

    def test_symlink_target_is_scanned(self):
        (self.root / "link").symlink_to(PRIVATE.decode())
        self.git("add", "link")
        self.scan(expected=1)
        self.scan("worktree", 1)

    def test_symlinked_parent_is_incomplete_without_reading_outside_root(self):
        self.write(b"safe\n", "nested/fixture.txt")
        self.git("commit", "-qm", "Track nested fixture")
        external = self.root.parent / "privacy-external"
        external.mkdir()
        self.addCleanup(shutil.rmtree, external)
        (external / "fixture.txt").write_bytes(PRIVATE)
        shutil.rmtree(self.root / "nested")
        (self.root / "nested").symlink_to(external, target_is_directory=True)
        self.scan("worktree", 2)

    def test_ripgrep_regex_local_rules_and_allowlist(self):
        self.write(b"private[[:digit:]]+\n", ".git-safety/privacy-patterns.local", stage=False)
        self.write(b"private123\n")
        self.scan(expected=1)
        self.write(b"^private123$\n", ".git-safety/privacy-allowlist.local", stage=False)
        self.scan()

    def test_invalid_rules_fail_even_without_staged_files(self):
        self.write(b"[\n", ".git-safety/privacy-patterns.local", stage=False)
        self.scan(expected=2)

    def test_invalid_allowlist_fails_even_without_matches(self):
        self.write(b"[\n", ".git-safety/privacy-allowlist.local", stage=False)
        self.scan(expected=2)

    def test_unreadable_required_policy_fails_closed(self):
        with mock.patch("git_safety.policy.os.open", side_effect=PermissionError):
            self.scan(expected=2)

    def test_unreadable_optional_policy_fails_closed(self):
        local = self.root / ".git-safety/privacy-patterns.local"
        local.write_text("custom-rule\n")
        original_open = os.open

        def deny_local(path, flags, *args):
            if Path(path) == local:
                raise PermissionError
            return original_open(path, flags, *args)

        with mock.patch("git_safety.policy.os.open", side_effect=deny_local):
            self.scan(expected=2)

    def test_subprocess_failure_payload_is_redacted(self):
        with mock.patch("git_safety.privacy.common_run",
                        side_effect=privacy.SafetyError(PRIVATE.decode())):
            self.scan(expected=2)

    def test_missing_ripgrep_is_actionable_error_two(self):
        with mock.patch("git_safety.privacy.shutil.which", return_value=None):
            output = self.scan(expected=2)
        self.assertIn(b"requires ripgrep", output)

    def test_rg_environment_config_cannot_disable_scanning(self):
        config = self.root / "rg-config"
        config.write_text("--invert-match\n")
        self.write(PRIVATE)
        self.scan(expected=1, env={"RIPGREP_CONFIG_PATH": str(config)})

    @unittest.skipIf(sys.platform == "darwin", "macOS rejects non-UTF-8 filenames")
    def test_non_utf8_filename(self):
        name = b"nonutf8-\xff.txt"
        full_path = os.fsencode(self.root) + b"/" + name
        with open(full_path, "wb") as file:
            file.write(PRIVATE)
        self.git("add", "--", os.fsdecode(name))
        self.scan(expected=1)
        self.scan("worktree", 1)

    def test_diff_attributes_cannot_hide_content(self):
        self.write(b"*.txt -diff\n", ".gitattributes")
        self.write(PRIVATE)
        self.scan(expected=1)

    def test_unmerged_index_is_incomplete(self):
        blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=self.root,
                              input=b"safe\n", stdout=subprocess.PIPE, check=True).stdout.strip()
        entries = b"100644 " + blob + b" 2\tconflict.txt\n" + b"100644 " + blob + b" 3\tconflict.txt\n"
        subprocess.run(["git", "update-index", "--index-info"], cwd=self.root,
                       input=entries, check=True)
        self.scan("staged", 2)

    def test_shallow_history_is_incomplete(self):
        git_dir = Path(self.git("rev-parse", "--git-dir").strip().decode())
        if not git_dir.is_absolute():
            git_dir = self.root / git_dir
        (git_dir / "shallow").write_bytes(self.git("rev-parse", "HEAD").strip() + b"\n")
        self.scan("history", 2)

    def test_scanner_setup_cleans_temporary_files_after_validation_failure(self):
        temporary = tempfile.TemporaryDirectory(prefix="privacy-cleanup-")
        self.addCleanup(temporary.cleanup)

        class TrackingDirectory:
            name = temporary.name
            cleaned = False

            def cleanup(self):
                self.cleaned = True
                temporary.cleanup()

        tracking = TrackingDirectory()
        with mock.patch("git_safety.privacy.temporary_directory", return_value=tracking), \
             mock.patch("git_safety.privacy._rg", side_effect=privacy.ScanFailure("invalid rules")):
            with self.assertRaises(privacy.ScanFailure):
                privacy._Scanner(self.root, b"rule\n", b"")
        self.assertTrue(tracking.cleaned)

    def test_tracked_ignored_file_remains_eligible(self):
        self.write(PRIVATE, "tracked.txt")
        self.git("commit", "-qm", "Track fixture")
        self.write(b"tracked.txt\n", ".gitignore", stage=False)
        self.scan("worktree", 1)

    def test_policy_file_exemption_is_exact(self):
        self.write(PRIVATE, ".git-safety/privacy-patterns.local", stage=False)
        self.scan("worktree")
        self.write(PRIVATE, ".git-safety/other.txt", stage=False)
        self.scan("worktree", 1)


if __name__ == "__main__":
    unittest.main()
