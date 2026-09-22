# Install the dependencies

The current installer links the CLI into your PATH. It does not install Git,
Python, ripgrep, or Gitleaks for you. Return to the [README](../README.md#installation)
once these commands work:

```sh
git --version
python3 --version
rg --version
gitleaks version
```

Required versions: Git 2.31+, Python 3.9+, ripgrep 13+, Bash 3.2+, and Gitleaks
**8.30.1 exactly**. The other minimum versions describe the supported interface;
see [validation](../VALIDATION.md) for the versions actually tested.

## macOS with Homebrew

If Git, Python, or ripgrep is missing or too old, install it through Homebrew:

```sh
brew install git python ripgrep
```

If `gitleaks version` already prints `8.30.1`, keep that installation. Homebrew
may supply a different Gitleaks version, which this toolkit currently rejects.
This is a packaging gap we still need to fix.

If you need 8.30.1, the following block downloads the release for an Apple Silicon
or Intel Mac, checks its SHA-256 digest, and installs it in `~/.local/bin`.
It refuses to replace an existing file there. It doesn't remove or change a
Homebrew installation. These digests come from the official
[8.30.1 release checksum file](https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_checksums.txt).

```sh
bash <<'BASH'
set -euo pipefail
case "$(uname -m)" in
  arm64)
    archive=gitleaks_8.30.1_darwin_arm64.tar.gz
    digest=b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5
    ;;
  x86_64)
    archive=gitleaks_8.30.1_darwin_x64.tar.gz
    digest=dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709
    ;;
  *) echo 'Unsupported Mac architecture' >&2; exit 2 ;;
esac
target="$HOME/.local/bin/gitleaks"
if [ -e "$target" ] || [ -L "$target" ]; then
  echo 'A file already exists at ~/.local/bin/gitleaks; inspect it before replacing it.' >&2
  exit 2
fi
scratch="$(mktemp -d /tmp/git-safety-dependency.XXXXXX)"
trap 'rm -rf "$scratch"' EXIT
curl --fail --location --retry 3 --output "$scratch/$archive" \
  "https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/$archive"
(cd "$scratch" && printf '%s  %s\n' "$digest" "$archive" | shasum -a 256 -c -)
tar -xzf "$scratch/$archive" -C "$scratch" gitleaks
mkdir -p "$HOME/.local/bin"
install -m 0755 "$scratch/gitleaks" "$target"
"$target" version
BASH
```

Use the README's PATH setup so this pinned copy is the one the CLI finds.
Run `command -v gitleaks` and `gitleaks version` to check. If you later remove
this manually installed copy, an existing Homebrew copy may become visible again.

## Ubuntu 24.04

Install the system dependencies with:

```sh
sudo apt-get update
sudo apt-get install --yes git python3 ripgrep
```

The [CI guide](CI.md) includes the pinned Gitleaks 8.30.1 Linux x64 download and
checksum verification steps. Its `RUNNER_TEMP` and `GITHUB_PATH` variables belong
to GitHub Actions; don't paste that whole job into a local terminal. Other Linux
architectures need the corresponding release asset and digest from the official
release. No Lua or Hammerspoon installation is required.
