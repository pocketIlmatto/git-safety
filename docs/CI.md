# CI for consuming repositories

The toolkit's own `.github/workflows/checks.yml` tests the exact commit checked
out for the run. Consumer jobs must additionally pin their installed toolkit to
a reviewed full commit SHA. No published source URL or release is assumed here.

Local installations use Homebrew's maintained Gitleaks formula within the
supported 8.29.1–8.30.1 range. CI intentionally keeps an exact release/checksum:
the toolkit tests both endpoints, and this consumer example pins 8.30.1.
See [compatibility policy](GITLEAKS_COMPATIBILITY.md) when updating those pins.

Use the following workflow as a starting point. Replace both `YOUR_...` values
with your verified toolkit repository URL and its full 40-character commit SHA.
Keep those pins in reviewed workflow code. The Git object ID verifies the fetched
toolkit revision; the SHA-256 below verifies the Gitleaks release archive before
extraction. Installation and scanner scratch files stay outside the checkout.

```yaml
name: Security
on:
  push:
    branches: [main]
  pull_request:
permissions:
  contents: read
concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true
jobs:
  security:
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    env:
      GIT_SAFETY_REPOSITORY: YOUR_VERIFIED_TOOL_REPOSITORY_URL
      GIT_SAFETY_COMMIT: YOUR_VERIFIED_FULL_COMMIT_SHA
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
          persist-credentials: false
      - name: Install pinned tools outside the checkout
        shell: bash
        run: |
          sudo apt-get update
          sudo apt-get install --yes python3 ripgrep
          [[ "$GIT_SAFETY_COMMIT" =~ ^[0-9a-f]{40}$ ]]
          tool_dir="$(mktemp -d "${RUNNER_TEMP:?}/git-safety.XXXXXX")"
          git -C "$tool_dir" init --quiet
          git -C "$tool_dir" fetch --depth=1 "$GIT_SAFETY_REPOSITORY" "$GIT_SAFETY_COMMIT"
          git -C "$tool_dir" checkout --detach FETCH_HEAD
          test "$(git -C "$tool_dir" rev-parse HEAD)" = "$GIT_SAFETY_COMMIT"
          echo "$tool_dir/bin" >> "$GITHUB_PATH"
          archive=gitleaks_8.30.1_linux_x64.tar.gz
          scratch="$(mktemp -d "$RUNNER_TEMP/gitleaks.XXXXXX")"
          trap 'rm -rf "$scratch"' EXIT
          curl --fail --location --retry 3 --output "$scratch/$archive" \
            "https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/$archive"
          (cd "$scratch" && echo '551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb  gitleaks_8.30.1_linux_x64.tar.gz' | sha256sum --check --strict)
          tar --extract --gzip --file "$scratch/$archive" --directory "$scratch" gitleaks
          mkdir -p "$RUNNER_TEMP/security-bin"
          install -m 0755 "$scratch/gitleaks" "$RUNNER_TEMP/security-bin/gitleaks"
          echo "$RUNNER_TEMP/security-bin" >> "$GITHUB_PATH"
      - name: Full privacy and credential scans
        run: git-safety all
```

Run the consuming project's own regression tests in a separate step or job,
with its own dependencies. Hammerspoon retains its Lua/application test runner;
this toolkit requires no Lua. Do not copy clone-local privacy policies to CI.
Public protections belong in committed `.git-safety` policy files; run `init`
locally and commit them before enabling the workflow, rather than creating
missing policy silently in CI.

Full checkout history is required. A shallow consumer checkout fails with code
2; the toolkit never fetches during scans. `fetch-depth: 0` cannot supply refs
that the remote does not expose, unavailable submodule contents, or other clones'
local branches. Branch protection and required checks are separate settings;
hooks remain opt-in and bypassable. This example does not modify those settings.

The checkout revision was verified against the official `v7.0.1` tag, and the
Gitleaks digest against its official
[8.30.1 checksums](https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_checksums.txt).
Local YAML/shell checks are not evidence that a hosted GitHub Actions run passed.
