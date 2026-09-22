# Validation record

## Read-only reference baseline

On September 21, 2026, the Hammerspoon reference was clean at `fb32b24`.
It advanced externally from `ee7d821` between initial inspection and baseline:
the additional commit reverted the handover documentation. No scanner, test,
hook, policy, or CI changes exist between the specified `fa12f28` baseline and
this revision. This task has made no changes or commits in that repository.

Running its original `tests/test_privacy.py` with bytecode writing disabled
completed all 20 cases: 19 passed and the non-UTF-8 filename case was skipped on
macOS, as expected. Fixtures were confined to temporary disposable repositories.

Local tools: Python 3.14.7, ripgrep 15.2.0, Gitleaks 8.30.1, Apple Git 2.50.1,
and system Bash 3.2.57. Gitleaks help confirms `git --staged`, `git --log-opts`,
`dir`, `stdin`, redaction, a configurable findings exit code, and JSON reports.
The integration tests below establish the selected coverage independently of
the help text.

## Standalone results

Final local regression run: `/bin/bash scripts/check` ran **85 tests**, with
**84 passing and one expected macOS non-UTF-8 filename skip**. This includes:

| Suite | Cases | Evidence |
| --- | ---: | --- |
| Privacy and policy | 36 | Original 20 case names retained; 35 pass, one platform skip; partial policy staging, deduplication, symlink boundaries, shallow history, unmerged index, and errors extended |
| Gitleaks adapter | 20 | 17 real Gitleaks 8.30.1 integrations plus three explicitly mocked failure/report tests |
| CLI and installer | 12 | Ten end-to-end cases and two mocked aggregation cases; includes real hook rejection/acceptance and missing CLI diagnosis |
| Repository setup | 15 | Disposable repositories for hook ownership/conflicts, ignore negations, linked worktrees, executable bits, and fail-closed configuration handling |
| Parity harness | 2 | Public-input boundary and synthetic redaction checks |

Permission/read errors and subprocess failures have explicitly mocked tests;
these are not represented as real filesystem permission or missing-binary
integration runs. Real Gitleaks tests use assembled synthetic credentials,
repository-specific Gitleaks configuration, ignored/tracked files, policy-file
secrets, symlink target strings, removed history, and non-current branches.

`scripts/compare-reference.py --source <reference-checkout>` additionally ran
**36 successful comparisons**: nine synthetic scenarios across staged,
worktree, history, and all. It copied only the two public privacy scanner files
and two public policy files into disposable repositories. Both implementations
agreed on exit codes; redaction assertions passed. It did not copy local policy,
scan the live reference's private configuration, or modify its checkout.

`./bin/git-safety all` passed all six engine/coverage combinations against this
toolkit, including its reachable commit history. `git-safety doctor` passed with
this checkout's `bin` directory added to the current process PATH. No permanent
CLI installation or opt-in hook was added to the user's repositories; installer
and hook lifecycle checks used disposable directories.

The toolkit's exact public exception for the synthetic Git identity in early
setup-test commits is documented in `.git-safety/privacy-allowlist`. Current
tests use the normal safe example-domain placeholder. No test-directory or
broad new built-in exemption was added, and no history was rewritten.

## Architecture and deliberate differences

- Python standard-library modules separate policy/privacy, Gitleaks, repository
  setup, and CLI orchestration. Bash 3.2 launch/install scripts support a single
  reusable checkout and CLI symlink; consumers retain only policy/integration.
- Built-in/public/local privacy rules and exceptions combine additively; current
  on-disk policy applies in every mode. Missing required public policy is an
  error; empty public files keep built-in protection.
- Independent scans continue after findings/errors. The overall result is 2
  for incomplete coverage, otherwise 1 for findings, otherwise 0.
- New secret `all` explicitly includes staged coverage. Source Gitleaks 8.30.1
  already defaults to all refs: this was verified in the
  [versioned Git source](https://github.com/gitleaks/gitleaks/blob/v8.30.1/sources/git.go).
  The new invocation makes all refs explicit, forces text for history, disables
  external diff/textconv, and includes root and merge-parent diffs. A real test
  independently detects removed secrets on a non-current branch.
- Worktree secrets are scanned from an external temporary snapshot containing
  only Git-eligible files, including tracked ignored files and symlink target
  strings. Root Gitleaks configuration and ignore settings are preserved.
- Hook installation never changes `core.hooksPath`. Existing/conflicting or
  unsafe hooks are preserved. Git's default common hook directory can be shared
  across linked worktrees; configured checkout-owned directories stay separate.
- Shallow history reports incomplete coverage; partial/promisor configurations
  are refused before object scanning to avoid automatic network fetches.

## CI and compatibility evidence

The Ubuntu 24.04 workflow has pull-request/main triggers, cancellation,
read-only permissions, a bounded job, full-history credential-free checkout,
separate regressions/full scans, and dependency artifacts in runner temporary
storage. Local YAML structure and embedded Bash syntax checks passed.

The checkout action revision was independently verified using the official
`v7.0.1` tag. The pinned Linux x64 Gitleaks SHA-256 was verified against the
[official 8.30.1 checksum file](https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_checksums.txt).
Consumer CI guidance pins the toolkit itself to a reviewed full commit SHA.

Python 3.9 grammar checks passed for all 15 Python source/test files. The actual
runtime was Python 3.14.7; minimum-version runtime testing has not been performed.
The system Bash 3.2 ran the regression script successfully. No Linux container
run occurred because the local Docker daemon was unavailable. **No hosted
GitHub Actions run was triggered or observed.**

## Remaining limits and migration status

Gitleaks' native staged engine can skip content Git marks binary; a dedicated
regression records that limit. Worktree and forced-text history are separate
coverage, and the two engines must not be described as identical. Metadata,
messages, reflogs, unreachable objects, unfetched history, and recursive
submodule contents remain outside the documented content audit. Filenames and
paths remain visible even when matches/source lines are redacted. GUI client
PATH must be checked in that client's own environment.

Hammerspoon remains clean at `fb32b24`; no source scanner, public/local policy,
hook, CI file, application file, or commit there was changed by this task.
Migration is deliberately deferred. A later migration should validate the
consumer's actual public/local policy and content before replacing its scanners.
No push, publication, history rewrite, or remote settings change was performed.

## Persistent checkpoints

Key commits in this repository (additional corrective checkpoints are in Git):

| Commit | Completed work |
| --- | --- |
| `cd1730e` | Concrete plan and supplied handover |
| `59f2566` | Read-only reference baseline |
| `af7f8ad` | Privacy/policy extraction |
| `4d0ea6a` | Repository setup and hook lifecycle |
| `79ba556` | Gitleaks integration and real-binary tests |
| `b9bf671` | CLI, installation, and end-to-end integration |
| `3851f60` | Disposable reference parity harness |
| `3aeb60a` | Extended policy/error acceptance tests |
| `dcb87d8` | Pinned CI and toolkit public policy |
| `ec4c4ed` | Fail-closed hook configuration checks |
| `376c58d` | Installed hook enforcement through real commits |

The final documentation checkpoint records these results. There are no task
commits in Hammerspoon.
