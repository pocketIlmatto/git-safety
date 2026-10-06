# Homebrew tap implementation plan

Status: checkpoints 1, 2 and 4 are implemented locally; checkpoint 3's lifecycle test
is written but has not been run; checkpoint 5 (publication) has not started. See
[HOMEBREW.md](HOMEBREW.md), [RELEASING.md](RELEASING.md) and the evidence notes in
[NEXT_STEPS.md](../NEXT_STEPS.md). Hammerspoon migration stays separate.

## Intended experience

Proposed public install command, once the tap and first release exist:

```sh
brew install pocketIlmatto/tools/git-safety
```

Homebrew installs the tool and its dependencies. Users then run `git-safety init`
and optionally `git-safety install-hook` inside their projects. Upgrades and
removal use `brew upgrade` and `brew uninstall`; installation never enables
project hooks automatically or edits shell startup files.

Proposed tap: `pocketIlmatto/homebrew-tools`, with `Formula/git-safety.rb`.
This name leaves room for other personal tools. It was not found through the
current GitHub credentials on September 22, 2026; creation is still pending.

## What we know and what needs a decision

- Source: public `pocketIlmatto/git-safety`, default branch `main`.
- Package version: `0.1.0`. No local tags or GitHub releases were found.
- No license file or GitHub-detected license exists. The owner must choose the
  distribution license before publication; do not invent license metadata.
- Gitleaks stable 8.29.1–8.30.1 is supported. Use maintained dependencies rather
  than a private Gitleaks formula. Recheck the current formula before release.
- Confirm the proposed tap name, first tag (`v0.1.0`), license, and publication
  authorization before creating remote resources. Local preparation and tests
  can be completed first; present the exact artifacts for publication review.

## Packaging decisions

Use a versioned source archive attached to a GitHub release in the source repo,
with its SHA-256 fixed in the formula. The eventual URL will have the form
`https://github.com/pocketIlmatto/git-safety/releases/download/v0.1.0/git-safety-0.1.0.tar.gz`.
Never replace an existing release asset or retag a published version; release a
new version if its bytes must change. Checksums verify the chosen bytes, not
independent publisher identity.

Install the package at `libexec/git_safety/`, with a small Homebrew-specific
command wrapper under `bin` that executes `libexec/git_safety/cli.py` directly.
The existing direct-script import path supports this layout. The wrapper must:

- Use the declared Homebrew Python directly, initially targeting the already
  validated Python 3.14 line after confirming the formula name.
- Make declared Homebrew Git, ripgrep, and Gitleaks take precedence over stale
  copies on the caller's PATH, using formula paths rather than hardcoded Intel
  or Apple Silicon prefixes. Retain the caller's remaining PATH.
- Preserve the caller's working directory, arguments, exit code, and supported
  Gitleaks configuration environment variables. Invoke the installed package,
  never the original development checkout or a package in the scanned project.
- Suppress bytecode writes, as the current launcher does.

Use safely quoted formula-derived paths and preserve `"$@"`; test directories
and arguments containing spaces. Use stable dependency `opt` paths so routine
dependency keg replacement does not strand the wrapper.

Declare normal dependencies on `git`, `ripgrep`, `gitleaks`, and the selected
Python formula. Preserve the runtime Gitleaks range check. Do not add a pip
environment, PyPI package, compiler, bundled scanner, or a custom updater for
this standard-library-only program. Keep the existing source-checkout installer
for contributors; the Homebrew formula must not call it.

Start with source installation, without bottles. There is no application
compilation to save; bottles would add platform artifacts and publishing work.
Dependencies may still use Homebrew's existing bottles.
Initial Brew support is macOS. Existing Ubuntu scanner tests remain; do not
claim Linuxbrew or untested Mac architectures have been validated.

## Implementation checkpoints

Commit each completed checkpoint after its checks. Complete parallel work within
a checkpoint before moving to the next.

1. **Prepare versioned release artifacts.** Add a release builder and instructions
   in this repo, with explicit version/ref inputs. Require a committed source
   revision and matching package version. Produce a deterministic archive and
   checksum outside scanned worktrees; include source, docs/tests, and the chosen
   license, but no ignored files, local policy, or `.git` data. Verify archive
   inventory, reproducibility, extraction, and execution without the original
   checkout. A repeat build from the same commit must have the same digest.
   Create no tag or release yet. Checkpoint: release preparation and tests.

2. **Implement the formula and installed launcher.** Keep a canonical template
   under `packaging/homebrew/` and a small renderer that requires release version,
   asset URL, and digest. Generate the concrete formula only after building the
   archive: keeping a template avoids an archive/formula checksum cycle. Stage
   the future tap contents locally for review. Add the wrapper and meaningful
   formula tests below. Validate with Homebrew style/audit and local install/test
   checks; resolve real findings without silently weakening the audit. Checkpoint:
   formula template, renderer, packaging tests, and staged tap instructions.

3. **Validate installation and transitions.** Test in a disposable Brew CI runner
   or explicitly approved local tap, without displacing the user's current
   installation. Use the candidate archive for prepublication tests; later test
   the exact final URL/digest as well. Validate install, reinstall, upgrade to a
   second local fixture version, uninstall, and restoration of the previous known
   version. Include minimal/conflicting PATH cases and a real Git hook. Confirm
   project rule files, Git config, and hooks are preserved across package changes.
   Checkpoint: lifecycle evidence and any necessary fixes.

4. **Finish docs and low-cost CI.** Make the one-command Brew install the normal
   README path once usable; retain contributor instructions. Document source-to-
   Brew transition, dependency selection, Gitleaks bounds, GUI PATH, update and
   removal. Add one Mac packaging smoke job for packaging changes and release
   candidates. Keep the existing Linux suite and Gitleaks endpoint matrix; do not
   multiply that entire matrix across Mac architectures or add scheduled polling.
   Pin Actions revisions and use read-only permissions for tests. Checkpoint:
   reviewed docs, CI, and release checklist.

5. **Publish only after artifact review and authorization.** Show the exact source
   commit, tag, archive digest, rendered formula, proposed tap files, license, and
   validation results. Then create/push the approved tag and GitHub release, create
   the approved tap repo, and publish the reviewed formula. Verify downloads and
   the advertised install command from the remote tap. Record hosted results and
   final revisions. Do not call a local staging test a successful public install.

## Tests that matter

The formula's `test do` should do more than print a version. In a disposable Git
repository with a synthetic identity, initialize policy, accept clean content,
reject an assembled synthetic credential, and verify the value is absent from
diagnostics. Run the installed entry point from a nested directory. Isolate
global hooks and configuration so the test cannot invoke a developer's hooks.

Packaging integration tests should additionally prove:

- The original checkout can be unavailable; the installed CLI still works.
- Dependency selection survives a minimal PATH and deliberately conflicting
  executables. The wrapper never changes the target repository by changing cwd.
- An existing hook still finds `git-safety` after a package upgrade. A missing
  CLI after uninstall fails clearly. A GUI must still find the top-level Brew
  executable; the wrapper cannot repair an environment that never launches it.
- A source-install symlink earlier on PATH is diagnosed in transition guidance.
  Install and test Brew's command by its explicit path first, then remove the
  old shortcut through its checkout's uninstall command. Confirm `type -a
  git-safety` and `command -v git-safety` select the intended version. Do not
  delete source shortcuts automatically or erase the checkout.
- Uninstall leaves user policy and hooks alone. Instructions remove hooks first
  when permanently retiring the tool. Rollback restores a tested toolkit and
  compatible Gitleaks combination; it does not promise `brew rollback` exists or
  that Homebrew retains old kegs after cleanup.

## Release operations, risks, and cost

Start with manual, documented publication. Each release updates one version,
builds one source archive, runs one packaging check, and updates one formula.
Do not introduce cross-repository automation credentials just to save that small
step. Later automation can be separately scoped if release frequency warrants it.

An ordinary `gitleaks` dependency can advance beyond our range. During formula
installation, run the packaged dependency validator under the intended dependency
PATH and fail clearly if unsupported; don't duplicate range constants in Ruby.
Retain runtime validation because an independent dependency upgrade can happen
later. Test both cases. No automatic fallback to another binary is allowed.

The current manual Gitleaks fallback applies to the source installation, not the
Brew wrapper. Recovery for a Brew install is an updated compatible toolkit or a
deliberate return to the verified source installation plus its pinned dependency,
followed by PATH and hook checks. Document that procedure; do not silently alter
Brew dependencies or invent a dependency-override setting in the first release.
Validate Brew's current version before each release and expand support using
the existing focused suite. This availability tradeoff is the principal ongoing
maintenance obligation.

The work with the most uncertainty is Homebrew-specific execution, PATH and
package lifecycle—not copying Python files. Dependency downloads and a Mac CI
runner dominate incremental runtime/cost. Avoid bottles, large release matrices,
and automated updater services initially. No dollar estimate is assumed.

## Delegation during implementation

After agreeing on interfaces, two bounded streams can run in parallel:

| Work | Owner/model | Boundary |
| --- | --- | --- |
| Release builder and archive checks | `gpt-5.6-terra`, medium | Release scripts/tests; no publishing |
| Formula template, wrapper, and package tests | `gpt-5.6-terra`, medium | Homebrew packaging files/tests; no changes to active installations |
| Integration, dependency decisions, docs, publication review | Primary agent | Shared files and final verification |

Use concise briefs with file ownership and acceptance checks. Don't delegate
another full scan-engine audit or repeat the finished Gitleaks version research.
Each stream commits its tested files before integration; the primary owns final
artifact review and any separately authorized publication.

For this planning turn, one terra/medium sub-agent reviews packaging risks while
the primary handles release and repository decisions. No implementation agents
or publication jobs are started.

## References

Homebrew documents [tap naming and installation](https://docs.brew.sh/How-to-Create-and-Maintain-a-Tap),
and its [formula cookbook](https://docs.brew.sh/Formula-Cookbook) covers dependency
declarations, private `libexec` files, and command wrappers. These support the
packaging approach; the lifecycle requirements above come from this toolkit's
current launcher, installer, hook behavior, and compatibility policy.
