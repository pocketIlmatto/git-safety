"""Release archive determinism, inventory and standalone execution."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_release", SOURCE / "scripts" / "build-release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="git-safety-release-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "source repo"
        (self.repo / "git_safety").mkdir(parents=True)
        (self.repo / "git_safety" / "__init__.py").write_text('__version__ = "1.2.3"\n')
        (self.repo / "tool").write_text("#!/bin/sh\n")
        (self.repo / "tool").chmod(0o755)
        (self.repo / "LICENSE").write_text("terms\n")
        (self.repo / ".gitignore").write_text("ignored\n*.local\n")
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=T", "-c", "user.email=t@example.com", "commit", "-qm", "one")
        (self.repo / "ignored").write_text("private\n")
        (self.repo / "privacy.local").write_text("private\n")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              stdout=subprocess.PIPE).stdout

    def build(self, out="out", **kwargs):
        return release.build(self.repo, "1.2.3", "HEAD", self.base / out, **kwargs)

    def test_inventory_excludes_ignored_local_and_git_data(self):
        path, digest, commit, licenses = self.build()
        with tarfile.open(path) as archive:
            names = sorted(archive.getnames())
            modes = {m.name: m.mode for m in archive.getmembers()}
        prefix = "git-safety-1.2.3/"
        self.assertEqual(names, [prefix + n for n in (".gitignore", "LICENSE", "git_safety/__init__.py", "tool")])
        self.assertEqual(modes[prefix + "tool"], 0o755)
        self.assertEqual(licenses, ["LICENSE"])
        self.assertEqual((path.parent / (path.name + ".sha256")).read_text(), f"{digest}  {path.name}\n")
        self.assertEqual(commit, self.git("rev-parse", "HEAD").decode().strip())

    def test_repeat_build_has_identical_digest(self):
        first = self.build("a")[1]
        os.utime(self.repo / "tool", (1, 1))
        self.assertEqual(self.build("b")[1], first)

    def test_new_commit_changes_digest(self):
        first = self.build("a")[1]
        (self.repo / "tool").write_text("#!/bin/sh\necho\n")
        self.git("-c", "user.name=T", "-c", "user.email=t@example.com", "commit", "-qam", "two")
        self.assertNotEqual(self.build("b")[1], first)

    def test_refuses_version_mismatch_missing_license_and_inside_worktree(self):
        with self.assertRaisesRegex(release.ReleaseError, "package version"):
            release.build(self.repo, "1.2.4", "HEAD", self.base / "out")
        with self.assertRaisesRegex(release.ReleaseError, "outside any Git worktree"):
            release.build(self.repo, "1.2.3", "HEAD", self.repo / "dist")
        with self.assertRaisesRegex(release.ReleaseError, "version must"):
            release.build(self.repo, "v1", "HEAD", self.base / "out")
        with self.assertRaises(release.ReleaseError):
            release.build(self.repo, "1.2.3", "no-such-ref", self.base / "out")
        self.git("rm", "-q", "LICENSE")
        self.git("-c", "user.name=T", "-c", "user.email=t@example.com", "commit", "-qm", "drop")
        with self.assertRaisesRegex(release.ReleaseError, "license"):
            self.build()
        self.assertEqual(self.build(allow_missing_license=True)[3], [])

    def test_real_head_archive_runs_without_original_checkout(self):
        path, _, _, _ = release.build(SOURCE, self.current_version(), "HEAD", self.base / "real",
                                      allow_missing_license=True)
        extracted = self.base / "extracted"
        extracted.mkdir()
        with tarfile.open(path) as archive:
            archive.extractall(extracted, filter="data")
        root = next(extracted.iterdir())
        env = {"PATH": os.environ["PATH"]}
        for command in (["bin/git-safety", "--version"], [sys.executable, "-B", "git_safety/cli.py", "--version"]):
            result = subprocess.run(command, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(b"git-safety " + self.current_version().encode(), result.stdout)

    @staticmethod
    def current_version():
        sys.path.insert(0, str(SOURCE))
        from git_safety import __version__
        return __version__


if __name__ == "__main__":
    unittest.main()
