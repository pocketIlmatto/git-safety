"""Real Gitleaks integration and separately identified subprocess-failure tests."""

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from git_safety import secrets
from git_safety.common import SafetyError

TOKEN = b"ghp_" + b"aB3dE6gH9jK2mN5pQ8sT1vW4yZ7cF0iL3oR6"


@unittest.skipUnless(shutil.which("gitleaks"), "real Gitleaks binary is required")
class RealGitleaksTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="git-safety-real-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Scanner Test")
        self.git("config", "user.email", "scanner@example.com")
        self.git("config", "core.hooksPath", "/dev/null")
        self.env = patch.dict(os.environ)
        self.env.start()
        self.addCleanup(self.env.stop)
        os.environ.pop("GITLEAKS_CONFIG", None)
        os.environ.pop("GITLEAKS_CONFIG_TOML", None)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    def write(self, content, name="fixture.txt", stage=True):
        path = self.root / name
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_bytes(content)
        if stage:
            self.git("add", "--", name)

    def scan(self, mode, expected):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = secrets.scan(self.root, mode)
        self.assertEqual(status, expected, output.getvalue())
        self.assertNotIn(TOKEN.decode(), output.getvalue())
        return output.getvalue()

    def test_supported_real_binary(self):
        secrets.check_dependency()

    def test_unborn_empty_repository(self):
        for mode in ("staged", "worktree", "history"):
            self.scan(mode, 0)

    def test_index_isolation_in_both_directions(self):
        self.write(b"token=" + TOKEN + b"\n")
        self.write(b"clean\n", stage=False)
        self.scan("staged", 1)
        self.scan("worktree", 0)
        self.git("add", "fixture.txt")
        self.write(TOKEN, stage=False)
        self.scan("staged", 0)
        self.scan("worktree", 1)

    def test_removed_and_noncurrent_ref_history(self):
        self.write(b"clean\n")
        self.git("commit", "-qm", "Initial")
        start = self.git("rev-parse", "HEAD").decode().strip()
        self.git("checkout", "-qb", "other")
        self.write(TOKEN)
        self.git("commit", "-qm", "Synthetic fixture")
        self.git("rm", "-q", "fixture.txt")
        self.git("commit", "-qm", "Remove fixture")
        self.git("checkout", "-q", "--detach", start)
        self.scan("worktree", 0)
        self.scan("history", 1)

    def test_deleting_secret_is_permitted_in_staged(self):
        self.write(TOKEN + b"\nclean\n")
        self.git("commit", "-qm", "Synthetic fixture")
        self.write(b"clean\n")
        self.scan("staged", 0)
        self.scan("history", 1)

    def test_tracked_ignored_and_eligible_untracked(self):
        self.write(b"clean\n", "tracked.txt")
        self.git("commit", "-qm", "Initial")
        self.write(b"tracked.txt\nignored.txt\n", ".gitignore")
        self.write(TOKEN, "ignored.txt", stage=False)
        self.scan("worktree", 0)
        self.write(TOKEN, "tracked.txt", stage=False)
        self.scan("worktree", 1)
        self.write(b"clean\n", "tracked.txt", stage=False)
        self.write(TOKEN, "untracked.txt", stage=False)
        self.scan("worktree", 1)

    def test_symlink_destination_is_not_read_but_target_string_is(self):
        self.write(b"ignored.txt\n", ".gitignore")
        self.write(TOKEN, "ignored.txt", stage=False)
        (self.root / "link").symlink_to("ignored.txt")
        self.git("add", "link")
        self.scan("worktree", 0)
        (self.root / "link").unlink()
        (self.root / "link").symlink_to(TOKEN.decode())
        self.scan("worktree", 1)

    def test_policy_files_are_not_secret_exempt(self):
        self.write(TOKEN, ".git-safety/privacy-patterns")
        self.scan("staged", 1)
        self.scan("worktree", 1)
        self.git("commit", "-qm", "Synthetic policy fixture")
        self.scan("history", 1)

    def test_repository_gitleaks_config_is_preserved_for_all_modes(self):
        config = (b"[[rules]]\nid='synthetic'\ndescription='synthetic'\n"
                  b"regex='''custom[[:digit:]]{8}'''\n")
        self.write(config, ".gitleaks.toml")
        self.write(b"custom" + b"12345678")
        self.scan("staged", 1)
        self.scan("worktree", 1)
        self.git("commit", "-qm", "Custom configuration fixture")
        self.scan("history", 1)

    def test_config_environment_precedence(self):
        self.write(b"invalid toml [", ".gitleaks.toml")
        os.environ["GITLEAKS_CONFIG_TOML"] = (
            "[[rules]]\nid='synthetic'\nregex='''custom[[:digit:]]{8}'''\n")
        self.write(b"custom" + b"12345678")
        self.scan("staged", 1)
        self.scan("worktree", 1)

    def test_invalid_config_is_error_even_with_no_history(self):
        self.write(b"[malformed", ".gitleaks.toml", stage=False)
        for mode in ("staged", "worktree", "history"):
            with self.subTest(mode=mode), self.assertRaises(SafetyError):
                secrets.scan(self.root, mode)

    def test_unusual_worktree_names_have_escaped_reports(self):
        name = 'dir/tab\tline\n"[glob]é.txt'
        self.write(TOKEN, name)
        output = self.scan("worktree", 1)
        self.assertIn("\\n", output)
        self.assertNotIn(name, output)

    def test_history_forces_text_despite_diff_attributes(self):
        self.write(b"*.txt -diff\n", ".gitattributes")
        self.write(b"\x00\xff" + TOKEN)
        self.git("commit", "-qm", "Binary synthetic fixture")
        self.scan("history", 1)

    def test_symlinked_parent_fails_closed(self):
        self.write(b"clean", "directory/file.txt")
        shutil.rmtree(self.root / "directory")
        (self.root / "directory").symlink_to(self.root)
        with self.assertRaises(SafetyError):
            secrets.scan(self.root, "worktree")

    def test_scratch_stays_outside_local_tmpdir(self):
        inside = self.root / "scratch"
        inside.mkdir()
        with patch("tempfile.tempdir", str(inside)):
            self.scan("worktree", 0)
        self.assertEqual(list(inside.iterdir()), [])


class MockedGitleaksFailures(unittest.TestCase):
    def test_subprocess_error_is_not_a_finding_and_does_not_leak(self):
        result = subprocess.CompletedProcess([], 1, TOKEN, TOKEN)
        with patch.object(secrets, "run", return_value=result):
            with self.assertRaises(SafetyError) as error:
                secrets._invoke(Path.cwd(), ["stdin"], data=b"")
        self.assertNotIn(TOKEN.decode(), str(error.exception))

    def test_malformed_report_fails_closed(self):
        for output, status in ((TOKEN, 0), (b"{}", 0), (b"[]", 42), (b'[{}]', 0)):
            result = subprocess.CompletedProcess([], status, output, b"")
            with self.subTest(output=output), patch.object(secrets, "run", return_value=result):
                with self.assertRaises(SafetyError):
                    secrets._invoke(Path.cwd(), ["stdin"], data=b"")

    def test_custom_rule_metadata_and_source_are_not_printed(self):
        report = [{"File": "safe.txt", "StartLine": 1, "Commit": "",
                   "RuleID": TOKEN.decode(), "Match": TOKEN.decode(), "Secret": TOKEN.decode()}]
        result = subprocess.CompletedProcess([], 42, json.dumps(report).encode(), b"")
        output = io.StringIO()
        with patch.object(secrets, "run", return_value=result), contextlib.redirect_stdout(output):
            self.assertEqual(secrets._invoke(Path.cwd(), ["stdin"], data=b""), 1)
        self.assertNotIn(TOKEN.decode(), output.getvalue())


if __name__ == "__main__":
    unittest.main()
