#!/usr/bin/env python3
"""Optional, disposable parity check against an explicitly supplied legacy checkout.

The source checkout is never run in place.  Only its public privacy scanner and
public policy files are copied into temporary Git repositories; local policy
files are deliberately neither read nor copied.  This intentionally covers
privacy parity only; secrets have a deliberately expanded coverage contract.
"""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Callable, Dict, Iterable, Tuple


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from git_safety import privacy  # noqa: E402


ASSETS = (
    ("scripts/privacy-check", "scripts/privacy-check"),
    ("scripts/privacy_check.py", "scripts/privacy_check.py"),
    (".privacy-patterns", ".privacy-patterns"),
    (".privacy-allowlist", ".privacy-allowlist"),
)
MODES = ("staged", "worktree", "history", "all")
PRIVATE_HOME = b"/" + b"Users/" + b"parity-user/"
PRIVATE_EMAIL = b"parity.user" + b"@" + b"private.invalid"
SAFE_EMAIL = b"placeholder" + b"@" + b"example.com"
PRIVATE_BEAR = b"bear://x-callback-url/open-note?id=" + b"12345678"


class ParityError(RuntimeError):
    pass


def _git(root: Path, *args: str) -> None:
    completed = subprocess.run(["git", *args], cwd=root, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode:
        raise ParityError("disposable Git fixture setup failed")


def _copy_assets(source: Path, destination: Path) -> None:
    """Copy exactly the public legacy inputs allowed to this harness."""
    for relative, target in ASSETS:
        original = source / relative
        if not original.is_file() or original.is_symlink():
            raise ParityError(f"required public reference asset is unavailable: {relative}")
        copied = destination / target
        copied.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, copied)
        if relative == "scripts/privacy-check":
            copied.chmod(0o755)


def _new_policy_from_public_assets(root: Path) -> None:
    policy = root / ".git-safety"
    policy.mkdir()
    shutil.copyfile(root / ".privacy-patterns", policy / "privacy-patterns")
    shutil.copyfile(root / ".privacy-allowlist", policy / "privacy-allowlist")


def _new_repo(source: Path, path: Path) -> None:
    path.mkdir()
    _copy_assets(source, path)
    _new_policy_from_public_assets(path)
    _git(path, "init", "-q")
    _git(path, "config", "user.name", "Parity Fixture")
    _git(path, "config", "user.email", "placeholder@example.com")
    _git(path, "config", "core.hooksPath", "/dev/null")
    _git(path, "add", ".")
    _git(path, "commit", "-qm", "public scanner baseline")


def _write(root: Path, name: str, data: bytes, stage: bool = True) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if stage:
        _git(root, "add", "--", name)


def _commit(root: Path, message: str) -> None:
    _git(root, "commit", "-qm", message)


def _safe_placeholders(root: Path) -> None:
    _write(root, "fixture.txt", SAFE_EMAIL + b" /Users/username/ "
           b"bear://x-callback-url/open-note?id=YOUR-BEAR-NOTE-ID\n")


def _partial_index_clean(root: Path) -> None:
    _write(root, "fixture.txt", b"clean\n")
    _write(root, "fixture.txt", PRIVATE_HOME, stage=False)


def _partial_index_sensitive(root: Path) -> None:
    _write(root, "fixture.txt", PRIVATE_EMAIL)
    _write(root, "fixture.txt", b"clean\n", stage=False)


def _deleted_history(root: Path) -> None:
    _write(root, "fixture.txt", PRIVATE_HOME)
    _commit(root, "sensitive fixture")
    _write(root, "fixture.txt", b"clean\n")


def _other_ref(root: Path) -> None:
    initial = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root).strip().decode("ascii")
    _git(root, "checkout", "-qb", "other-fixture-ref")
    _write(root, "fixture.txt", PRIVATE_EMAIL)
    _commit(root, "other ref fixture")
    _git(root, "checkout", "-q", "--detach", initial)


def _binary_unusual(root: Path) -> None:
    _write(root, "odd name\t[fixture].bin", b"\x00\xff" + PRIVATE_EMAIL)
    _write(root, "line\nfixture.txt", PRIVATE_HOME)
    _write(root, "--fixture.txt", PRIVATE_BEAR)


def _symlink_target(root: Path) -> None:
    (root / "link").symlink_to(PRIVATE_HOME.decode("ascii"))
    _git(root, "add", "link")


def _symlink_no_follow(root: Path) -> None:
    _write(root, ".gitignore", b"ignored.txt\n")
    _write(root, "ignored.txt", PRIVATE_HOME, stage=False)
    (root / "link").symlink_to("ignored.txt")
    _git(root, "add", ".gitignore", "link")


def _match_level_exception(root: Path) -> None:
    _write(root, "fixture.txt", SAFE_EMAIL + b" " + PRIVATE_EMAIL)


Fixture = Callable[[Path], None]
CASES: Tuple[Tuple[str, Fixture], ...] = (
    ("safe-placeholders", _safe_placeholders),
    ("partial-index-clean", _partial_index_clean),
    ("partial-index-sensitive", _partial_index_sensitive),
    ("deleted-history", _deleted_history),
    ("noncurrent-ref", _other_ref),
    ("binary-unusual-name", _binary_unusual),
    ("symlink-target", _symlink_target),
    ("symlink-no-follow", _symlink_no_follow),
    ("match-level-exception", _match_level_exception),
)


def _legacy_scan(root: Path, mode: str) -> Tuple[int, bytes]:
    completed = subprocess.run([str(root / "scripts/privacy-check"), f"--{mode}"], cwd=root,
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, check=False)
    return completed.returncode, completed.stdout + completed.stderr


def _new_scan(root: Path, mode: str) -> Tuple[int, bytes]:
    stdout, stderr = StringIO(), StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = privacy.scan(root, mode)
    return code, (stdout.getvalue() + stderr.getvalue()).encode("utf-8", "surrogateescape")


def _redacted(output: bytes) -> bool:
    return all(value not in output for value in (PRIVATE_HOME, PRIVATE_EMAIL, PRIVATE_BEAR))


@dataclass(frozen=True)
class Result:
    case: str
    mode: str
    legacy: int
    current: int
    legacy_redacted: bool
    current_redacted: bool


def compare(source: Path) -> Iterable[Result]:
    source = source.resolve()
    if not source.is_dir():
        raise ParityError("--source must name an existing reference repository")
    with tempfile.TemporaryDirectory(prefix="git-safety-parity-") as directory:
        base = Path(directory)
        for case, fixture in CASES:
            legacy_root, current_root = base / f"{case}-legacy", base / f"{case}-current"
            _new_repo(source, legacy_root)
            _new_repo(source, current_root)
            fixture(legacy_root)
            fixture(current_root)
            for mode in MODES:
                legacy_code, legacy_output = _legacy_scan(legacy_root, mode)
                current_code, current_output = _new_scan(current_root, mode)
                result = Result(case, mode, legacy_code, current_code,
                                _redacted(legacy_output), _redacted(current_output))
                if legacy_code != current_code:
                    raise ParityError(f"exit-code mismatch for {case}/{mode}: "
                                      f"legacy={legacy_code}, current={current_code}")
                if not result.legacy_redacted or not result.current_redacted:
                    raise ParityError(f"redaction mismatch for {case}/{mode}")
                yield result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run disposable privacy parity fixtures.")
    parser.add_argument("--source", type=Path, required=True,
                        help="explicit path to the read-only legacy checkout")
    args = parser.parse_args(argv)
    try:
        results = list(compare(args.source))
    except (ParityError, OSError, subprocess.SubprocessError) as error:
        print(f"ERROR: parity harness failed: {error}", file=sys.stderr)
        return 2
    for result in results:
        print(f"{result.case}/{result.mode}: legacy={result.legacy} current={result.current} "
              f"redacted=ok")
    print(f"Parity passed: {len(results)} privacy fixture/mode comparisons.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
