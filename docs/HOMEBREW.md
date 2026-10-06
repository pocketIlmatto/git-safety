# Installing with Homebrew

**Status: prepared, not published.** The formula, wrapper and release tooling exist
in this repository, but no tag, release archive or tap has been published, so
`brew install pocketIlmatto/tools/git-safety` does not work yet. Until it does, use the
[source-checkout installation](../README.md#installation). Release steps are in
[RELEASING.md](RELEASING.md).

## Install (once published)

```sh
brew install pocketIlmatto/tools/git-safety
git-safety --version
```

Homebrew installs Git, ripgrep, Gitleaks and Python 3.14 as dependencies, then
`git-safety` at `$(brew --prefix)/bin/git-safety`. Installing changes no project,
enables no hook and edits no shell startup file. In each project run
`git-safety init` and, optionally, `git-safety install-hook`.

macOS is the supported platform. Linuxbrew and other Mac architectures aren't validated.

## What the command does

The installed command is a small wrapper. It runs the installed package with Homebrew's
Python, puts the formula's Git, ripgrep and Gitleaks first on `PATH` (keeping the rest
of your `PATH`), writes no bytecode and never imports code from the project being
scanned. It keeps your working directory, arguments, exit code and Gitleaks
configuration variables.

Gitleaks comes from Homebrew's maintained formula. The package accepts stable
**8.29.1–8.30.1** only, checked when the formula installs and again each run. If a
later `brew upgrade gitleaks` goes beyond that range, `git-safety` exits with code 2
and says so; it never falls back to another binary. Upgrade the toolkit once support is
added ([policy](GITLEAKS_COMPATIBILITY.md)). Otherwise return to the source installation
and its [pinned fallback](DEPENDENCIES.md), because the first release has no
dependency-override setting.

## Moving from the source installation

1. Install the formula and test it by explicit path: `"$(brew --prefix)/bin/git-safety" --version`.
2. Run `type -a git-safety`. A `~/.local/bin/git-safety` symlink listed first wins over Brew.
3. Remove the old shortcut from its checkout with `./scripts/uninstall`. Nothing is deleted
   automatically, and your checkout stays.
4. Confirm `command -v git-safety` is the Brew path, then run `git-safety doctor` in a project.

Existing hooks keep working: they only call `git-safety` from `PATH`. Project rules and Git
configuration are not touched by install, upgrade or removal.

## Update, remove, roll back

- Update: `brew update && brew upgrade git-safety`.
- Remove: run `git-safety uninstall-hook` in each project first if retiring the tool, then
  `brew uninstall git-safety`. Left-over hooks fail with "command not found" (exit 2)
  rather than passing silently. Policy files remain.
- Roll back: install a tested toolkit and compatible Gitleaks together, or return to the
  source installation. Homebrew may have removed old versions during cleanup, and `brew`
  has no promised rollback command. Then check `command -v git-safety` and your hooks.

## GUI Git clients

A GUI must find the top-level `$(brew --prefix)/bin/git-safety` on its own `PATH`. The
wrapper fixes dependency selection, not an environment that never reaches it.

## Testing this packaging

`python3 -B -m unittest tests.test_release tests.test_packaging` runs without Homebrew.
`scripts/homebrew-lifecycle.py` runs install, reinstall, upgrade, uninstall and restore against
local candidate archives; set `GIT_SAFETY_DISPOSABLE_BREW=1` only on a disposable Homebrew such as
the CI runner (`.github/workflows/homebrew.yml`), because it replaces any installed `git-safety`.
