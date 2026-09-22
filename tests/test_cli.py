"""End-to-end CLI/lifecycle checks and coverage aggregation regressions."""

import contextlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from git_safety import cli, setup
from git_safety.common import SafetyError

SOURCE = Path(__file__).resolve().parents[1]
CLI = SOURCE / "bin" / "git-safety"


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="git-safety-cli-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "repository"
        self.root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Scanner Test")
        self.git("config", "user.email", "scanner@example.com")
        self.git("config", "core.hooksPath", "/dev/null")
        setup.init(self.root)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    def command(self, *args, cwd=None, expected=0, env=None):
        result = subprocess.run([str(CLI), *args], cwd=cwd or self.root,
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def test_default_comprehensive_unborn_and_nested(self):
        nested = self.root / "nested"
        nested.mkdir()
        output = self.command(cwd=nested)
        for mode in (b"staged", b"worktree", b"history"):
            for engine in (b"privacy", b"secrets"):
                self.assertIn(mode + b" " + engine + b": clean", output)

    def test_all_includes_staged_secrets_hidden_by_clean_worktree(self):
        token = b"ghp_" + b"aB3dE6gH9jK2mN5pQ8sT1vW4yZ7cF0iL3oR6"
        path = self.root / "fixture.txt"
        path.write_bytes(token)
        self.git("add", "fixture.txt")
        path.write_text("clean\n")
        output = self.command("all", expected=1)
        self.assertIn(b"staged secrets: findings", output)
        self.assertIn(b"worktree secrets: clean", output)
        self.assertNotIn(token, output)

    def test_shallow_all_runs_other_modes_but_fails_history(self):
        self.git("add", ".")
        self.git("commit", "-qm", "Initial")
        (self.root / "fixture").write_text("clean\n")
        self.git("add", ".")
        self.git("commit", "-qm", "Second")
        clone = self.base / "shallow"
        self.git("clone", "--depth=1", self.root.as_uri(), str(clone))
        output = self.command("all", cwd=clone, expected=2)
        self.assertIn(b"shallow history", output)
        self.assertIn(b"worktree secrets: clean", output)
        self.assertNotIn(b"Requested security checks passed", output)

    def test_missing_public_policy_still_runs_secrets(self):
        (self.root / ".git-safety" / "privacy-patterns").unlink()
        output = self.command("staged", expected=2)
        self.assertIn(b"privacy coverage did not run", output)
        self.assertIn(b"staged secrets: clean", output)

    def test_partial_clone_configuration_fails_without_fetch(self):
        self.git("config", "remote.origin.promisor", "true")
        output = self.command("all", expected=2)
        self.assertIn(b"partial/promisor", output)

    def test_linked_worktree_scan(self):
        self.git("add", ".")
        self.git("commit", "-qm", "Initial")
        linked = self.base / "linked"
        self.git("worktree", "add", "-qb", "linked", str(linked))
        self.command("all", cwd=linked)

    def test_doctor_validates_regexes_without_echoing_policy(self):
        (self.root / ".git-safety" / "privacy-patterns").write_text("sensitive-marker[\n")
        self.git("config", "--unset", "core.hooksPath")
        env = dict(os.environ, PATH=str(SOURCE / "bin") + os.pathsep + os.environ["PATH"])
        output = self.command("doctor", expected=2, env=env)
        self.assertNotIn(b"sensitive-marker", output)

    def test_install_upgrade_collision_uninstall_and_symlink_invocation(self):
        bindir = self.base / "bin with spaces"
        def install(action, expected=0):
            result = subprocess.run([str(SOURCE / "scripts" / action), "--bin-dir", str(bindir)],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        install("install")
        install("install")
        result = subprocess.run([str(bindir / "git-safety"), "--version"], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"0.1.0", result.stdout)
        install("uninstall")
        install("uninstall")
        (bindir / "git-safety").write_text("user-owned\n")
        install("install", 2)
        install("uninstall", 2)
        self.assertEqual((bindir / "git-safety").read_text(), "user-owned\n")

    def test_non_repository_is_error_two(self):
        self.command("all", cwd=self.base, expected=2)


class AggregationTests(unittest.TestCase):
    def test_error_overrides_findings_and_other_coverage_continues(self):
        with patch.object(cli, "dependencies"), patch.object(cli.policy, "validate_policy"), \
                patch.object(cli, "history_complete"), \
                patch.object(cli.privacy, "scan", side_effect=[1, 0, 0]) as privacy, \
                patch.object(cli.secrets, "scan", side_effect=[SafetyError("synthetic failure"), 0, 1]) as secrets, \
                contextlib.redirect_stdout(io.StringIO()) as output, \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.scan(Path.cwd(), "all"), 2)
        self.assertEqual(privacy.call_count, 3)
        self.assertEqual(secrets.call_count, 3)
        self.assertNotIn("Requested security checks passed", output.getvalue())

    def test_missing_dependency_does_not_suppress_independent_engine(self):
        with patch.object(cli, "dependencies", side_effect=[SafetyError("rg missing"), None]), \
                patch.object(cli.secrets, "scan", return_value=0) as secrets, \
                patch.object(cli.privacy, "scan") as privacy, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli.scan(Path.cwd(), "staged"), 2)
        secrets.assert_called_once()
        privacy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
