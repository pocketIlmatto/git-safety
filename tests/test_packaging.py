"""Homebrew wrapper and formula rendering, exercised without Homebrew itself."""

import importlib.util
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

from git_safety import setup

SOURCE = Path(__file__).resolve().parents[1]
TEMPLATES = SOURCE / "packaging" / "homebrew"
spec = importlib.util.spec_from_file_location("render_formula", SOURCE / "scripts" / "render-formula.py")
render_formula = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render_formula)
URL = "https://example.com/r/v1.2.3/git-safety-1.2.3.tar.gz"
DIGEST = "ab" * 32
TOKEN = "ghp_" + "aB3dE6gH9jK2mN5pQ8sT1vW4yZ7cF0iL3oR6"


def link_tools(directory, **overrides):
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("git", "rg", "gitleaks"):
        target = overrides.get(name) or shutil.which(name)
        (directory / name).symlink_to(target)


def fake_gitleaks(path, version):
    path.write_text(f"#!/bin/sh\n[ \"$1\" = version ] && echo {version}\nexit 0\n")
    path.chmod(0o755)
    return path


class FormulaTests(unittest.TestCase):
    def test_render_with_and_without_license(self):
        text = render_formula.render("1.2.3", URL, DIGEST, "MIT")
        self.assertIn(f'url "{URL}"', text)
        self.assertIn(f'sha256 "{DIGEST}"', text)
        self.assertIn('  license "MIT"\n', text)
        self.assertNotIn("license", render_formula.render("1.2.3", URL, DIGEST))
        self.assertNotIn("\n\n\n", text)

    def test_render_rejects_bad_inputs(self):
        for kwargs in (dict(version="1.2"), dict(url="http://example.com/git-safety-1.2.3.tar.gz"),
                       dict(url=URL.replace("1.2.3.tar", "9.9.9.tar")), dict(sha256="AB" * 32),
                       dict(sha256="ab"), dict(license_id='MIT"; system "x')):
            args = dict(version="1.2.3", url=URL, sha256=DIGEST, license_id=None)
            args.update(kwargs)
            with self.assertRaises(ValueError, msg=kwargs):
                render_formula.render(**args)

    def test_local_archive_mode_is_explicit(self):
        local = "file:///tmp/dist/git-safety-1.2.3.tar.gz"
        self.assertIn(f'url "{local}"', render_formula.render("1.2.3", local, DIGEST, local_archive=True))
        with self.assertRaises(ValueError):
            render_formula.render("1.2.3", local, DIGEST)
        with self.assertRaises(ValueError):
            render_formula.render("1.2.3", URL, DIGEST, local_archive=True)

    def test_template_declares_dependencies_without_hardcoded_prefixes_or_secrets(self):
        formula = (TEMPLATES / "git-safety.rb.in").read_text()
        wrapper = (TEMPLATES / "git-safety.sh.in").read_text()
        for name in ("git", "gitleaks", "python@3.14", "ripgrep"):
            self.assertIn(f'depends_on "{name}"', formula)
        for text in (formula, wrapper):
            self.assertNotIn("/opt/homebrew", text)
            self.assertNotIn("/usr/local", text)
        self.assertNotIn("scripts/install", formula)
        self.assertNotIn(TOKEN, formula)
        self.assertIn('"$@"', wrapper)

    def test_stage_tap_contents(self):
        with tempfile.TemporaryDirectory() as out:
            result = subprocess.run([sys.executable, "-B", str(SOURCE / "scripts" / "render-formula.py"),
                                     "--version", "1.2.3", "--url", URL, "--sha256", DIGEST,
                                     "--output-dir", out], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(b"no license", result.stderr)
            self.assertTrue((Path(out) / "Formula" / "git-safety.rb").is_file())
            self.assertTrue((Path(out) / "README.md").is_file())


class WrapperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="git-safety wrapper-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.prefix = self.base / "cellar dir"
        self.bin = self.prefix / "bin"
        self.deps = self.base / "deps opt"
        link_tools(self.deps)
        self.install()
        self.repo = self.base / "scanned repo"
        (self.repo / "nested").mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        for key, value in (("user.name", "T"), ("user.email", "t@example.com"), ("core.hooksPath", "/dev/null")):
            subprocess.run(["git", "config", key, value], cwd=self.repo, check=True)
        setup.init(self.repo)
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)

    def install(self, deps=None):
        """Mirror the formula: copy the package to libexec and fill the wrapper tokens."""
        libexec = self.prefix / "libexec"
        shutil.rmtree(libexec, ignore_errors=True)
        shutil.copytree(SOURCE / "git_safety", libexec / "git_safety",
                        ignore=shutil.ignore_patterns("__pycache__"))
        self.bin.mkdir(parents=True, exist_ok=True)
        text = (TEMPLATES / "git-safety.sh.in").read_text()
        text = text.replace("@DEPENDENCY_PATH@", shlex.quote(str(deps or self.deps)))
        text = text.replace("@PYTHON@", shlex.quote(sys.executable))
        text = text.replace("@LIBEXEC@", shlex.quote(str(libexec)))
        wrapper = self.bin / "git-safety"
        wrapper.unlink(missing_ok=True)
        wrapper.write_text(text)
        wrapper.chmod(0o555)

    def run_cli(self, *args, cwd=None, path=None, expected=0):
        env = {} if path is None else {"PATH": path}
        result = subprocess.run([str(self.bin / "git-safety"), *args], cwd=cwd or self.repo, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def test_runs_from_nested_directory_with_empty_environment(self):
        output = self.run_cli("staged", cwd=self.repo / "nested")
        self.assertIn(b"Requested security checks passed", output)
        self.assertIn(b"git-safety", self.run_cli("--version", path=""))

    def test_dependencies_beat_stale_copies_on_caller_path(self):
        stale = self.base / "stale"
        stale.mkdir()
        fake_gitleaks(stale / "gitleaks", "7.0.0")
        self.assertIn(b"passed", self.run_cli("staged", path=str(stale)))

    def test_unsupported_dependency_fails_without_fallback(self):
        deps = self.base / "new deps"
        link_tools(deps, gitleaks=fake_gitleaks(self.base / "future", "9.0.0"))
        self.install(deps)
        output = self.run_cli("staged", path=str(self.deps), expected=2)
        self.assertIn(b"unsupported Gitleaks version", output)
        self.assertNotIn(b"Requested security checks passed", output)

    def test_findings_exit_code_and_redaction_survive_the_wrapper(self):
        (self.repo / "credential.txt").write_text(TOKEN)
        subprocess.run(["git", "add", "credential.txt"], cwd=self.repo, check=True)
        output = self.run_cli("staged", expected=1)
        self.assertIn(b"staged secrets: findings", output)
        self.assertNotIn(TOKEN.encode(), output)

    def test_project_code_is_never_imported_from_scanned_directory(self):
        (self.repo / "secrets.py").write_text("raise SystemExit(99)\n")
        (self.repo / "git_safety").mkdir()
        (self.repo / "git_safety" / "__init__.py").write_text("raise SystemExit(98)\n")
        self.assertIn(b"git-safety", self.run_cli("--version"))

    def test_no_bytecode_is_written_into_the_installation(self):
        self.run_cli("--version")
        self.assertEqual(list((self.prefix / "libexec").rglob("*.pyc")), [])

    def test_existing_hook_survives_upgrade_and_fails_clearly_after_removal(self):
        hook_env = {"PATH": str(self.bin) + os.pathsep + "/usr/bin:/bin"}
        subprocess.run(["git", "config", "--unset", "core.hooksPath"], cwd=self.repo, check=True)
        self.run_cli("install-hook")
        hook = self.repo / ".git" / "hooks" / "pre-commit"
        policy = (self.repo / ".git-safety" / "privacy-patterns").read_bytes()
        config = (self.repo / ".git" / "config").read_bytes()

        def run_hook():
            return subprocess.run([str(hook)], cwd=self.repo, env=hook_env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        self.assertEqual(run_hook().returncode, 0)
        self.install()  # upgrade replaces libexec and the wrapper in place
        self.assertEqual(run_hook().returncode, 0)
        (self.bin / "git-safety").unlink()
        removed = run_hook()
        self.assertEqual(removed.returncode, 2)
        self.assertIn(b"command not found", removed.stderr)
        self.assertTrue(hook.exists())
        self.assertEqual((self.repo / ".git-safety" / "privacy-patterns").read_bytes(), policy)
        self.assertEqual((self.repo / ".git" / "config").read_bytes(), config)


if __name__ == "__main__":
    unittest.main()
