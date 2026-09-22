"""Non-overwriting symlink lifecycle for an explicitly chosen toolkit checkout."""

import argparse
from pathlib import Path
import sys

SOURCE = Path(__file__).resolve().parents[1] / "bin" / "git-safety"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "uninstall"))
    parser.add_argument("--bin-dir", type=Path, default=Path.home() / ".local" / "bin")
    args = parser.parse_args()
    link = args.bin_dir.expanduser() / "git-safety"
    owned = link.is_symlink() and link.resolve() == SOURCE
    if args.action == "uninstall":
        if owned:
            link.unlink()
        elif link.exists() or link.is_symlink():
            parser.error("refusing removal: CLI path is not this checkout's symlink")
        print("CLI symlink removed; repository policies and hooks were preserved.")
    else:
        if not owned:
            if link.exists() or link.is_symlink():
                parser.error("refusing replacement: CLI path already exists; remove its owned installation first")
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(SOURCE)
        print("CLI symlink installed. Add the selected bin directory to PATH, then run git-safety doctor.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except OSError:
        print("ERROR: CLI installation incomplete; check directory permissions.", file=sys.stderr)
        sys.exit(2)
