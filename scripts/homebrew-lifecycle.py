"""Prepublication Homebrew lifecycle test using local candidate archives.

Installs, upgrades, reinstalls and removes git-safety through a throwaway local tap,
then restores the first version. It replaces any installed formula of the same name,
so it refuses to run unless GIT_SAFETY_DISPOSABLE_BREW=1 confirms a disposable
Homebrew (such as a CI runner). Nothing is published.
"""

import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[1]
TAP = "local/git-safety-test"
FORMULA = TAP + "/git-safety"
TOKEN = "ghp_" + "aB3dE6gH9jK2mN5pQ8sT1vW4yZ7cF0iL3oR6"


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), SOURCE / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release, formula = load("build-release"), load("render-formula")


def run(*command, cwd=None, env=None, expected=0):
    result = subprocess.run(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode != expected:
        sys.exit(f"FAIL: {' '.join(map(str, command))} exited {result.returncode}, expected {expected}\n{result.stdout}")
    return result.stdout


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if os.environ.get("GIT_SAFETY_DISPOSABLE_BREW") != "1":
        sys.exit("Refusing: set GIT_SAFETY_DISPOSABLE_BREW=1 only on a disposable Homebrew installation.")
    if not shutil.which("brew"):
        sys.exit("Homebrew is required.")
    if subprocess.run(["brew", "list", "--formula", "git-safety"], stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL).returncode == 0:
        sys.exit("Refusing: a git-safety formula is already installed.")
    os.environ.update(HOMEBREW_NO_AUTO_UPDATE="1", HOMEBREW_NO_ANALYTICS="1", HOMEBREW_NO_INSTALL_CLEANUP="1")
    sys.path.insert(0, str(SOURCE))
    from git_safety import __version__ as first
    major, minor, patch = map(int, first.split("."))
    second = f"{major}.{minor}.{patch + 1}"
    work = Path(tempfile.mkdtemp(prefix="git-safety-lifecycle-"))
    try:
        # Candidate A is this commit; candidate B is a throwaway clone with a bumped version.
        clone = work / "second-source"
        run("git", "clone", "-q", str(SOURCE), str(clone))
        init = clone / "git_safety" / "__init__.py"
        init.write_text(init.read_text().replace(f'"{first}"', f'"{second}"'))
        run("git", "-c", "user.name=T", "-c", "user.email=t@example.com", "commit", "-qam", "bump", cwd=clone)
        builds = {}
        for version, repo in ((first, SOURCE), (second, clone)):
            path, sha, _, _ = release.build(repo, version, "HEAD", work / f"dist-{version}", allow_missing_license=True)
            builds[version] = (path, sha)

        def stage(version):
            path, sha = builds[version]
            text = formula.render(version, path.as_uri(), sha, local_archive=True)
            (tap_dir / "Formula").mkdir(parents=True, exist_ok=True)
            (tap_dir / "Formula" / "git-safety.rb").write_text(text)

        run("brew", "tap-new", "--no-git", TAP)
        tap_dir = Path(run("brew", "--repository", TAP).strip())
        prefix = Path(run("brew", "--prefix").strip())
        cli = prefix / "bin" / "git-safety"

        repo = work / "project dir"
        repo.mkdir()
        isolated = dict(os.environ, HOME=str(work), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        run("git", "init", "-q", cwd=repo, env=isolated)
        for key, value in (("user.name", "T"), ("user.email", "t@example.com")):
            run("git", "config", key, value, cwd=repo, env=isolated)

        def installed(version):
            assert f"git-safety {version}" in run(str(cli), "--version"), version
            run("brew", "test", FORMULA)
            minimal = dict(isolated, PATH="/usr/bin:/bin:" + str(prefix / "bin"))
            assert f"git-safety {version}" in run(str(cli), "--version", env=minimal)
            # A stale scanner earlier on PATH must not displace the declared dependency.
            stale = work / "stale"
            stale.mkdir(exist_ok=True)
            (stale / "gitleaks").write_text("#!/bin/sh\necho 7.0.0\n")
            (stale / "gitleaks").chmod(0o755)
            out = run(str(cli), "staged", cwd=repo, env=dict(isolated, PATH=f"{stale}:{os.environ['PATH']}"))
            assert "Requested security checks passed" in out, out

        stage(first)
        run("brew", "install", "--formula", FORMULA)
        installed(first)
        run(str(cli), "init", cwd=repo, env=isolated)
        run(str(cli), "install-hook", cwd=repo, env=isolated)
        run("git", "add", ".", cwd=repo, env=isolated)
        hook_env = dict(isolated, PATH=f"{prefix / 'bin'}:/usr/bin:/bin")
        run("git", "commit", "-qm", "clean", cwd=repo, env=hook_env)
        (repo / "credential.txt").write_text(TOKEN)
        run("git", "add", "credential.txt", cwd=repo, env=isolated)
        blocked = run("git", "commit", "-qm", "secret", cwd=repo, env=hook_env, expected=1)
        assert TOKEN not in blocked
        run("git", "rm", "-qf", "credential.txt", cwd=repo, env=isolated)
        policy = digest(repo / ".git-safety" / "privacy-patterns")
        config, hook = digest(repo / ".git" / "config"), digest(repo / ".git" / "hooks" / "pre-commit")

        def preserved():
            assert digest(repo / ".git-safety" / "privacy-patterns") == policy
            assert digest(repo / ".git" / "config") == config
            assert digest(repo / ".git" / "hooks" / "pre-commit") == hook

        run("brew", "reinstall", "--formula", FORMULA)
        installed(first)
        preserved()
        stage(second)
        run("brew", "upgrade", "--formula", FORMULA)
        installed(second)
        run("git", "commit", "--allow-empty", "-qm", "after upgrade", cwd=repo, env=hook_env)
        preserved()
        run("brew", "uninstall", "--formula", "git-safety")
        failed = run("git", "commit", "--allow-empty", "-qm", "no cli", cwd=repo, env=hook_env, expected=2)
        assert "command not found" in failed, failed
        preserved()
        stage(first)  # restore the previously known version
        run("brew", "install", "--formula", FORMULA)
        installed(first)
        run("git", "commit", "--allow-empty", "-qm", "restored", cwd=repo, env=hook_env)
        preserved()
        print("Homebrew lifecycle passed: install, test, reinstall, upgrade, uninstall, restore.")
    finally:
        subprocess.run(["brew", "uninstall", "--formula", "--force", "git-safety"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["brew", "untap", TAP], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
