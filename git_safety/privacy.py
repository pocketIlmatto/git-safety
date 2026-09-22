"""Byte-safe privacy scanning for staged, working-tree, and history content."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from .common import SafetyError, git as common_git, run as common_run, temporary_directory
from .policy import load_policy


# These defaults cover generic private data. Repository-specific identifiers
# belong in .git-safety/privacy-patterns rather than in this package.
BUILTIN_RULES = b"""/Users/[A-Za-z0-9._-]+/
[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}
https?://[^[:space:]/:@]+:[^[:space:]@]+@
"""
BUILTIN_ALLOWLIST = b"""^[A-Za-z0-9._%+-]+@example\\.(com|org|net)$
^/Users/(username|yourname)/$
"""

# Privacy patterns themselves contain examples of values which match them. The
# exemption is deliberately a finite list, never a directory-level exclusion.
POLICY_PATHS = frozenset({
    b".git-safety/privacy-patterns",
    b".git-safety/privacy-patterns.local",
    b".git-safety/privacy-patterns.local.example",
    b".git-safety/privacy-allowlist",
    b".git-safety/privacy-allowlist.local",
    b".privacy-patterns",
    b".privacy-patterns.local",
    b".privacy-patterns.local.example",
    b".privacy-allowlist",
    b".privacy-allowlist.local",
})


class ScanFailure(SafetyError):
    """A fail-closed scanner/dependency failure safe to print to a user."""


def _run(args: list[str], *, cwd: Path, data: bytes | None = None,
         accepted: tuple[int, ...] = (0,)) -> bytes:
    return common_run(args, cwd=cwd, data=data, accepted=accepted).stdout


def _git(root: Path, *args: str) -> bytes:
    return common_git(root, *args)


def _json_bytes(value: dict[str, str]) -> bytes:
    return value["text"].encode("utf-8") if "text" in value else base64.b64decode(value["bytes"])


def _combine(*chunks: bytes) -> bytes:
    lines = [line for chunk in chunks for line in chunk.splitlines() if line]
    return b"\n".join(lines) + (b"\n" if lines else b"")


def validate_regexes(rules: bytes, allowlist: bytes, root: Path | None = None) -> None:
    """Ensure ripgrep and both policy regex sets are usable before scanning."""
    if shutil.which("rg") is None:
        raise ScanFailure("privacy scanning requires ripgrep (rg)")
    directory_context = (temporary_directory(root, prefix="git-safety-privacy-")
                         if root is not None else tempfile.TemporaryDirectory(prefix="git-safety-privacy-"))
    with directory_context as directory:
        base = Path(directory)
        rules_path = base / "rules"
        allow_path = base / "allowlist"
        rules_path.write_bytes(rules)
        allow_path.write_bytes(allowlist)
        _rg(rules_path, b"")
        if allowlist:
            _rg(allow_path, b"")


def _rg(pattern_file: Path, data: bytes, *, json_output: bool = False) -> bytes:
    args = ["rg", "--no-config", "--text", "--ignore-case", "--color=never"]
    if json_output:
        args.append("--json")
    args.extend(["-f", str(pattern_file), "-"])
    # ripgrep exits 1 when it has no matches, which is normal.
    return _run(args, cwd=Path.cwd(), data=data, accepted=(0, 1))


class _Scanner:
    def __init__(self, root: Path, rules: bytes, allowlist: bytes):
        self.root = root
        self.findings = 0
        self.allowed: dict[bytes, bool] = {}
        self._temporary = temporary_directory(root, prefix="git-safety-privacy-")
        base = Path(self._temporary.name)
        self.rules_path = base / "rules"
        self.allow_path = base / "allowlist"
        self.rules_path.write_bytes(rules)
        self.allow_path.write_bytes(allowlist)
        _rg(self.rules_path, b"")
        if allowlist:
            _rg(self.allow_path, b"")
        self.has_allowlist = bool(allowlist)

    def close(self) -> None:
        self._temporary.cleanup()

    def scan_data(self, data: bytes, label: bytes, line_offset: int = 0) -> None:
        for raw in _rg(self.rules_path, data, json_output=True).splitlines():
            try:
                event = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ScanFailure("ripgrep produced invalid scan output; scan incomplete") from error
            if event.get("type") != "match":
                continue
            match = event["data"]
            for submatch in match["submatches"]:
                value = _json_bytes(submatch["match"])
                if value not in self.allowed:
                    self.allowed[value] = self.has_allowlist and bool(
                        _rg(self.allow_path, value)
                    )
                if self.allowed[value]:
                    continue
                self.findings += 1
                location = json.dumps(os.fsdecode(label), ensure_ascii=True)
                print(f"{location}:{match['line_number'] + line_offset}:"
                      f"{submatch['start'] + 1}: private pattern matched (value redacted)")

    def staged(self) -> None:
        paths = _git(self.root, "diff", "--cached", "--name-only", "-z", "--no-renames",
                     "--diff-filter=ACMRT").split(b"\0")
        for path in paths:
            if not path or path in POLICY_PATHS:
                continue
            diff = _git(self.root, "--literal-pathspecs", "diff", "--cached", "--no-ext-diff",
                        "--no-textconv", "--no-color", "--no-renames", "--text", "--unified=0",
                        "--", os.fsdecode(path))
            line_number: int | None = None
            remaining = 0
            for line in diff.split(b"\n"):
                hunk = re.match(rb"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
                if hunk:
                    line_number = int(hunk[1])
                    remaining = int(hunk[2]) if hunk[2] is not None else 1
                elif line_number is not None and remaining and line.startswith(b"+"):
                    self.scan_data(line[1:] + b"\n", path, line_number - 1)
                    line_number += 1
                    remaining -= 1
                elif line_number is not None and remaining and line.startswith(b" "):
                    line_number += 1
                    remaining -= 1

    def worktree(self) -> None:
        paths = _git(self.root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
        for path in sorted(set(paths.split(b"\0"))):
            if not path or path in POLICY_PATHS:
                continue
            file_path = self.root / os.fsdecode(path)
            try:
                info = file_path.lstat()
            except FileNotFoundError:
                # A concurrent removal is not publishable from this working tree.
                continue
            except OSError as error:
                raise ScanFailure("working-tree file could not be inspected; scan incomplete") from error
            if os.path.islink(file_path):
                self.scan_data(os.fsencode(os.readlink(file_path)), path)
            elif __import__("stat").S_ISREG(info.st_mode):
                try:
                    self.scan_data(file_path.read_bytes(), path)
                except OSError as error:
                    raise ScanFailure("working-tree file could not be read; scan incomplete") from error
            elif not __import__("stat").S_ISDIR(info.st_mode):
                raise ScanFailure("unsupported working-tree file type; scan incomplete")

    def history(self) -> None:
        seen: set[bytes] = set()
        for commit in _git(self.root, "rev-list", "--all").splitlines():
            tree = _git(self.root, "ls-tree", "-r", "-z", commit.decode("ascii"))
            for entry in tree.split(b"\0"):
                if not entry:
                    continue
                metadata, path = entry.split(b"\t", 1)
                _, kind, oid = metadata.split()
                if kind != b"blob" or path in POLICY_PATHS or oid in seen:
                    continue
                seen.add(oid)
                self.scan_data(_git(self.root, "cat-file", "blob", oid.decode("ascii")),
                               commit[:12] + b":" + path)


def scan(root: Path, mode: str) -> int:
    """Scan one coverage mode and return 0 clean, 1 findings, or 2 incomplete."""
    if mode not in {"staged", "worktree", "history", "all"}:
        print("ERROR: privacy mode must be staged, worktree, history, or all", file=os.sys.stderr)
        return 2
    try:
        rules, allowlist = load_policy(root)
        rules = _combine(BUILTIN_RULES, rules)
        allowlist = _combine(BUILTIN_ALLOWLIST, allowlist)
        scanner = _Scanner(root, rules, allowlist)
        try:
            if mode in {"staged", "all"}:
                scanner.staged()
            if mode in {"worktree", "all"}:
                scanner.worktree()
            if mode in {"history", "all"}:
                scanner.history()
            if scanner.findings:
                print(f"Privacy check failed: {scanner.findings} finding(s). "
                      "Remove private values or allowlist individual legitimate matches.")
                return 1
        finally:
            scanner.close()
    except (SafetyError, OSError, ValueError, UnicodeError):
        print("ERROR: privacy scan incomplete", file=os.sys.stderr)
        return 2
    print("Privacy check passed")
    return 0
