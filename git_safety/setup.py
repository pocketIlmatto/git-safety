"""Repository-local setup, hook lifecycle, and non-invasive diagnostics."""

from __future__ import annotations

import os
import json
from pathlib import Path
import shutil
import stat
import subprocess
import sys

from .common import SafetyError


POLICY_DIR = ".git-safety"
PUBLIC_POLICIES = {
    "privacy-patterns": "# Repository-specific privacy patterns (one ripgrep regex per line).\n",
    "privacy-allowlist": "# Repository-specific privacy exceptions (one ripgrep regex per line).\n",
    "privacy-patterns.local.example": (
        "# Local-only privacy patterns. Copy to privacy-patterns.local; do not commit it.\n"
    ),
}
LOCAL_POLICIES = ("privacy-patterns.local", "privacy-allowlist.local")
OWNED_HOOK = """#!/bin/sh
# Installed by git-safety; do not edit.
if ! command -v git-safety >/dev/null 2>&1; then
  echo "git-safety: command not found; install git-safety and ensure it is on PATH." >&2
  exit 2
fi
exec git-safety staged
""".encode()


def _git_process(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", *args], cwd=root, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
    except OSError as exc:
        raise SafetyError("Git is unavailable; install Git and try again.") from exc


def _git(root: Path, *args: str, check: bool = True) -> str:
    completed = _git_process(root, *args)
    if check and completed.returncode != 0:
        raise SafetyError("Unable to inspect this Git repository.")
    if not check and completed.returncode not in (0, 1):
        raise SafetyError("Unable to inspect this Git repository.")
    return _decode_git_output(completed.stdout)


def _optional_git(root: Path, *args: str) -> tuple[bool, str]:
    """Return whether an optional Git value exists, failing on other errors."""
    completed = _git_process(root, *args)
    if completed.returncode == 1:
        return False, ""
    if completed.returncode != 0:
        raise SafetyError("Unable to inspect this Git repository.")
    return True, _decode_git_output(completed.stdout)


def _decode_git_output(output: bytes) -> str:
    """Remove Git's one record terminator without altering a valid value."""
    if output.endswith(b"\n"):
        output = output[:-1]
    return output.decode("utf-8", "surrogateescape")


def _regular_or_missing(path: Path, description: str) -> None:
    if path.is_symlink():
        raise SafetyError(f"Refusing {description}: it is a symlink.")
    if path.exists() and not path.is_file():
        raise SafetyError(f"Refusing {description}: it is not a regular file.")


def _safe_directory(path: Path, description: str) -> None:
    """Ensure an existing directory and all existing ancestors are not symlinks."""
    current = path
    existing: list[Path] = []
    while not current.exists() and current != current.parent:
        existing.append(current)
        current = current.parent
    if current.is_symlink() or (current.exists() and not current.is_dir()):
        raise SafetyError(f"Refusing {description}: unsafe directory path.")
    # Check downward from the existing ancestor.  This catches a symlinked child.
    for component in reversed(existing):
        if component.exists() and (component.is_symlink() or not component.is_dir()):
            raise SafetyError(f"Refusing {description}: unsafe directory path.")


def _no_symlink_below(path: Path, boundary: Path, description: str) -> None:
    """Reject symlink components below a directory Git/repository selected."""
    try:
        relative = path.relative_to(boundary)
    except ValueError as exc:
        raise SafetyError(f"Refusing {description}: it escapes its trusted directory.") from exc
    current = boundary
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise SafetyError(f"Refusing {description}: unsafe directory path.")


def _write_new(path: Path, content: str | bytes, mode: int | None = None) -> None:
    if path.exists() or path.is_symlink():
        return
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600 if mode is not None else 0o666)
    try:
        data = content.encode() if isinstance(content, str) else content
        os.write(fd, data)
    finally:
        os.close(fd)
    if mode is not None:
        path.chmod(mode)


def init(root: Path) -> int:
    """Create only missing public policy files and precise local ignore entries."""
    root = Path(root)
    policy_dir = root / POLICY_DIR
    _safe_directory(root, "repository root")
    if policy_dir.is_symlink() or (policy_dir.exists() and not policy_dir.is_dir()):
        raise SafetyError("Refusing policy setup: .git-safety is not a directory.")

    ignore = root / ".gitignore"
    _regular_or_missing(ignore, ".gitignore")
    # Add ignores before exposing templates, so an interrupted init cannot leave
    # a copied local policy accidentally publishable.
    existing = ignore.read_text("utf-8", "surrogateescape") if ignore.exists() else ""
    lines = existing.splitlines()
    missing = [f"{POLICY_DIR}/{name}" for name in LOCAL_POLICIES if f"{POLICY_DIR}/{name}" not in lines]
    if missing:
        addition = "".join(("" if not existing or existing.endswith("\n") else "\n") + "\n".join(missing) + "\n")
        if ignore.exists():
            with ignore.open("a", encoding="utf-8", errors="surrogateescape") as handle:
                handle.write(addition)
        else:
            _write_new(ignore, addition)
    for name in LOCAL_POLICIES:
        relative = f"{POLICY_DIR}/{name}"
        if not _ignored(root, relative):
            raise SafetyError(
                f"Refusing policy setup: {relative} is not effectively ignored; "
                "remove a later ignore negation and run init again."
            )

    if not policy_dir.exists():
        policy_dir.mkdir(mode=0o755)
    _safe_directory(policy_dir, ".git-safety")
    for name, content in PUBLIC_POLICIES.items():
        path = policy_dir / name
        _regular_or_missing(path, f"policy file {path.name}")
        _write_new(path, content)
    return 0


def _path_from_git(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _hook_location(root: Path) -> tuple[Path, bool, str | None, bool]:
    """Return (directory, default_location, config_origin, shared_worktree)."""
    configured_set, configured = _optional_git(root, "config", "--path", "--get", "core.hooksPath")
    origin_set, origin = _optional_git(root, "config", "--show-origin", "--show-scope", "--get", "core.hooksPath")
    if configured_set:
        if not configured:
            raise SafetyError("Refusing hook installation: core.hooksPath is empty.")
        if not origin_set:
            raise SafetyError("Unable to inspect configured hooks directory safely.")
        scope = origin.split("\t", 1)[0] if origin else ""
        if scope not in {"local", "worktree"}:
            raise SafetyError(
                "Refusing hook installation: core.hooksPath is inherited outside this repository."
            )
        hook_dir = _path_from_git(root, configured)
        # A configured hooks directory is acceptable only if it is visibly owned
        # by this checkout, never an inherited home/shared location.
        try:
            resolved = hook_dir.resolve(strict=False)
            root_resolved = root.resolve(strict=True)
        except OSError as exc:
            raise SafetyError("Unable to resolve configured hooks directory safely.") from exc
        if not _is_within(resolved, root_resolved):
            raise SafetyError(
                "Refusing hook installation: core.hooksPath is outside this repository."
            )
        _safe_directory(hook_dir, "configured hooks directory")
        _no_symlink_below(hook_dir, root, "configured hooks directory")
        return hook_dir, False, origin, False

    hook_dir = _path_from_git(root, _git(root, "rev-parse", "--git-path", "hooks"))
    git_dir = _path_from_git(root, _git(root, "rev-parse", "--git-dir"))
    common_dir = _path_from_git(root, _git(root, "rev-parse", "--git-common-dir"))
    try:
        resolved_hook = hook_dir.resolve(strict=False)
        resolved_git = git_dir.resolve(strict=False)
        resolved_common = common_dir.resolve(strict=False)
        in_worktree = _is_within(resolved_hook, resolved_git)
        in_common = _is_within(resolved_hook, resolved_common)
        # A linked worktree can legitimately use the common Git hooks directory.
        if not in_worktree and not in_common:
            raise SafetyError("Refusing hook installation: Git returned an unsafe hooks path.")
    except OSError as exc:
        raise SafetyError("Unable to resolve Git hooks directory safely.") from exc
    _safe_directory(hook_dir, "Git hooks directory")
    _no_symlink_below(hook_dir, common_dir if in_common else git_dir, "Git hooks directory")
    return hook_dir, True, None, in_common and not in_worktree


def _hook_path(root: Path) -> Path:
    hook_dir, _, _, _ = _hook_location(root)
    if not hook_dir.exists():
        hook_dir.mkdir(mode=0o755, parents=True)
    if hook_dir.is_symlink() or not hook_dir.is_dir():
        raise SafetyError("Refusing hook installation: hooks directory is unsafe.")
    return hook_dir / "pre-commit"


def install_hook(root: Path) -> int:
    hook = _hook_path(Path(root))
    if hook.is_symlink():
        raise SafetyError("Refusing hook installation: existing pre-commit hook is a symlink.")
    if hook.exists():
        if not hook.is_file():
            raise SafetyError("Refusing hook installation: existing pre-commit hook is not a file.")
        if hook.read_bytes() == OWNED_HOOK:
            if not hook.stat().st_mode & 0o111:
                hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            return 0
        raise SafetyError("Refusing hook installation: an existing pre-commit hook is not owned by git-safety.")
    _write_new(hook, OWNED_HOOK, 0o755)
    return 0


def uninstall_hook(root: Path) -> int:
    hook_dir, _, _, _ = _hook_location(Path(root))
    hook = hook_dir / "pre-commit"
    if hook.is_symlink():
        raise SafetyError("Refusing hook removal: pre-commit hook is a symlink.")
    if not hook.exists():
        return 0
    if not hook.is_file():
        raise SafetyError("Refusing hook removal: pre-commit hook is not a regular file.")
    if hook.read_bytes() != OWNED_HOOK:
        raise SafetyError("Refusing hook removal: existing pre-commit hook is not owned by git-safety.")
    hook.unlink()
    return 0


def _tracked(root: Path, relative: str) -> bool:
    return bool(_git(root, "ls-files", "--error-unmatch", "--", relative, check=False))


def _ignored(root: Path, relative: str) -> bool:
    completed = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", "--", relative], cwd=root,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def _safe_display(value: Path | str) -> str:
    return json.dumps(os.fsdecode(os.fspath(value)), ensure_ascii=True)


def doctor(root: Path) -> int:
    """Report setup state without reading any private local policy content."""
    root = Path(root)
    errors: list[str] = []
    notices: list[str] = []
    for name in ("privacy-patterns", "privacy-allowlist"):
        path = root / POLICY_DIR / name
        if path.is_symlink() or not path.is_file() or not os.access(path, os.R_OK):
            errors.append(f"missing or unreadable required policy: {POLICY_DIR}/{name}")
    try:
        hook_dir, is_default, origin, shared_worktree = _hook_location(root)
        hook = hook_dir / "pre-commit"
        if hook.is_symlink():
            errors.append("pre-commit hook path is unsafe")
        elif hook.exists() and hook.is_file():
            if hook.read_bytes() == OWNED_HOOK:
                if hook.stat().st_mode & 0o111:
                    notices.append("pre-commit hook: git-safety")
                else:
                    errors.append("git-safety pre-commit hook is not executable")
            else:
                notices.append("pre-commit hook: existing user hook")
        elif hook.exists():
            errors.append("pre-commit hook path is unsafe")
        else:
            notices.append("pre-commit hook: not installed")
        if not is_default:
            notices.append(
                f"core.hooksPath: {_safe_display(hook_dir)}"
                + (f" ({_safe_display(origin)})" if origin else "")
            )
        if shared_worktree:
            notices.append("pre-commit hook location is shared across linked worktrees")
    except SafetyError as exc:
        errors.append(str(exc))
    if shutil.which("git-safety") is None:
        errors.append("git-safety is not on PATH; hooks will fail in this environment")

    for name in LOCAL_POLICIES:
        relative = f"{POLICY_DIR}/{name}"
        path = root / relative
        if _tracked(root, relative):
            errors.append(f"local policy is tracked: {relative}")
        elif path.exists() and not _ignored(root, relative):
            errors.append(f"local policy is not ignored: {relative}")
        elif path.exists():
            notices.append(f"local policy: {relative} is ignored")
    for message in notices:
        print(f"git-safety doctor: {message}")
    for message in errors:
        print(f"git-safety doctor: {message}", file=sys.stderr)
    return 2 if errors else 0


def run(command: str, root: Path) -> int:
    commands = {
        "init": init,
        "install-hook": install_hook,
        "uninstall-hook": uninstall_hook,
        "doctor": doctor,
    }
    try:
        return commands[command](Path(root))
    except KeyError as exc:
        raise SafetyError(f"Unknown setup command: {command}") from exc
