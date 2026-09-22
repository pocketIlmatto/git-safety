"""Loading and validation for repository privacy policy files."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from .common import SafetyError


POLICY_DIRECTORY = ".git-safety"
PUBLIC_POLICY_FILES = ("privacy-patterns", "privacy-allowlist")
LOCAL_POLICY_FILES = ("privacy-patterns.local", "privacy-allowlist.local")


def _read_regular_file(path: Path, *, required: bool) -> bytes:
    """Read a policy file without accepting a symlink or special file."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        if required:
            raise SafetyError(f"required privacy policy file is missing: {path.name}")
        return b""
    except OSError as error:
        raise SafetyError("privacy policy could not be inspected") from error
    if not stat.S_ISREG(info.st_mode):
        raise SafetyError(f"privacy policy file must be a regular file: {path.name}")
    try:
        return path.read_bytes()
    except OSError as error:
        raise SafetyError(f"privacy policy file is not readable: {path.name}") from error


def policy_paths(root: Path) -> dict[str, Path]:
    directory = root / POLICY_DIRECTORY
    return {name: directory / name for name in (*PUBLIC_POLICY_FILES, *LOCAL_POLICY_FILES)}


def load_policy(root: Path) -> tuple[bytes, bytes]:
    """Return newline-normalized rule and exception data from on-disk policy."""
    paths = policy_paths(root)
    values = {
        name: _read_regular_file(paths[name], required=name in PUBLIC_POLICY_FILES)
        for name in paths
    }
    return (
        _meaningful_lines(values["privacy-patterns"], values["privacy-patterns.local"]),
        _meaningful_lines(values["privacy-allowlist"], values["privacy-allowlist.local"]),
    )


def _meaningful_lines(*contents: bytes) -> bytes:
    lines: list[bytes] = []
    for content in contents:
        lines.extend(
            line for line in content.splitlines()
            if line.strip() and not line.lstrip().startswith(b"#")
        )
    return b"\n".join(lines) + (b"\n" if lines else b"")


def validate_policy(root: Path) -> None:
    """Verify public/local policy file shape and ripgrep syntax.

    The import is intentionally local to avoid making policy loading depend on the
    scanner's implementation details.
    """
    rules, allowlist = load_policy(root)
    from .privacy import validate_regexes

    validate_regexes(rules, allowlist, root)
