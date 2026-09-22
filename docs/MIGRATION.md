# Migration guide

This guide describes a future, consumer-owned migration from repository-local
privacy and secret checks to `git-safety`. Migration is intentionally deferred
until parity has been demonstrated in the consuming repository. No Hammerspoon
or other consumer migration is performed by this repository.

## Before scheduling migration

Choose and record:

- the exact verified `git-safety` commit;
- the exact Gitleaks 8.30.1 binary and checksum;
- the consumer's public privacy rules and narrow match-level exceptions;
- the secure source for clone-local rules;
- the CI checkout and permissions policy; and
- the rollback commit and uninstall procedure.

Keep application behavior, private configuration, GUI integration, and
consumer-specific policy in the consumer repository. Do not copy private
identifiers, credentials, fixtures, logs, or local allowlists into this tool.

## Inventory and preserve

Inventory the existing scanner, hooks, CI jobs, Gitleaks configuration and
ignore rules. Classify each rule as generic privacy, consumer-specific privacy,
credential detection, or application behavior. Move only reusable scanner and
workflow behavior. Preserve consumer-specific identifiers in
`.git-safety/privacy-patterns` or secure local policy, using safe placeholders in
public examples.

For consumers with public Bear URL rules, preserve the rule while replacing
real account or host values with a documented placeholder. Create precise
ignore entries first, before moving local policy files; then copy local rules
only through the consumer's secure, ignored path. Never copy private values
into public policy, fixtures, documentation, or logs.

Preserve existing `.gitleaks.toml` and `.gitleaksignore` semantics. The toolkit
uses native Gitleaks environment precedence, then the repository root config,
and honors `.gitleaksignore`; privacy allowlists do not suppress Gitleaks.

## Shadow validation

Install the pinned tool outside the consumer worktree, run `git-safety init`,
and compare old and new checks in disposable clones. Run staged, worktree,
history, and `all` scans against synthetic fixtures that cover partial staging,
tracked ignored files, untracked files, symlinks, deleted historical content,
other local refs, malformed policy, and shallow history. Confirm expected exit
codes (`0` clean, `1` findings, `2` incomplete/error) and inspect only redacted
diagnostics.

For history parity, use a full local clone. `git-safety history` scans all
reachable local refs with explicit full-history Gitleaks options and does not
fetch. A shallow or unfetched clone is an incomplete audit. Privacy history
uses current on-disk policy and deduplicates blobs, so it is not a byte-for-byte
replay of policy as it existed in each historical commit.

Staged privacy scanning reads added index content. Staged secrets use Gitleaks'
native `git --staged` engine. Their Git attribute, binary, and text handling can
differ; parity means agreeing on the required coverage and handling differences
explicitly, not assuming identical engines.

## Cutover

After shadow results are reviewed by the consumer owner:

1. Pin the verified tool checkout and Gitleaks binary in CI.
2. Add `.git-safety/privacy-patterns`, `.git-safety/privacy-allowlist`, and the
   local template through `git-safety init`; review every rule.
3. Provision local policy securely and verify both local files are ignored and
   untracked. Never add a broad allowlist to hide fixtures or findings.
4. Install the opt-in hook with `git-safety install-hook` only after inspecting
   existing hook configuration. Resolve conflicts manually; the command refuses
   unsafe or user-owned hooks.
5. Run `git-safety all` in the consumer checkout and in full-history CI.
6. Remove the old duplicate scanner only after the new checks have passed in the
   agreed validation matrix and the rollback window has been recorded.

The hook is clone-local and bypassable with `--no-verify`; enforce publication
requirements separately through protected-branch CI settings.

## Rollback and removal

Rollback means restoring the consumer's previously verified scanner and CI
configuration, then recording why the cutover was reversed. Do not rewrite
history or delete policy as part of rollback. To remove the toolkit integration,
run `git-safety uninstall-hook` and remove only files explicitly owned by the
consumer's migration change. The installer uninstall command removes only the
owned CLI symlink. Leave repository policy available for audit until the
consumer owner approves its removal.

## Incident handling

If a scan finds a credential, revoke or rotate it through its owning service
before deciding whether history cleanup is needed. `git-safety` does not rotate
credentials or rewrite history. Treat history rewriting, force-pushes, branch
protection changes, and remote cleanup as separate authorized operations.
