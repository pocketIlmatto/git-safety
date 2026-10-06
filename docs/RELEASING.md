# Release preparation

Releases are manual. Nothing here tags, uploads or publishes; publication steps are
listed at the end and need explicit owner approval.

## Build the archive

1. Commit all changes and set `__version__` in `git_safety/__init__.py`.
2. Build from the committed revision, writing outside any Git worktree:

   ```sh
   python3 scripts/build-release.py --version 0.1.0 --ref HEAD --output-dir ~/git-safety-release
   ```

The builder archives only files tracked at that commit, so ignored files, local
policy and `.git` data are excluded. It refuses a version that differs from the
package, an output directory inside a worktree, and a missing tracked license file
(`--allow-missing-license` builds a candidate that must not be published).
The tarball and its `.sha256` file are deterministic: the same commit gives the
same digest. Never replace a published asset or retag a version; release a new
version instead. A checksum verifies bytes, not publisher identity.

## Formula and tap staging

After building, render the formula and stage the tap contents for review
(see `packaging/homebrew/`):

```sh
python3 scripts/render-formula.py --version 0.1.0 \
  --url https://github.com/pocketIlmatto/git-safety/releases/download/v0.1.0/git-safety-0.1.0.tar.gz \
  --sha256 "$(cut -d' ' -f1 ~/git-safety-release/git-safety-0.1.0.tar.gz.sha256)" \
  --license <SPDX id chosen by the owner> \
  --output-dir ~/git-safety-tap
```

## Before publishing

Review the exact commit, archive digest, rendered formula, tap files, license and
test results. Then, with approval: push the `vX.Y.Z` tag, attach the archive to a
GitHub release, publish the tap repository, and verify
`brew install pocketIlmatto/tools/git-safety` from the remote tap.
