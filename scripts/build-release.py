"""Build a deterministic release archive from a committed source revision.

The archive contains only files tracked at the chosen revision, so ignored files,
local policy and .git data cannot enter it. Nothing is tagged, uploaded or published.
"""

import argparse
import gzip
import hashlib
import io
from pathlib import Path
import re
import subprocess
import sys
import tarfile

SOURCE = Path(__file__).resolve().parents[1]
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
VERSION_LINE = re.compile(r'^__version__ = "([^"]+)"$', re.MULTILINE)
LICENSE_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING")
MODES = {"100644": 0o644, "100755": 0o755}


class ReleaseError(Exception):
    pass


def git(repo, *args, text=True):
    result = subprocess.run(["git", "-C", str(repo), *args], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise ReleaseError("git " + args[0] + " failed: " + result.stderr.decode(errors="replace").strip())
    return result.stdout.decode() if text else result.stdout


def inside_worktree(directory):
    probe = directory
    while not probe.exists():
        probe = probe.parent
    result = subprocess.run(["git", "-C", str(probe), "rev-parse", "--is-inside-work-tree"],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return result.returncode == 0 and result.stdout.strip() == b"true"


def build(repo, version, ref, output_dir, allow_missing_license=False):
    if not VERSION.fullmatch(version):
        raise ReleaseError("version must look like 1.2.3")
    if inside_worktree(output_dir):
        raise ReleaseError("output directory must be outside any Git worktree")
    commit = git(repo, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").strip()
    declared = VERSION_LINE.search(git(repo, "show", commit + ":git_safety/__init__.py"))
    if not declared or declared[1] != version:
        raise ReleaseError(f"package version at {commit[:12]} is {declared and declared[1]}, not {version}")
    timestamp = int(git(repo, "show", "-s", "--format=%ct", commit).strip())
    entries = []
    for record in git(repo, "ls-tree", "-r", "-z", "--full-tree", commit, text=False).split(b"\0"):
        if not record:
            continue
        meta, path = record.split(b"\t", 1)
        mode, kind, blob = meta.decode().split()
        if mode not in MODES or kind != "blob":
            raise ReleaseError(f"unsupported tracked entry {path.decode(errors='replace')!r} ({mode})")
        entries.append((path, mode, blob))
    names = {path.decode() for path, _, _ in entries}
    license_files = [name for name in LICENSE_NAMES if name in names]
    if not license_files and not allow_missing_license:
        raise ReleaseError("no license file is tracked; the owner must choose one, or pass "
                           "--allow-missing-license for an unpublishable candidate")
    prefix = f"git-safety-{version}"
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, compresslevel=9, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for path, mode, blob in sorted(entries):
                content = git(repo, "cat-file", "blob", blob, text=False)
                info = tarfile.TarInfo(f"{prefix}/{path.decode()}")
                info.size, info.mtime, info.mode = len(content), timestamp, MODES[mode]
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                archive.addfile(info, io.BytesIO(content))
    data = buffer.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{prefix}.tar.gz"
    archive_path.write_bytes(data)
    (output_dir / f"{prefix}.tar.gz.sha256").write_text(f"{digest}  {archive_path.name}\n")
    return archive_path, digest, commit, license_files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--ref", required=True, help="commit-ish to archive; no default, to keep releases explicit")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--repo", type=Path, default=SOURCE, help=argparse.SUPPRESS)
    parser.add_argument("--allow-missing-license", action="store_true")
    args = parser.parse_args()
    try:
        path, digest, commit, licenses = build(args.repo, args.version, args.ref,
                                               args.output_dir.expanduser().resolve(),
                                               args.allow_missing_license)
    except ReleaseError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(f"archive: {path}\nsha256:  {digest}\ncommit:  {commit}\nlicense: {', '.join(licenses) or 'NONE (candidate only)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
