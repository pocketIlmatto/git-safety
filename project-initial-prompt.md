# Handover: extract a reusable Git privacy and security toolkit

I want to extract the privacy/security checks and their Git workflow integration
from my `~/.hammerspoon` repository into a separate reusable personal tool,
tentatively named `git-safety`. Build the tool in its own repository, then migrate
Hammerspoon only after parity is demonstrated. Do not merely copy scripts into
each consuming repository.

This prompt was reconciled against Hammerspoon commit `fa12f28` on September 21,
2026. Inspect the source repository and subsequent changes before implementing;
the source and tests are authoritative evidence of existing behavior. Distinguish
verified behavior, known limitations, and proposed improvements. Do not treat
this handover as evidence that the new tool has already been built or tested.

## Scope and extraction boundary

Extract the reusable privacy scanner, Gitleaks integration, scan orchestration,
policy loading, hook installation and diagnosis, scanner regression tests, and
security-related CI guidance. Include installation, upgrades, uninstallation,
and a safe migration path for existing repositories.

Keep Hammerspoon application behavior, Lua configuration validation, private
configuration, Bear integration, window/Spaces movement, Lua tests, and the
Drag.spoon submodule in Hammerspoon. Its project test runner should continue to
run its own checks. A reusable toolkit must not depend on Hammerspoon or Lua.
Bear URL rules are repository policy, not application integration to extract.

Do not move private values into the new repository, fixtures, documentation,
logs, or public policy. Preserve ignored local policy locally during migration.
Do not push, publish, rewrite history, or change remote branch protection as part
of this work without explicit authorization.

## Inspect this implementation first

- `scripts/privacy-check`: Bash entry point resolving the Git root and requiring
  Python 3; delegates to `scripts/privacy_check.py`.
- `scripts/privacy_check.py`: privacy scanner using Python's standard library
  for Git orchestration, byte-safe parsing, temporary files, and ripgrep JSON
  results. Ripgrep remains the regex engine.
- `scripts/secret-check`: Gitleaks staged, worktree, history, and all modes.
- `scripts/security-check`: combined privacy/secret entry point; currently accepts
  staged, worktree, and all modes, but not history by itself.
- `.githooks/pre-commit`: delegates to combined staged scanning.
- `.privacy-patterns`, `.privacy-allowlist`, `.privacy-patterns.local.example`,
  ignored `.privacy-patterns.local` and `.privacy-allowlist.local`, and `.gitignore`.
- `tests/test_privacy.py`: disposable-repository regressions to carry forward.
- `scripts/check`, `.github/workflows/checks.yml`, and README security/setup
  sections: test separation, CI, dependency requirements, and coverage limits.
- `IMPLEMENTATION_PLAN.md` and relevant Git history: completed scanner hardening
  and CI changes. Historical workstream instructions are context, not a request
  to repeat unrelated application work or to delegate this extraction.

Relevant changes include `25a4489` (privacy hardening/history), `130080c` (tests
and CI), `79cf97c` (coverage documentation), `488afd8` (Ubuntu CI), and `7c997e3`
(installer artifacts outside the scanned worktree).

### Existing guarantees to preserve

- Staged privacy checks inspect added lines from the index, not the working copy.
  Removing a sensitive line is permitted. Partial staging works in both
  directions, including a sensitive index with a clean working copy.
- Diff parsing handles added content beginning with `++`, unusual filenames,
  literal pathspecs, and NUL-delimited inventories. External diff/text conversion
  and attributes must not hide content from privacy scanning.
- Worktree privacy scanning covers tracked plus untracked, non-ignored files.
  Already-tracked files remain eligible even when an ignore rule matches them.
  A symlink's target string is scanned without following its destination.
- Privacy history scanning already exists and is required: it scans unique blob
  contents reachable through `git rev-list --all`, using current policy, including
  other branches and content deleted in later commits. It reports a representative
  commit/path location for a blob, not every occurrence.
- Privacy `--all` covers staged additions, publishable worktree content, and
  reachable history. Do not regress it to worktree plus history only.
- Exceptions are evaluated against each detected value, never the complete
  source line. A safe placeholder must not exempt a separate private value on
  that line. Shared exceptions are narrowly anchored to prevent suffix bypasses.
- Regex rules are ripgrep-compatible and case-insensitive; blank/comment lines
  are ignored. Both rules and exceptions are validated even for an empty scan.
  `rg --no-config` prevents ambient ripgrep configuration from changing behavior.
- Binary/non-UTF-8 content is scanned as bytes/text, not silently excluded.
- Privacy findings report escaped locations and redact matched values and source
  lines. Scanner failures suppress raw subprocess output that could reveal them.
  Gitleaks invocations use redaction.
- Privacy scanner outcomes distinguish success (0), findings (1), and incomplete
  scans/configuration/dependency errors (2). Preserve fail-closed error handling.

### Existing differences and limits to address explicitly

Do not claim that the existing scanners have identical coverage:

- Secret `--all` currently runs worktree and history, without a separate staged
  pass. Gitleaks history currently uses its default Git scope, with no explicit
  all-refs option. Verify that scope against the supported Gitleaks version before
  claiming equivalence to privacy history.
- Secret worktree scanning currently calls Gitleaks per regular file and does not
  implement the privacy scanner's explicit symlink handling. Define and test the
  replacement's behavior; do not accidentally read ignored symlink destinations.
- Privacy currently skips its explicitly named policy/template files in all
  content modes; Gitleaks does not share those exemptions. Do not turn these into
  a blanket exemption of the entire policy directory or of secrets in policy.
- Privacy currently reads current on-disk policy, including local rules, rather
  than policy from each historical commit or necessarily the staged policy.
  Document and test the chosen semantics when policy itself is partially staged.
- Empty privacy policy currently reports no configured rules and succeeds.
  Define how built-in rules and missing required public policy change this;
  malformed or unexpectedly unreadable required policy must not silently pass.
- Privacy content scanning excludes commit author/committer metadata, messages,
  unreachable objects, and reflogs. Submodules are not scanned recursively.
  History that has not been fetched cannot be scanned.
- Redacting matched values does not anonymize filenames: reported locations may
  themselves contain identifying text. Document that limit without printing
  private content in diagnostics or tests.
- Local ignored policies are absent in CI and other clones. Hooks are clone-local
  opt-in and bypassable; a passing scan only means configured rules found no
  unresolved matches. Deleting current content does not erase historical content.

## Architecture and policy

Install one reusable CLI on PATH, for example `~/.local/bin/git-safety`. Keep only
repository policy and minimal hook/CI integration in consuming repositories:

```text
project/
├── .git-safety/
│   ├── privacy-patterns
│   ├── privacy-allowlist
│   ├── privacy-patterns.local.example
│   ├── privacy-patterns.local       # ignored
│   └── privacy-allowlist.local      # ignored
├── .gitignore
└── ...
```

Support three clearly documented rule layers: built-in generic defaults,
repository public rules, and ignored repository-local rules. Define combination
and exception behavior explicitly; local privacy exceptions must not implicitly
disable Gitleaks detections. Keep generic path/email/credential-bearing-URL
protections reusable and Hammerspoon-specific identifiers in its policy.

Gitleaks remains responsible for tokens, API keys, passwords, private keys, and
cloud credentials. Preserve any existing repository Gitleaks configuration and
define how it is discovered; do not invent a second secrets engine.

Keep ripgrep regex compatibility and match-level exceptions. Examples should be
safe placeholders. Explain escaping literal identifiers and the consequences of
broad exceptions. Do not copy actual local identifiers into public templates.

Resolve the root through Git so commands work from nested directories and linked
worktrees. Do not assume `.git` is a directory or modify global Git settings.

## CLI contract

Keep the interface simple. These names are preferred unless a material reason
justifies a change:

| Command | Required behavior |
| --- | --- |
| `git-safety staged` | Scan added index content for privacy and staged secrets with Gitleaks. Never substitute the working copy for the index. |
| `git-safety worktree` | Scan tracked and untracked, non-ignored publishable files with both engines. Preserve tracked-file and symlink semantics described above. |
| `git-safety history` | Scan privacy blobs and secrets across all reachable local refs. Verify/configure Gitleaks to achieve the intended scope, or explicitly report a limitation instead of silently narrowing it. |
| `git-safety all` | Run staged, worktree, and history coverage for both engines. Keep full coverage as the default comprehensive check. |
| `git-safety init` | Create missing public policy/templates and precise local-file ignore entries without overwriting existing policy, local files, or ignore rules. Repeated execution is safe. |
| `git-safety install-hook` | Install a minimal repo-local pre-commit integration delegating to `git-safety staged`; safely account for existing hooks and hook configuration. |
| `git-safety doctor` | Diagnose repository context, dependencies/compatibility, effective hook configuration, CLI visibility to Git, readable/valid policy, and ignored/untracked local policy. |

Use consistent exit codes: 0 clean, 1 findings, 2 setup/configuration/incomplete
scan errors. Normalize Gitleaks failures appropriately rather than treating every
nonzero status as a finding. Clearly identify coverage that did not run; never
print an overall pass after a failed or incomplete component. Decide whether to
aggregate independent findings or stop early, and document it.

For comprehensive scans, diagnose shallow history and explain how to fetch what
is required. Never silently describe a shallow or otherwise incomplete scan as a
complete publication audit. Do not auto-fetch or change repository state during
read-only scan commands.

`doctor` should check both ignore status and whether a supposedly private local
file is already tracked. It must not print that file's contents. Missing binaries
or unsupported Gitleaks commands should produce actionable installation/version
guidance. No network access should be required for ordinary scans or diagnosis.

## Hook and Git safety

Prefer explicit per-repository opt-in. Do not set a global `core.hooksPath`.
Inspect the effective local/global hook configuration, existing hook files, and
linked-worktree behavior before installing. Do not silently replace hooks or
disconnect other hook types by changing `core.hooksPath`. Compose only when safe
and testable; otherwise explain the conflict and preserve the existing setup.

The hook should contain no scanner logic, essentially delegating via
`exec git-safety staged`. A missing CLI must fail clearly, including in GUI Git
clients with a different PATH. Make installation idempotent and uninstallation
remove only tool-owned integration, restoring configuration safely where needed.

Do not delete user files, discard changes, reset the index, rewrite history,
overwrite security policy, or silently untrack private files. Handle unusual
filenames with byte-safe/NUL-delimited Git operations and literal pathspecs.
Keep temporary files and installer artifacts outside the scanned repository and
clean up tool-owned temporary resources on success and failure.

## Dependencies, installation, and upgrades

Primary local target: macOS with zsh as the interactive shell and Homebrew
available. Support Linux CI, including Ubuntu 24.04. Bash scripts are acceptable;
declare and test the minimum Bash version rather than assuming a new system Bash
on macOS.

The current proven stack is Git, Bash, Python 3 standard library, ripgrep, and
Gitleaks. Python is already part of the hardened implementation; retain it unless
there is a strong, parity-tested reason to replace it. Avoid additional runtime
dependencies. Lua belongs only to Hammerspoon's own checks.

Provide a straightforward install mechanism such as a CLI symlink or installer,
with clear install location, dependency setup, supported versions, upgrade to a
release, rollback, and uninstall instructions. Installation/upgrades must preserve
repository policy and opt-in hooks. Homebrew packaging is optional later.
Gitleaks 8.30.1 is the source project's validated baseline, not a requirement to
assume it remains the newest release; verify supported commands/version behavior.

## CI and development workflow

Preserve the source project's security properties during migration:

- Pull-request checks and pushes to `main`, with superseded runs canceled for the
  same workflow and branch/PR; read-only repository permissions and a bounded job.
- Full-history checkout (`fetch-depth: 0`) and `persist-credentials: false`.
- Full scans, including privacy history; do not replace them with diff-only or
  changed-file-only scans as an efficiency shortcut.
- Pinned checkout action and a pinned Gitleaks release with verified SHA-256.
  Pin the installed toolkit version too; do not rely on an unversioned latest
  download or execute an unverified installer fetched at runtime.
- Dependency downloads/extraction under runner temporary storage, outside the
  publishable worktree, so scanners do not inspect the installer or release
  archive as untracked repository content.
- Separate project regression tests from security scans. Hammerspoon retains its
  own `scripts/check` and Lua dependencies; toolkit CI runs toolkit regressions.
- Explain that hooks can be bypassed with `git commit --no-verify`; a required
  branch check is a separate repository setting, not something this CLI enforces.

Provide minimal CI setup guidance for other consuming repositories. Do not ship
private local policies to CI. Verify local commands and workflow structure, and
distinguish those checks from actually observing a successful hosted run.

Use Git commits as persistent checkpoints. Inspect status/history in each affected
repository, commit a concrete implementation plan before implementation, and
commit every completed logical/numbered subtask after relevant checks. Do not
start the next planned subtask with the preceding subtask uncommitted. Do not
amend existing commits. Keep unrelated user changes intact and verify all
intended changes are committed at completion.

## Tests and acceptance criteria

Port the existing disposable-repository privacy suite, preserving its byte-safe
fixtures and redaction assertions. Do not replace it with only happy-path tests.
It currently defines 20 cases, with the invalid-UTF-8 filename case skipped on
macOS. Keep that platform-specific distinction visible in results.

Preserve and extend coverage for:

- Bear-style note links and local identifier rules; safe placeholder exceptions.
- Multiple findings on one line, multiple findings of one rule, and placeholder
  suffix bypass attempts; one allowed value cannot hide another finding.
- Staged deletions, partial staging in both directions, and added `++` content.
- Spaces, quotes, tabs, newlines, leading dashes, glob characters, backslashes,
  Unicode filenames, and non-UTF-8 filenames where the filesystem permits them.
- Binary/non-UTF-8 contents, diff attributes, and ambient ripgrep configuration.
- Ignored files, eligible untracked files, tracked files matching ignore rules,
  symlink target strings, and not following symlinks into private destinations.
- Removed historical content, non-current refs, deduplicated blobs, and detection
  of incomplete/shallow history. Verify Gitleaks history scope independently.
- Invalid rules/allowlists even with no staged content; missing/unreadable required
  policy and missing dependencies; subprocess errors must fail closed and redact.
- Policy-file exemptions that do not accidentally exempt unrelated files or
  actual secrets, plus explicit behavior for partially staged policy edits.
- A clean repository, initial/unborn repositories, nested invocation, and linked
  worktrees; existing hooks/configuration; repeatable init/install/uninstall.
- A synthetic credential detected by the supported real Gitleaks binary, staged
  secrets hidden by a clean working copy, and redacted secret diagnostics.
- Migration parity between old and new implementations, plus documented tests
  for intentional improvements over the source's known gaps.

Generate private-looking fixtures in disposable repositories; never use real
credentials or identifying values. Do not broadly weaken production policy to
make test fixtures pass. Keep scanner tests independent of live applications and
network services. Distinguish mocked command tests from real Gitleaks integration
checks in the validation report.

## Migration and documentation deliverables

First establish a baseline in Hammerspoon, then build and validate the standalone
tool. Before removing or replacing any source scanner, demonstrate parity with
the existing regressions and representative staged/worktree/history scans.
Document expected differences caused by deliberately broader coverage.

Migrate public policy to the chosen repository layout without losing its Bear
URL/user-identification protections. Preserve local rule/allowlist contents only
in ignored local destinations; establish ignore protection before moving them.
Maintain privacy exemptions for the old policy paths during history scanning, as
well as narrowly scoped new paths, so migration does not start flagging the
historical regex definitions themselves. Do not exempt their secrets from Gitleaks.

Update Hammerspoon's hook, CI invocation, README, and test references. Keep its
application tests working, and move scanner tests into the toolkit once their
replacement coverage is established. Remove obsolete repo-local scanner logic
only after checks pass, with a clear rollback path through normal Git commits.
Do not edit the private Lua configuration or application code for this extraction.

Deliver a README covering installation/dependencies, initialization, normal Git
workflow, each scan's exact coverage, rule layers, exceptions, local-policy/CI
differences, safe hook composition and removal, bypass behavior, failures,
upgrades/rollback, and limitations. Explain that historical findings require
separate remediation decisions; this tool neither rotates credentials nor rewrites
history. Metadata scanning or other added modes can be proposed separately without
blocking this extraction or silently expanding its default scope.

At completion, report architecture decisions, validation results and limitations,
migration status, and checkpoints in both repositories. Identify any requested
work still outstanding accurately; do not claim CI ran remotely unless observed.
