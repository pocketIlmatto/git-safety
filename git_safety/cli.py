"""Command line entry point and independent coverage aggregation."""

import argparse
import os
from pathlib import Path
import re
import shutil
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from git_safety import __version__, policy, privacy, secrets, setup
from git_safety.common import SafetyError, git, repository_root, run


def dependencies(engine):
    if engine == "privacy":
        if not shutil.which("rg"):
            raise SafetyError("ripgrep is missing; install ripgrep 13 or later (brew install ripgrep)")
        output = run(["rg", "--version"]).stdout
        match = re.match(rb"ripgrep (\d+)\.", output)
        if not match or int(match[1]) < 13:
            raise SafetyError("unsupported ripgrep; install ripgrep 13 or later")
    else:
        secrets.check_dependency()


def repository_checks(root):
    version = run(["git", "--version"]).stdout
    match = re.search(rb"git version (\d+)\.(\d+)", version)
    if not match or tuple(map(int, match.groups())) < (2, 31):
        raise SafetyError("git-safety requires Git 2.31 or later")
    # Older Git may ignore GIT_NO_LAZY_FETCH. Refuse promisor repositories before
    # reading any objects, so scan commands cannot initiate lazy network fetches.
    partial = git(root, "config", "--get-regexp", r"^(remote\..*\.promisor|extensions\.partialclone)$",
                  accepted=(0, 1))
    if partial:
        raise SafetyError("partial/promisor clone cannot be audited offline; use a full local clone")


def history_complete(root):
    if git(root, "rev-parse", "--is-shallow-repository").strip() == b"true":
        raise SafetyError("shallow history: history coverage did not run; fetch full relevant history "
                          "(for example git fetch --unshallow), then retry; nothing was fetched")


def scan(root, mode):
    modes = ("staged", "worktree", "history") if mode == "all" else (mode,)
    status = 0
    ready = {}
    for engine in ("privacy", "secrets"):
        try:
            dependencies(engine)
            if engine == "privacy":
                policy.validate_policy(root)
            ready[engine] = True
        except SafetyError as error:
            ready[engine] = False
            print(f"ERROR: {engine} coverage did not run: {error}", file=sys.stderr)
            status = 2
    for coverage in modes:
        if coverage == "history":
            try:
                history_complete(root)
            except SafetyError as error:
                print(f"ERROR: {error}", file=sys.stderr)
                status = 2
                continue
        for engine, scanner in (("privacy", privacy.scan), ("secrets", secrets.scan)):
            if not ready[engine]:
                continue
            print(f"== {coverage}: {engine} ==", flush=True)
            try:
                result = scanner(root, coverage)
            except (SafetyError, OSError, ValueError) as error:
                message = str(error) if isinstance(error, SafetyError) else "read/parse failure (details suppressed)"
                print(f"ERROR: {coverage} {engine} incomplete: {message}", file=sys.stderr)
                result = 2
            status = max(status, result)
            print(f"{coverage} {engine}: {('clean', 'findings', 'incomplete')[result]}")
    if status == 0:
        print("Requested security checks passed.")
    elif status == 1:
        print("Security findings detected; review the reported locations.")
    else:
        print("Security checks incomplete; no overall pass.", file=sys.stderr)
    return status


def doctor(root):
    status = setup.doctor(root)
    for engine in ("privacy", "secrets"):
        try:
            dependencies(engine)
            if engine == "privacy":
                policy.validate_policy(root)
            else:
                secrets.validate_config(root)
            print(f"git-safety doctor: {engine} dependency and policy valid")
        except (SafetyError, OSError, ValueError) as error:
            message = str(error) if isinstance(error, SafetyError) else "unreadable configuration (details suppressed)"
            print(f"git-safety doctor: {message}", file=sys.stderr)
            status = 2
    try:
        history_complete(root)
    except SafetyError as error:
        print(f"git-safety doctor: {error}", file=sys.stderr)
        status = 2
    print("git-safety doctor: PATH describes this process; verify the PATH of GUI Git clients separately")
    return status


def main(argv=None):
    parser = argparse.ArgumentParser(prog="git-safety", description="Scan publishable Git content with privacy rules and Gitleaks.")
    parser.add_argument("--version", action="version", version="git-safety " + __version__)
    parser.add_argument("command", nargs="?", default="all", choices=(
        "staged", "worktree", "history", "all", "init", "install-hook", "uninstall-hook", "doctor"))
    args = parser.parse_args(argv)
    try:
        if sys.version_info < (3, 9):
            raise SafetyError("git-safety requires Python 3.9 or later")
        if not shutil.which("git"):
            raise SafetyError("Git is missing; install Git 2.31 or later")
        root = repository_root()
        if args.command in ("init", "install-hook", "uninstall-hook"):
            result = setup.run(args.command, root)
            print(f"git-safety {args.command}: complete")
            return result
        repository_checks(root)
        if args.command == "doctor":
            return doctor(root)
        return scan(root, args.command)
    except SafetyError as error:
        print(f"ERROR: {error}", file=sys.stderr)
    except (OSError, ValueError):
        print("ERROR: operation incomplete (private diagnostics suppressed)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
