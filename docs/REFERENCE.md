# Configuration and coverage reference

Start with the [README](../README.md) for installation and everyday use. This
page describes details that matter when configuring a project or investigating
a finding.

## Scan coverage

Every scan command runs the privacy scanner and Gitleaks. `all` runs `staged`,
`worktree`, and `history`; it is also the default command.

**Staged:** privacy checks inspect added lines in Git's index, which holds the
changes selected for the next commit. Deleting a private line is allowed.
Partial staging works even when the file on disk differs from the staged copy.
Gitleaks uses its native `git --staged` command, which can skip files that Git
marks binary. Privacy scanning forces text, so the engines have different
binary and Git attribute behavior.

**Worktree:** scans tracked files and untracked files that Git doesn't ignore.
Already tracked files remain eligible even if they match an ignore rule.
Symlinks are scanned as their target strings, without reading the destination.
A symlink in a tracked file's parent path produces an incomplete scan. Gitleaks
receives a temporary copy of eligible content outside the repository; that copy
is removed when the scan ends.

**History:** privacy scans unique file contents reachable through all local
Git refs, including other branches and content deleted in later commits. It
reports one representative commit/path for identical content. Gitleaks uses
these explicit Git log options:

```text
--all --full-history --root --no-renames --no-ext-diff --no-textconv --text -m
```

Shallow repositories have incomplete history: `history` returns `2`, and `all`
runs the other modes but returns `2` overall. Partial/promisor clones, which can
fetch missing objects on demand, are refused before scanning. Fetch or make a
full clone separately. Scans never fetch automatically.

Content checks exclude commit author/committer metadata, messages, unreachable
objects, reflogs, and recursive submodule contents. History that hasn't been
fetched is unavailable. Matches and source lines are redacted; filenames are
still shown and can themselves contain private information.

The exit codes are `0` clean, `1` findings, and `2` setup/configuration/dependency
errors or incomplete coverage. Independent checks continue after a finding or
error. An error takes precedence over findings, so incomplete coverage never
produces an overall pass.

## Rules and exceptions

Privacy patterns combine three sources:

1. Built-in macOS home-path, email, and credential-in-URL patterns.
2. Public `.git-safety/privacy-patterns`.
3. Optional ignored `.git-safety/privacy-patterns.local`.

Built-in exceptions allow example-domain email addresses and specific placeholder
home paths. Public `.git-safety/privacy-allowlist` and optional local
`.git-safety/privacy-allowlist.local` add exceptions. They apply to the matched
value, not the whole source line: one allowed placeholder cannot hide a separate
private value on that line. They can allow matches from any privacy rule layer.

Use ripgrep-compatible, case-insensitive regular expressions. Blank lines and
comment lines are ignored. To match the literal `alice+test@example.com`, use
`alice\+test@example\.com`. An exception limited to example domains is
`^[A-Za-z0-9._%+-]+@example\.(com|org|net)$`. Anchoring it with `^` and `$` prevents
a longer address with an extra domain suffix from matching the exception.

Both public files are required. Empty public files retain built-in protection;
missing or unreadable required policy and malformed regexes are errors, even
when no files are staged. Policy files and the policy directory must not be
symlinks. Rules are read from the current files on disk in every mode, including
history. Staging an older version of a rule file doesn't change which rules run.
Local ignored rules and exceptions aren't available in CI or other clones.

To avoid matching regex definitions, privacy content scans exempt exactly:

```text
.git-safety/privacy-patterns
.git-safety/privacy-patterns.local
.git-safety/privacy-patterns.local.example
.git-safety/privacy-allowlist
.git-safety/privacy-allowlist.local
.privacy-patterns
.privacy-patterns.local
.privacy-patterns.local.example
.privacy-allowlist
.privacy-allowlist.local
```

The legacy root-level paths stay exempt when scanning old commits after a
migration. Other files in `.git-safety` aren't exempt. These privacy exemptions
don't exempt files from Gitleaks.

Gitleaks discovers configuration in this order: `GITLEAKS_CONFIG`, then
`GITLEAKS_CONFIG_TOML`, then the project's `.gitleaks.toml`, then built-in defaults.
The project's `.gitleaksignore` is honored. Gitleaks configuration can change
secret coverage; privacy rules and exceptions do not change it.

## Hooks

`install-hook` installs a small pre-commit script that runs `git-safety staged`.
It doesn't change `core.hooksPath` or replace an existing user hook. Repeating
installation is safe for an unchanged tool-owned hook. A missing CLI causes the
hook to fail with an explanation.

Inherited, external, empty, or unsafe hook paths are refused. A configured
directory inside the project can be used safely. Default Git hooks may be shared
by linked worktrees, so installation/removal can affect the other worktrees too.

If you already have a pre-commit hook, review it before adding a call to
`git-safety staged`. Both the existing checks and the new check must run, and a
failure from either must make the hook fail. Don't append after an unconditional
`exit` or `exec`, or change the hooks directory in a way that disconnects other
hook types. This composition is manual; the installer doesn't rewrite user hooks.

`uninstall-hook` removes only a hook whose contents still exactly match the
tool's template. Remove a manually added call manually. Project policy and other
hooks are left in place. `git commit --no-verify` bypasses the hook; branch
protection is a separate repository setting.

`doctor` checks dependencies, policy validity, hook configuration, CLI visibility,
and whether local policy is ignored or already tracked. It never silently
untracks files. Its PATH check describes the process that ran it, not a separate
GUI application's environment.

## Updates and rollback

The current installation is a symlink to a checkout. There is no separate copy
of the program and no automatic update command.

For a dedicated installation checkout, save its current `git rev-parse HEAD`
value, make sure it has no unsaved work, then switch to the tested revision you
want to use. Run `./scripts/check` and `git-safety --version` afterward. To roll
back, switch the same checkout back to the saved revision. The version command
prints the package version, not the commit ID; use Git to identify the exact code.
Avoid switching a checkout where you're actively developing uncommitted changes.

To use a different checkout, run `./scripts/uninstall` from the old one, then
`./scripts/install` from the new one. The installer refuses to replace a symlink
belonging to a different checkout. Both commands accept `--bin-dir` if you used
a location other than `~/.local/bin`; pass the same location when uninstalling.

Upgrades and CLI removal preserve project policy and hooks. Remove project
hooks before removing the CLI entirely, or commits will fail because their
scanner command is missing.
