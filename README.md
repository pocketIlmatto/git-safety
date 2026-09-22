# git-safety

`git-safety` is a repository-local privacy and credential scanning toolkit. It
combines a byte-safe privacy scanner with Gitleaks and provides opt-in Git hook
integration. It is designed to run locally and in CI without changing Git
history, fetching objects, or changing global Git configuration.

The toolkit is still being integrated. Treat the exact commit used by a
consumer as the versioned artifact until a release process is established.
Replace `<VERIFIED_COMMIT>` and `<INSTALL_ROOT>` in the examples below with
values chosen by the consuming project; this repository does not publish a
repository URL or release channel.

## Requirements

The supported baseline is:

- Git 2.31 or newer
- Bash 3.2 or newer for the launcher and installer
- Python 3.9 or newer, using only the standard library
- ripgrep 13 or newer
- Gitleaks exactly 8.30.1, the validated baseline

The CLI checks the Gitleaks version and required commands before scanning.
Install dependencies through a trusted, separately reviewed source. Do not
execute an unverified latest-release installer in CI.

## Installation

Consumer installation should use a verified checkout or archive at an exact
commit, outside the repository being scanned. The installer creates one
`git-safety` symlink in the selected bin directory and refuses an existing
non-owned collision. For example:

```sh
git clone <TOOL_SOURCE_URL> <INSTALL_ROOT>
git -C <INSTALL_ROOT> checkout --detach <VERIFIED_COMMIT>
<INSTALL_ROOT>/scripts/install --bin-dir "$HOME/.local/bin"
export PATH="$HOME/.local/bin:$PATH"
git-safety --version
```

The source URL above is intentionally a placeholder. Pin the tool checkout and
the Gitleaks 8.30.1 binary in CI, and verify checksums using the release
process adopted by the consuming project.

Upgrade by installing a new verified checkout with `scripts/install` and then
running `git-safety --version`. Repository policy and opt-in hooks are left in
place. To roll back, point the installation checkout at the previous verified
commit and rerun the installer. To remove the CLI symlink, run:

```sh
<INSTALL_ROOT>/scripts/uninstall --bin-dir "$HOME/.local/bin"
```

Uninstallation removes only the symlink owned by this tool and refuses a
collision or replacement it does not own. Remove repository hooks separately
with `git-safety uninstall-hook`; that command also removes only a byte-for-byte
tool-owned hook.

## Repository setup

Run setup from any directory inside the target Git repository:

```sh
git-safety init
git-safety install-hook
git-safety doctor
```

`init` creates missing files under `.git-safety/`:

```text
.git-safety/privacy-patterns
.git-safety/privacy-allowlist
.git-safety/privacy-patterns.local.example
```

It also adds precise ignores for `privacy-patterns.local` and
`privacy-allowlist.local`. Existing policy, local files, and ignore entries are
preserved. The two local files are for clone-specific rules and are never
public policy. Keep them untracked and do not put credentials or broad
allowlists in public policy.

The pre-commit hook is repository opt-in. It delegates to `git-safety staged`,
does not contain scanner logic, does not set global `core.hooksPath`, and
refuses to replace an existing hook or unsafe hook configuration. Hooks can be
bypassed with `git commit --no-verify`; required CI branch checks are a separate
repository setting.

## Commands and exit status

The default command is `all`:

```text
git-safety [--version] [--help]
git-safety staged
git-safety worktree
git-safety history
git-safety all
git-safety init
git-safety install-hook
git-safety uninstall-hook
git-safety doctor
```

Exit status is consistent across scans: `0` means clean, `1` means findings,
and `2` means setup, dependency, configuration, or incomplete-scan error. The
comprehensive command runs independent components and aggregates them: an error
takes precedence over findings, and findings take precedence over clean
results. A component that did not run is reported as incomplete rather than
being treated as a pass.

`staged` reads added content from the index and runs privacy and Gitleaks
staged checks. It does not substitute the working copy, so partial staging and
an index that differs from the working tree remain meaningful. Gitleaks' native
staged engine and the privacy scanner's forced-text diff parsing have different
Git attribute and binary handling; identical results are not promised.

`worktree` scans tracked and untracked, non-ignored publishable files. Tracked
files remain eligible even if an ignore rule matches them. Symlinks are scanned
as their target strings and are never followed. Gitleaks receives an external
temporary snapshot, which is removed after the scan.

`history` scans privacy blobs and Gitleaks history over all reachable local
refs. The Gitleaks invocation uses:

```text
--all --full-history --root --no-renames --no-ext-diff --no-textconv --text -m
```

It does not fetch missing objects. A shallow repository is incomplete and
returns `2`; fetch the required history separately, then rerun the scan.
Privacy history deduplicates blob contents and reports a representative
commit/path. History excludes unreachable objects, reflogs, commit metadata and
messages, and recursively separate submodules.

`all` runs staged, worktree, and history coverage. `doctor` checks repository
context, dependency visibility, policy readability and syntax, effective hook
configuration, CLI visibility (including the current process PATH used by GUI
clients), and whether local policy files are ignored and untracked. It never
prints local policy contents. If a GUI client has a different PATH, repair that
client's environment and rerun diagnosis; a terminal PATH change cannot verify
the GUI process.

## Privacy policy

Privacy rules are additive in this order:

1. Built-in generic rules for user paths, email addresses, and credential-bearing URLs.
2. Public repository rules in `.git-safety/privacy-patterns`.
3. Ignored local rules in `.git-safety/privacy-patterns.local`.

Allowlist entries are additive in the corresponding public and local files, and
are evaluated against each matched value. A placeholder on a line does not
exempt another private value on that line. Rules and exceptions use
case-insensitive ripgrep-compatible regular expressions; blank and comment
lines are ignored and both files are validated even when no content is found.
Escape literal identifiers as regular expressions require. Keep exceptions
narrow and value-specific.

Privacy policy files themselves have exact path exemptions for the current
`.git-safety/` names and the legacy root-level names. This prevents examples in
policy from self-matching; it is not an exemption for the policy directory or
for secrets. Gitleaks retains its own detection behavior and does not inherit
privacy allowlists or these path exemptions.

Gitleaks configuration follows native environment precedence (`GITLEAKS_CONFIG`
or `GITLEAKS_CONFIG_TOML`), then a root `.gitleaks.toml` when present, then
Gitleaks defaults. `.gitleaksignore` is honored. A local privacy exception can
never suppress a Gitleaks finding.

Findings redact matched values and source lines. Reported filenames and paths
may themselves contain identifying text, so redaction is not anonymization.

## CI and routine workflow

For a routine local check, initialize once, install the hook, and run
`git-safety all` before publishing. In CI, use a full-history checkout with
credentials persisted off, run the pinned toolkit and Gitleaks versions from
temporary storage outside the worktree, and retain separate project tests and
security scans. Run full coverage on pull requests and pushes to the protected
default branch with read-only repository permissions and bounded execution.

The scanner does not enforce branch protection. A successful scan means only
that the configured rules found no unresolved matches in the scanned local
objects and files.

## Safety boundaries and limitations

The tool never rewrites history, rotates credentials, deletes user files,
resets the index, silently untracks private files, or auto-fetches history.
Deleting a current value does not remove it from reachable history; rotate or
revoke exposed credentials through the responsible service and handle history
rewriting as a separately authorized operation.

Local ignored policy is absent in CI and other clones unless provisioned
securely. Hooks are clone-local and bypassable. Policy is read from the current
on-disk checkout, including local rules; a partially staged policy file does
not create a historical or index-specific policy snapshot. Submodules are not
scanned recursively, and content unavailable in a shallow or unfetched history
cannot be audited.

## Development

Run the repository's regression tests with Python's standard test runner. Keep
fixtures synthetic and outside scanned worktrees. Do not claim hosted CI or a
consumer migration unless it was actually run and reviewed.

