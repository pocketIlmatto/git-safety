# Choosing an installation experience

Only **local checkout + symlink** is implemented today. The other options below
are proposals, not installation commands you can use with this project yet.

The main difficulty is dependency setup: this is a Python CLI that also runs
Git, ripgrep, and exactly Gitleaks 8.30.1. Packaging the Python code alone doesn't
install those external programs. Any replacement installer needs to address
that explicitly.

## Comparison

Complexity and cost are estimates for this project, not vendor quotes. Cost
includes developer time, release CI, downloads/storage, and support. The options
can be combined; for example, a Homebrew formula can install a release archive.

| Pattern | User experience | Build and maintenance effort | Security tradeoffs | Cost and fit |
| --- | --- | --- | --- | --- |
| **Local checkout + symlink** (current) | Get the source, install dependencies, run a script, set PATH. Updates require Git knowledge. | Low effort for us; users handle versions, locations, and dependency problems. Moving or editing the checkout affects the command. | Source is inspectable and can be pinned to a commit. Local edits immediately change what hooks execute. | Lowest release infrastructure cost, but more user support. Useful for development and early personal use. |
| **Downloadable release archive** | Download a named version, unpack it, run a local installer. No Git knowledge needed. | Low–medium. We need release tags, archives, checksums, stable installation directories, and update/removal instructions. Dependencies still need a solution. | Users can verify the downloaded artifact. A checksum detects changes relative to the expected digest; it doesn't independently establish who published it. | Small artifacts and relatively modest release work. A useful base for other installers. |
| **Homebrew tap** | Install, upgrade, and uninstall through familiar `brew` commands; dependencies can be declared. | Medium. Maintain a formula in a tap, release URLs/digests, dependency choices, and install tests. macOS is the primary fit here. | Downloads can be checksum-verified. Users must trust our tap and its installation code. Managing dependencies centrally makes updates easier to track. | Low incremental distribution cost if source archives are used; ongoing release testing still costs time. Best next user-facing option for this project's Mac audience. |
| **Python package via pipx or uv** | Install a named Python tool into its own environment; standard upgrade/uninstall commands. Requires pipx or uv first. | Low–medium for Python packaging and releases. Git/ripgrep/Gitleaks still need separate installation or a companion setup step. | Python environments prevent dependency collisions, but aren't security sandboxes. Users still trust the package publisher and dependencies. | Small package/build cost. Good for Python-oriented users and cross-platform distribution, but doesn't solve our hardest setup problem by itself. |
| **Bootstrap installer script** | Download and run one installer that selects the platform and installs a chosen version. | Medium–high. We own PATH setup, dependency versions, download verification, interrupted installs, collision handling, upgrade, rollback, and uninstall. | The script runs with the user's permissions. A versioned script and verified payloads are reviewable; piping a changing remote script straight into a shell gives users less opportunity to inspect it. | Few artifacts if source-based, but substantial support and security maintenance. Worth it only if we need a consistent experience outside package managers. |
| **Standalone executable** | Download a program and put it on PATH; can avoid a separate Python installation. | High. Build/test supported OS/architecture combinations, manage bundled runtime updates, and adapt launcher/resource lookup. External executables must still be shipped or installed separately. | Bundled components need timely security updates. Signing and release verification become part of the delivery process. | More CI and larger artifacts; signing can add cost. Attractive later for a wider audience, excessive for the current personal-tool scope. |
| **Container image** | Run a pinned image with the repository mounted into it. Dependencies can be included. | Medium–high. Maintain base-image/dependency updates and test mounts, file permissions, linked worktrees, and hook invocation. Requires a container runtime. | Pinning an image digest fixes the image version. Mounted repository data is still accessible to the container; isolation doesn't make untrusted scanner code safe. | Larger downloads/storage and a runtime to support. More useful for repeatable CI than frequent local pre-commit checks. |

Homebrew's [tap guide](https://docs.brew.sh/How-to-Create-and-Maintain-a-Tap) and
[formula cookbook](https://docs.brew.sh/Formula-Cookbook) describe custom formulae,
dependency declarations, and release checksums. A tap doesn't require accepting
the formula into Homebrew's main collection.

[pipx](https://pipx.pypa.io/stable/) and
[uv's tool installer](https://docs.astral.sh/uv/guides/tools/) provide separate
Python environments and command exposure. They manage the Python package; our
external-command dependencies remain our responsibility.

[PyInstaller](https://pyinstaller.org/en/stable/operating-mode.html) can bundle
the Python interpreter, but the result is platform-specific. For this codebase,
bundling Python wouldn't automatically include Git, ripgrep, or Gitleaks.
[Docker's run documentation](https://docs.docker.com/engine/containers/run/)
describes image execution and host-directory mounts.

## Recommendation for git-safety

Use a **Homebrew tap backed by versioned release archives** as the next install
experience. Most intended local users already have Homebrew. It can manage the
tool and its dependencies without making this project maintain a second package
manager inside an installer script. Keep the existing checkout install for
contributors. Linux CI can continue installing a pinned version separately.

The first design decision is Gitleaks compatibility. A normal dependency on
Homebrew's Gitleaks formula doesn't guarantee version 8.30.1. We have two choices:

- Test and support an explicit range of Gitleaks versions, then depend on the
  maintained formula. This needs compatibility tests; removing the exact-version
  check alone would not establish support.
- Keep 8.30.1 and maintain a separate versioned dependency in our tap. That makes
  the initial behavior predictable but leaves us responsible for its eventual
  security updates and platform support. Homebrew documents
  [keeping historical versions in a tap](https://docs.brew.sh/How-to-Create-and-Maintain-a-Tap).

I favor testing a supported range before shipping the tap. That reduces the
long-term burden of carrying an old scanner version. Until then, the README
documents the existing installation honestly, including the manual pinned
dependency step.

A follow-up implementation would need a release location and naming scheme,
the Gitleaks compatibility decision, a formula, and fresh-machine install,
upgrade, uninstall, and hook tests. No tap, package, bootstrap downloader, or
release publication was added as part of this documentation revision.
