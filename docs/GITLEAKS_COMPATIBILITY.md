# Gitleaks compatibility

Supported range: **8.29.1 through 8.30.1 inclusive**, stable releases. Install
the maintained formula with `brew install gitleaks`; no separate versioned
Gitleaks formula is required. Homebrew's
[formula metadata](https://formulae.brew.sh/api/formula/gitleaks.json) reported
8.30.1 on September 22, 2026. This is a dependency choice for local installation;
the toolkit's own Homebrew tap is still a separate next step.

## Evidence and testing cost

Each published version in this small range passed the same 34 tests on macOS:

| Version | Source | Result |
| --- | --- | --- |
| 8.29.1 | Official Apple Silicon release, checksum verified | 34 passed |
| 8.30.0 | Official Apple Silicon release, checksum verified | 34 passed |
| 8.30.1 | Existing local/Homebrew installation | 34 passed |

The tests include 17 real-binary adapter cases and ten CLI/lifecycle cases,
plus seven mocked failure, version-boundary, and aggregation cases. They cover
index/worktree differences, removed and non-current-ref history, symlinks,
custom configuration, redacted diagnostics, malformed reports, and hook behavior.
The three runs took about 9, 30, and 30 seconds individually, with older-version
runs overlapping. Binaries were downloaded to temporary directories; the
installed scanner and user PATH were not changed.

We reviewed the official release notes for
[8.29.1](https://github.com/gitleaks/gitleaks/releases/tag/v8.29.1),
[8.30.0](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.0), and
[8.30.1](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1).
The notes include rule/decoding changes and build/report-template changes.
Tests establish compatibility with this adapter, not identical detection of
every possible secret across versions. In particular, newly added detector
rules or decoding changes can change findings without breaking the CLI contract.

CI checks the two endpoints with pinned, checksum-verified Linux binaries.
The newest version runs the whole toolkit suite; the oldest runs the focused
adapter/CLI suites. Both jobs run full staged/worktree/history security scans.
The middle version was tested locally; it doesn't add a third ongoing CI job.
The new Linux matrix has been syntax-checked, but has not run on hosted CI yet.
If branch rules previously required a single `checks` result, review them after
the first hosted run: the jobs are now named `checks (Gitleaks 8.29.1)` and
`checks (Gitleaks 8.30.1)`. This change does not update branch protection itself.

## Failure modes and tradeoffs

- **Homebrew upgrades outside the range:** scans return `2` and identify the
  supported range. Hooks block commits until a supported version is selected.
  Update the toolkit when support is available, or use the documented pinned
  fallback. We do not automatically downgrade or alter the installed scanner.
- **Prerelease, HEAD, or vendor version strings:** rejected. Numeric stable
  versions with an optional `v` prefix are accepted only inside the range.
  Required command flags are checked too. A version string alone is not proof
  that a custom build behaves like an official release.
- **Changed detections or project configuration:** findings may differ by
  release. A config requiring a newer scanner can fail; invalid configuration
  remains an incomplete scan. Privacy exceptions never suppress Gitleaks.
- **Operational failure versus findings:** Gitleaks uses a distinct findings
  exit code and a validated JSON report. Other failures return `2`; raw scanner
  diagnostics are suppressed to avoid exposing private content.
- **Multiple installations:** a manual binary earlier in PATH may hide the
  Homebrew binary. Check `command -v gitleaks` and `gitleaks version`, including
  the environment used by a GUI Git client.
- **Security updates:** a closed range trades availability after upgrades for
  bounded compatibility. It can delay adopting a security fix, so reviewing a
  new release remains maintenance work. A passing test suite isn't a scanner
  security audit and doesn't justify keeping a vulnerable release indefinitely.

## Expanding support cheaply

Review a candidate's release notes, then run the existing focused suite with
its verified binary first on PATH:

```sh
python3 -B -m unittest tests.test_secrets tests.test_cli -v
```

For a patch with no relevant interface changes, testing that candidate plus the
retained minimum is usually sufficient; that is a maintenance judgment, not a
promise based only on version numbering. Add targeted cases if release changes
affect Git diff handling, JSON reports, exit codes, redaction, config discovery,
or decoding. Major versions require a separate compatibility review.

After passing, update the range, pinned CI version/checksum, and this evidence.
Keep local Homebrew installation convenient while keeping CI reproducible.
This avoids retesting every historical version or maintaining our own Gitleaks
builds; the recurring cost is a release review, a short focused test run, and
two CI jobs. Existing binary/attribute limitations still apply; see
[scan coverage](REFERENCE.md#scan-coverage).
