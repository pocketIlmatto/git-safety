from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

from git_safety import setup
from git_safety.common import SafetyError


class SetupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "Test"], check=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_init_is_idempotent_and_preserves_existing_policy(self) -> None:
        (self.root / ".git-safety").mkdir()
        policy = self.root / ".git-safety" / "privacy-patterns"
        policy.write_text("custom-rule\n")
        setup.init(self.root)
        first_ignore = (self.root / ".gitignore").read_bytes()
        setup.init(self.root)
        self.assertEqual(policy.read_text(), "custom-rule\n")
        self.assertEqual((self.root / ".gitignore").read_bytes(), first_ignore)
        self.assertIn(b".git-safety/privacy-patterns.local\n", first_ignore)
        self.assertIn(b".git-safety/privacy-allowlist.local\n", first_ignore)

    def test_init_refuses_symlinked_ignore(self) -> None:
        target = self.root / "target"
        target.write_text("")
        (self.root / ".gitignore").symlink_to(target)
        with self.assertRaises(SafetyError):
            setup.init(self.root)

    def test_hook_conflict_idempotence_and_uninstall_preserves_user_hook(self) -> None:
        setup.install_hook(self.root)
        hook = Path(subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "--git-path", "hooks"], text=True).strip())
        if not hook.is_absolute():
            hook = self.root / hook
        hook = hook / "pre-commit"
        owned = hook.read_bytes()
        setup.install_hook(self.root)
        self.assertEqual(hook.read_bytes(), owned)
        setup.uninstall_hook(self.root)
        self.assertFalse(hook.exists())
        hook.write_text("#!/bin/sh\nexit 0\n")
        with self.assertRaises(SafetyError):
            setup.install_hook(self.root)
        with self.assertRaises(SafetyError):
            setup.uninstall_hook(self.root)
        self.assertIn("exit 0", hook.read_text())

    def test_configured_external_hooks_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as external_name:
            external = Path(external_name)
            subprocess.run(["git", "-C", str(self.root), "config", "core.hooksPath", str(external)], check=True)
            with self.assertRaises(SafetyError):
                setup.install_hook(self.root)

    def test_repository_owned_configured_hooks_are_supported(self) -> None:
        hooks = self.root / ".githooks"
        hooks.mkdir()
        subprocess.run(["git", "-C", str(self.root), "config", "core.hooksPath", ".githooks"], check=True)
        setup.install_hook(self.root)
        self.assertEqual((hooks / "pre-commit").read_bytes(), setup.OWNED_HOOK)
        setup.uninstall_hook(self.root)
        self.assertFalse((hooks / "pre-commit").exists())

    def test_nested_repository_owned_hooks_path_is_created(self) -> None:
        hooks = self.root / ".tools" / "git" / "hooks"
        subprocess.run(
            ["git", "-C", str(self.root), "config", "core.hooksPath", ".tools/git/hooks"],
            check=True,
        )
        setup.install_hook(self.root)
        self.assertEqual((hooks / "pre-commit").read_bytes(), setup.OWNED_HOOK)

    def test_symlinked_configured_hook_directory_is_refused(self) -> None:
        target = self.root / "real-hooks"
        target.mkdir()
        (self.root / ".githooks").symlink_to(target, target_is_directory=True)
        subprocess.run(["git", "-C", str(self.root), "config", "core.hooksPath", ".githooks"], check=True)
        with self.assertRaises(SafetyError):
            setup.install_hook(self.root)

    def test_doctor_flags_tracked_local_policy_without_reading_it(self) -> None:
        setup.init(self.root)
        local = self.root / ".git-safety" / "privacy-patterns.local"
        local.write_text("private-value\n")
        subprocess.run(["git", "-C", str(self.root), "add", "-f", "--", ".git-safety/privacy-patterns.local"], check=True)
        self.assertEqual(setup.doctor(self.root), 2)

    def test_init_rejects_a_nested_ignore_negation(self) -> None:
        policy_dir = self.root / ".git-safety"
        policy_dir.mkdir()
        (policy_dir / ".gitignore").write_text(
            "!privacy-patterns.local\n!privacy-allowlist.local\n"
        )
        with self.assertRaises(SafetyError):
            setup.init(self.root)

    def test_owned_nonexecutable_hook_is_flagged_then_repaired(self) -> None:
        setup.install_hook(self.root)
        hook_dir = Path(subprocess.check_output(
            ["git", "-C", str(self.root), "rev-parse", "--git-path", "hooks"], text=True
        ).strip())
        hook = (hook_dir if hook_dir.is_absolute() else self.root / hook_dir) / "pre-commit"
        hook.chmod(0o644)
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(setup.doctor(self.root), 2)
        self.assertIn("not executable", stderr.getvalue())
        setup.install_hook(self.root)
        self.assertTrue(hook.stat().st_mode & 0o111)

    def test_git_output_removes_one_terminator_only(self) -> None:
        self.assertEqual(setup._decode_git_output(b"one\n\n"), "one\n")

    def test_linked_worktree_initializes_its_own_policy_directory(self) -> None:
        (self.root / "README").write_text("base\n")
        subprocess.run(["git", "-C", str(self.root), "add", "README"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "base"], check=True)
        with tempfile.TemporaryDirectory() as checkout_name:
            checkout = Path(checkout_name) / "linked"
            subprocess.run(
                ["git", "-C", str(self.root), "worktree", "add", "-q", "-b", "linked", str(checkout)],
                check=True,
            )
            setup.init(checkout)
            self.assertTrue((checkout / ".git-safety" / "privacy-patterns").is_file())
            self.assertFalse((self.root / ".git-safety").exists())
            setup.install_hook(checkout)
            stdout, stderr = StringIO(), StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                self.assertEqual(setup.doctor(checkout), 2)  # CLI intentionally absent in test env.
            self.assertIn("shared across linked worktrees", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
