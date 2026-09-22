# git-safety

This is a Git project for private information and secrets before you commit or
share it. `git-safety` looks for things such as personal file paths and email
addresses, and uses Gitleaks to find credentials such as API keys.

You install the command once, then choose which projects use it. Each project
keeps its own rules. You can run checks yourself or have Git run them before
each commit.

## Installation

For now, install from a local copy of this repository. There isn't a Homebrew
formula or Python package for `git-safety` yet.

### 1. Check the dependencies

Run these commands in Terminal:

```sh
git --version
python3 --version
rg --version
gitleaks version
```

You need Git 2.31+, Python 3.9+, ripgrep 13+, and **Gitleaks 8.30.1 exactly**.
The shell scripts also need Bash 3.2+. If all four commands report the required
versions, continue to step 2.

If anything is missing, follow [dependency setup](docs/DEPENDENCIES.md), then
come back here. The exact Gitleaks version is a current installation limitation:
the tool rejects other versions, even newer ones.

### 2. Install the command

For the current development checkout, run:

```sh
cd ~/Development/dev-tools/git-safety
./scripts/install
```

If you keep the repository somewhere else, open Terminal in that directory and
run `./scripts/install` there instead.

This creates `~/.local/bin/git-safety`, a **symbolic link**—a shortcut—to the
command in this repository. It doesn't copy the program or install dependencies.
Keep this repository in place: moving or deleting it breaks the shortcut, and
editing its code changes the installed command immediately. You don't need
`sudo`.

### 3. Make the command available in Terminal

Run:

```sh
export PATH="$HOME/.local/bin:$PATH"
git-safety --version
```

You should see `git-safety 0.1.0`. `PATH` is the list of directories your shell
searches for commands. The `export` line adds the installation directory for
this terminal session.

To keep it available in new terminals, add this line **once** to `~/.zshrc`:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

Installation is now complete. It hasn't enabled checks in any other project.

## Set up a project

Open Terminal in the Git project you want to check, then run:

```sh
git-safety init
git-safety doctor
git-safety all
```

`init` creates the project's rule files and adds ignore entries for local rules.
It preserves existing files. `doctor` checks the setup and tells you about
missing dependencies or configuration problems. `all` checks staged changes,
current files, and Git history.

Commit the public configuration when you're ready:

```sh
git add .gitignore .git-safety/privacy-patterns .git-safety/privacy-allowlist .git-safety/privacy-patterns.local.example
git commit -m "Add Git safety rules"
```

To run checks automatically before commits, also run:

```sh
git-safety install-hook
```

A **pre-commit hook** is a script Git runs before creating a commit. This one
runs `git-safety staged`. If the project already has a hook, installation stops
and leaves it alone; see [hook setup](docs/REFERENCE.md#hooks) before combining
them. Each developer needs to run git-safety install-hook in their local copy of the project to enable automatic checks before commits.

## Everyday use

| Command | Use it to… |
| --- | --- |
| `git-safety staged` | Check the changes you've selected with `git add`. |
| `git-safety worktree` | Check current files, including new files Git doesn't ignore. |
| `git-safety history` | Check committed content across locally available branches and tags. |
| `git-safety all` | Run all three checks. This is also the default if you omit the command. |
| `git-safety doctor` | Diagnose installation, rule-file, and hook problems. |

With the hook installed, your usual `git add` and `git commit` workflow stays
the same. Run `git-safety all` before sharing the project to include its history.

A finding shows a file location without printing the matched value or source
line. Review that location, remove the private content or add a narrow exception
if it's intentional, and rerun the check. A finding in an old commit stays in
history even after you delete it from today's files. The tool doesn't rewrite
history or rotate credentials.

For scripts and CI, exit code **0** means clean, **1** means findings, and **2**
means a check couldn't finish. Other checks continue where possible; any
incomplete check makes the overall result `2`.

## Add project-specific rules

Built-in rules cover macOS home-directory paths, email addresses, and URLs with
embedded usernames and passwords. Add other information you want to catch to
`.git-safety/privacy-patterns`, one regular expression per line.

For example, a literal identifier containing a dot needs an escaped dot:

```text
internal-project\.example
```

Rules are case-insensitive. Empty lines and lines beginning with `#` in the rule files are ignored.
The built-in rules stay active even if your project rule files are empty.

For rules that should stay on your machine, create the ignored local file:

```sh
cp -n .git-safety/privacy-patterns.local.example .git-safety/privacy-patterns.local
```

Edit that file and run `git-safety doctor` to check it is ignored and untracked.
Local rules aren't present in other clones or CI.

Use `.git-safety/privacy-allowlist` for shared exceptions, or
`.git-safety/privacy-allowlist.local` for exceptions on your machine. Keep them
specific: an exception applies to an individual match, and can allow that value
wherever it appears. Privacy exceptions do not disable Gitleaks detections.
See the [rule reference](docs/REFERENCE.md#rules-and-exceptions) for examples
and Gitleaks configuration.

## Troubleshooting

| Problem | What to do |
| --- | --- |
| `git-safety: command not found` | Run the `export PATH=...` line from installation. Check the repository hasn't moved. |
| Gitleaks version is unsupported | Install exactly 8.30.1 using the [dependency guide](docs/DEPENDENCIES.md). |
| Required policy is missing | Run `git-safety init` inside the project, then `git-safety doctor`. |
| History is shallow | Fetch full history separately, for example with `git fetch --unshallow`, then rerun. The scanner doesn't fetch for you. |
| Terminal works, but a Git GUI fails | The GUI may use a different PATH. Configure it to find the CLI and its dependencies. |
| Hook installation finds an existing hook | Keep it and follow the [hook guidance](docs/REFERENCE.md#hooks). |

Checks can only find what their rules cover. Hooks can be bypassed with
`git commit --no-verify`; required CI checks are configured separately.
Filenames remain visible in reports. Submodules and commit messages aren't
scanned. Gitleaks' staged scan can skip files Git treats as binary. Read the
[coverage reference](docs/REFERENCE.md#scan-coverage) for the full boundaries.

## Update or uninstall

The installed command points to this checkout, so switching this checkout to
another tested commit also switches the installed version. Check `git status`
and save your work before switching versions. There is no automatic updater or
published release channel yet. See [version management](docs/REFERENCE.md#updates-and-rollback)
for the current manual process.

To stop automatic checks in a project, run this inside that project:

```sh
git-safety uninstall-hook
```

To remove the command entirely, remove its hooks from your projects first.
Then, from this toolkit's directory, run:

```sh
./scripts/uninstall
```

This removes the shortcut in `~/.local/bin`. It leaves your project rules and
this repository in place.

## Development and further reading

From this repository, run `./scripts/check` for regression tests and
`./bin/git-safety all` for security scans. Tests use temporary repositories and
synthetic data.

- [Validation results](VALIDATION.md), including what hasn't been tested
- [CI setup](docs/CI.md)
- [Migration from existing scanners](docs/MIGRATION.md)
- [Installation options we're considering](docs/INSTALLATION_OPTIONS.md)
