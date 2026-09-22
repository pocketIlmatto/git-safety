# Standalone git-safety implementation plan

## Scope and decisions

Build and validate this repository only. Treat `~/.hammerspoon` as a read-only
reference; its application and migration are outside this phase. Never copy local
private policy values, push, publish, rewrite history, or change remote settings.

Use a Python 3 standard-library package with a small Bash 3.2-compatible launcher,
ripgrep regex matching, and Gitleaks 8.30.1 as the validated secrets baseline.
Expose staged, worktree, history, all (default), init, install-hook,
uninstall-hook, and doctor commands. Scans aggregate independent components;
errors (2) take precedence over findings (1), then clean (0).

Keep current on-disk policy semantics, with additive built-in/public/local rules
and match-level privacy exceptions. Require initialized public policy files.
Keep exact legacy and new privacy policy exemptions, never secrets exemptions.
Scan symlink target strings without following destinations. History covers all
reachable local refs; shallow history produces an incomplete result.

Use conservative hook ownership: install only into a safe repository-owned hook
location, leave other hooks/configuration intact, refuse conflicts, and remove
only byte-for-byte tool-owned integration. Do not change global configuration.

## Checkpoints

1. **Plan and baseline.** Commit this plan and supplied handover. Run the source's
   disposable privacy regressions without writes to its checkout; record baseline
   versions and subsequent source changes. Inspect supported Gitleaks commands.
2. **Implementation (parallel independent workstreams).** Commit each completed
   logical stream after its own relevant tests, staging only its owned files.
   - Privacy/policy: port the hardened scanner and original 20 regressions;
     extend policy, path, history, and failure coverage.
   - Repository setup: implement non-destructive initialization, hook lifecycle,
     and repository/policy diagnosis with disposable-repository tests.
   - Coordinator: implement shared utilities, CLI/installation, Gitleaks coverage,
     redacted diagnostics, and real-binary and mocked integration tests.
   Streams may execute concurrently; do not begin a subsequent checkpoint until
   all completed streams are committed. Changes to the plan are committed first.
3. **Integration, documentation, CI, and parity.** Integrate interfaces, resolve
   findings, run meaningful combined tests and source comparison checks, and
   commit each completed correction. Add precise usage/coverage/lifecycle docs,
   pinned full-scan CI, and a deferred migration guide. Validate locally; do not
   claim a hosted CI run or Linux execution unless actually observed.
4. **Final verification.** Scan this tool, review implementation and history,
   record test results, limitations, and checkpoint commits. Verify intended
   changes are committed and the reference checkout was not changed by this task.

## Acceptance and validation

Preserve original scanner regressions, including the macOS non-UTF-8 filename
skip. Add tests for required and partially staged policy, tracked ignored files,
deduplicated history, initial/nested/linked repositories, shallow history, hook
conflicts/idempotence/uninstall, dependency/configuration failures, and redaction.
Use synthetic credentials with real Gitleaks to independently verify staged
index isolation, all-ref history, symlink handling, and all-mode aggregation.
Distinguish mock tests from real integrations in the validation report.

Installer artifacts and disposable fixtures belong outside scanned worktrees.
Runtime scans and doctor require no network and must not mutate repository state.

## Completion

All four standalone checkpoints are complete. The final suite ran 85 cases
(84 passed, one expected macOS skip), the optional reference harness passed 36
comparisons, and full toolkit self-scans and current-PATH doctor checks passed.
See `VALIDATION.md` for evidence, architecture decisions, commit checkpoints,
known engine differences, and compatibility limits. Linux/hosted CI execution
and the separate Hammerspoon migration have not been performed.

## README and installation guidance follow-up

Rewrite the README for junior and mid-level engineers, starting with the existing
local-checkout installation and explaining PATH, the symlink, dependencies, and
per-project setup. Preserve exact scan/policy details in a linked reference page.
Add a comparison of standard installation patterns with user effort, maintenance,
security, and cost tradeoffs, clearly separating proposals from implemented UX.
This follow-up changes documentation only; it does not install tools, change
shell settings, introduce packaging, or migrate Hammerspoon. Validate links,
documented commands against the installer, and scanner results before committing
the completed documentation change.

Completed: README rewritten; dependency setup, coverage reference, and seven-option
installation comparison added. Relative links and all 14 shell examples passed
checks; temporary install/reinstall/version/uninstall and full self-scans passed.
No runtime or installer code changed, and no user installation was performed.
