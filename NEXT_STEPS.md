2026-09-21
Please move forward with testing and supporting an explicit range of Gitleaks versions, then depend on the
  maintained formula. This needs compatibility tests; removing the exact-version
  check alone would not establish support.

Then implement a **Homebrew tap backed by versioned release archives** as the next install
experience.

2026-09-22 status: Compatibility range 8.29.1–8.30.1 implemented and tested.
Local dependency instructions now use the maintained Homebrew Gitleaks formula.
See docs/GITLEAKS_COMPATIBILITY.md. The toolkit tap/release archives remain next.

2026-09-22 plan: See docs/HOMEBREW_PLAN.md for implementation checkpoints,
packaging/lifecycle tests, release decisions, and publication boundaries. One
bounded sub-agent review informed the plan; implementation has not started.

2026-10-06 status: Homebrew checkpoints 1, 2 and 4 implemented locally (release
builder, formula template/renderer/wrapper, docs, Mac CI workflow). `brew style` and
`brew audit --strict` pass in a Linuxbrew container. Not done: running
scripts/homebrew-lifecycle.py (needs a disposable Homebrew with network access; first run
via the Mac workflow), choosing a license, and publication (tag, release, tap repo), which
need owner authorization. See docs/HOMEBREW.md and docs/RELEASING.md.

2026-10-06 update: PR #1 squash-merged; the Mac lifecycle workflow passed. MIT license
chosen and added (LICENSE; formula uses `--license MIT`). Remaining: publication (tag,
release, tap repo), which needs owner authorization.

2026-10-06 end-of-day: PR #1 (Homebrew packaging) and PR #2 (MIT license) are both
squash-merged to main; CI was green on each, including the Mac lifecycle workflow.
Nothing is published yet: no tag, release archive or tap repo exists, and
`brew install pocketIlmatto/tools/git-safety` does not work.

Remaining, in order. Steps 1-2 are public and hard to undo; get owner approval for each.
1. Tag v0.1.0 and build the release archive (scripts/build-release.py; see
   docs/RELEASING.md). A local dry run, building the archive and rendering the formula
   for review without pushing, is a safe first move.
2. Push the tag, attach the archive to a GitHub release, and create the tap repo
   pocketIlmatto/homebrew-tools from the formula rendered with `--license MIT` and the
   real archive sha256 (packaging/homebrew/tap-README.md seeds the tap).
3. Verify a real install on a clean Mac: `brew install pocketIlmatto/tools/git-safety`,
   then `git-safety --version`, `init`, `doctor`.
4. Replace the "prepared, not published" wording in README.md and docs/HOMEBREW.md with
   the live install path.

Environment notes: `origin` is an SSH URL that fails in the sandbox; push with
https://github.com/pocketIlmatto/git-safety.git instead. The pre-commit hook needs
`git-safety` and Gitleaks on PATH (8.29.1-8.30.1; a checksum-verified 8.30.1 arm64 build
was used from the session scratchpad, which may not persist).
