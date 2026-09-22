import tempfile
import unittest
from pathlib import Path

from git_safety.common import SafetyError
from git_safety.policy import validate_policy


class PolicyTests(unittest.TestCase):
    def make_root(self):
        temporary = tempfile.TemporaryDirectory(prefix="policy-test-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        directory = root / ".git-safety"
        directory.mkdir()
        (directory / "privacy-patterns").write_text("# public rules\n")
        (directory / "privacy-allowlist").write_text("# public exceptions\n")
        return root

    def test_required_public_policy_is_required(self):
        root = self.make_root()
        (root / ".git-safety/privacy-patterns").unlink()
        with self.assertRaises(SafetyError):
            validate_policy(root)

    def test_public_policy_must_not_be_symlink(self):
        root = self.make_root()
        target = root / "policy-target"
        target.write_text("rule\n")
        path = root / ".git-safety/privacy-patterns"
        path.unlink()
        path.symlink_to(target)
        with self.assertRaises(SafetyError):
            validate_policy(root)

    def test_policy_directory_must_not_be_symlink(self):
        root = self.make_root()
        real_directory = root / "real-policy"
        (root / ".git-safety").rename(real_directory)
        (root / ".git-safety").symlink_to(real_directory, target_is_directory=True)
        with self.assertRaises(SafetyError):
            validate_policy(root)

    def test_empty_public_policy_is_valid_with_builtin_rules(self):
        validate_policy(self.make_root())


if __name__ == "__main__":
    unittest.main()
