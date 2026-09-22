"""Shared fail-closed process and repository helpers."""

import os
from pathlib import Path
import subprocess
import tempfile


class SafetyError(Exception):
    """An actionable message that contains no subprocess or private content."""


def environment():
    env = dict(os.environ)
    env["GIT_NO_LAZY_FETCH"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env


def run(args, *, cwd=None, data=None, accepted=(0,), env=None):
    try:
        result = subprocess.run(args, cwd=cwd, input=data, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=env or environment())
    except OSError:
        raise SafetyError("required command could not start; check installed dependencies") from None
    if result.returncode not in accepted:
        raise SafetyError("command failed; scan incomplete (output suppressed)")
    return result


def git(root, *args, accepted=(0,)):
    return run(["git", *args], cwd=root, accepted=accepted).stdout


def repository_root():
    value = git(None, "rev-parse", "--show-toplevel")
    # Remove only Git's terminating newline: a directory name can end in a newline.
    return Path(os.fsdecode(value[:-1] if value.endswith(b"\n") else value))


def temporary_directory(root, prefix="git-safety-"):
    """Keep scratch data outside the scanned repository even with a local TMPDIR."""
    root = Path(root).resolve()
    for candidate in (Path(tempfile.gettempdir()), Path("/tmp")):
        candidate = candidate.resolve()
        if candidate != root and root not in candidate.parents:
            return tempfile.TemporaryDirectory(prefix=prefix, dir=candidate)
    raise SafetyError("no temporary directory outside the repository is available")
