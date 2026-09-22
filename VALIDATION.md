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
Help inspection is not proof of scan coverage; integration tests will establish
the chosen staged, worktree, and history behavior.

Standalone implementation, parity checks, and hosted CI are not yet validated.
