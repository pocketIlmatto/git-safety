"""Gitleaks adapter: explicit scope, isolated snapshots, and sanitized output."""

import json
import os
from pathlib import Path
import re
import shutil
import stat

from .common import SafetyError, git, run, temporary_directory

SUPPORTED_VERSION = "8.30.1"
FINDINGS_EXIT = 42
HISTORY_OPTIONS = "--all --full-history --root --no-renames --no-ext-diff --no-textconv --text -m"


def check_dependency():
    if not shutil.which("gitleaks"):
        raise SafetyError("Gitleaks is missing; install Gitleaks 8.30.1 (see README)")
    version = run(["gitleaks", "version"]).stdout.strip()
    if version != SUPPORTED_VERSION.encode():
        raise SafetyError("unsupported Gitleaks version; use validated Gitleaks 8.30.1")
    for command, flag in (("git", b"--staged"), ("git", b"--log-opts"),
                          ("dir", b"--redact"), ("stdin", b"--exit-code")):
        if flag not in run(["gitleaks", command, "--help"]).stdout:
            raise SafetyError("Gitleaks lacks required commands; install Gitleaks 8.30.1")


def config_args(root):
    # Retain native environment precedence; explicitly select repository config
    # when scanning a temporary directory rather than relying on source discovery.
    if os.environ.get("GITLEAKS_CONFIG") or os.environ.get("GITLEAKS_CONFIG_TOML"):
        return []
    path = root / ".gitleaks.toml"
    if path.is_symlink():
        raise SafetyError("repository Gitleaks configuration must not be a symlink")
    if path.exists():
        if not path.is_file():
            raise SafetyError("repository Gitleaks configuration must be a readable file")
        return ["--config", str(path)]
    return []


def _invoke(root, command, *, data=None, snapshot=None, quiet=False):
    args = ["gitleaks", *command, "--redact=100", "--no-banner", "--no-color",
            "--log-level=error", "--exit-code", str(FINDINGS_EXIT),
            "--report-format=json", "--report-path=-",
            "--gitleaks-ignore-path", str(root), *config_args(root)]
    result = run(args, cwd=root, data=data, accepted=(0, FINDINGS_EXIT, 1, 2, 126))
    if result.returncode not in (0, FINDINGS_EXIT):
        raise SafetyError("Gitleaks failed; coverage incomplete (diagnostics suppressed); "
                          "check Gitleaks configuration and repository readability")
    try:
        findings = json.loads(result.stdout)
        if not isinstance(findings, list):
            raise ValueError()
        if bool(findings) != (result.returncode == FINDINGS_EXIT):
            raise ValueError()
        for finding in findings:
            if not isinstance(finding, dict):
                raise ValueError()
            path = finding.get("File", "")
            line = finding.get("StartLine", 0)
            commit = finding.get("Commit", "")
            if not isinstance(path, str) or not isinstance(line, int) or not isinstance(commit, str):
                raise ValueError()
            if snapshot and path.startswith(str(snapshot) + os.sep):
                path = path[len(str(snapshot)) + 1:]
            # Do not echo arbitrary rule IDs, metadata, matches, source, or logs.
            label = (commit[:12] + ":" if re.fullmatch(r"[0-9a-f]{40,64}", commit) else "") + path
            if not quiet:
                print(f"{json.dumps(label, ensure_ascii=True)}:{line}: secret matched (value redacted)")
    except (ValueError, TypeError):
        raise SafetyError("Gitleaks returned an invalid report; scan incomplete") from None
    return 1 if findings else 0


def validate_config(root):
    """Exercise the real parser even for unborn repositories and empty scans."""
    _invoke(root, ["stdin"], data=b"", quiet=True)


def _worktree_snapshot(root, destination):
    paths = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    for raw in sorted(set(paths.split(b"\0"))):
        if not raw:
            continue
        relative = Path(os.fsdecode(raw))
        if relative.is_absolute() or ".." in relative.parts:
            raise SafetyError("unsafe Git path; worktree scan incomplete")
        source = root / relative
        # A tracked directory replaced by a symlink must not expose its destination.
        for parent in relative.parents:
            if parent != Path(".") and (root / parent).is_symlink():
                raise SafetyError("symlink in a tracked file's parent path; scan incomplete")
        try:
            info = source.lstat()
        except FileNotFoundError:
            continue  # A worktree deletion contains no publishable bytes.
        if stat.S_ISDIR(info.st_mode):
            continue  # Submodules are separate repositories.
        if stat.S_ISLNK(info.st_mode):
            content = os.fsencode(os.readlink(source))
        elif stat.S_ISREG(info.st_mode):
            fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(fd, "rb") as stream:
                content = stream.read()
        else:
            raise SafetyError("unsupported working-tree file type; scan incomplete")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def scan(root, mode):
    root = Path(root)
    if mode == "staged":
        if git(root, "ls-files", "--unmerged", "-z"):
            raise SafetyError("unmerged index entries; staged secret scan incomplete")
        return _invoke(root, ["git", "--staged", str(root)])
    if mode == "history":
        if git(root, "rev-parse", "--is-shallow-repository").strip() == b"true":
            raise SafetyError("shallow history; secret scan incomplete")
        if not git(root, "rev-list", "--all").strip():
            validate_config(root)
            return 0
        return _invoke(root, ["git", "--log-opts=" + HISTORY_OPTIONS, str(root)])
    if mode == "worktree":
        with temporary_directory(root, "git-safety-secrets-") as directory:
            snapshot = Path(directory) / "content"
            snapshot.mkdir()
            _worktree_snapshot(root, snapshot)
            return _invoke(root, ["dir", str(snapshot)], snapshot=snapshot)
    raise SafetyError("unsupported secret scan mode")
