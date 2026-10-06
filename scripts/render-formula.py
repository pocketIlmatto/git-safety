"""Render the Homebrew formula and stage a local tap directory for review."""

import argparse
from pathlib import Path
import re
import sys

SOURCE = Path(__file__).resolve().parents[1]
TEMPLATES = SOURCE / "packaging" / "homebrew"
LICENSE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+-]*( (AND|OR|WITH) [A-Za-z0-9][A-Za-z0-9.+-]*)*")


def render(version, url, sha256, license_id=None, local_archive=False):
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("version must look like 1.2.3")
    scheme = "file://" if local_archive else "https://"
    if not re.fullmatch(re.escape(scheme) + r"[A-Za-z0-9._~/%-]+", url) or not url.endswith(f"/git-safety-{version}.tar.gz"):
        raise ValueError(f"url must be {scheme} and end with /git-safety-{version}.tar.gz")
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
    if license_id is not None and not LICENSE.fullmatch(license_id):
        raise ValueError("license must be an SPDX expression")
    text = (TEMPLATES / "git-safety.rb.in").read_text()
    text = text.replace("@URL@", url).replace("@SHA256@", sha256)
    text = text.replace("@LICENSE@\n", f'  license "{license_id}"\n\n' if license_id else "\n")
    text = text.replace("\n\n\n", "\n\n")
    # The wrapper tokens are filled by the formula at install time, not here.
    if set(re.findall(r"@[A-Z_]+@", text)) - {"@DEPENDENCY_PATH@", "@PYTHON@", "@LIBEXEC@"}:
        raise ValueError("unresolved template token")
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--license", help="SPDX identifier chosen by the owner; omitted if unset")
    parser.add_argument("--local-archive", action="store_true",
                        help="prepublication testing only: require a file:// URL instead of https://")
    parser.add_argument("--output-dir", required=True, type=Path, help="staged tap directory")
    args = parser.parse_args()
    try:
        formula = render(args.version, args.url, args.sha256, args.license, args.local_archive)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    (args.output_dir / "Formula").mkdir(parents=True, exist_ok=True)
    (args.output_dir / "Formula" / "git-safety.rb").write_text(formula)
    (args.output_dir / "README.md").write_text((TEMPLATES / "tap-README.md").read_text())
    print(f"staged tap contents in {args.output_dir}")
    if not args.license:
        print("WARNING: no license set; the owner must choose one before publication", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
