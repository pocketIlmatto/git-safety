2026-09-21
Please move forward with testing and supporting an explicit range of Gitleaks versions, then depend on the
  maintained formula. This needs compatibility tests; removing the exact-version
  check alone would not establish support.

Then implement a **Homebrew tap backed by versioned release archives** as the next install
experience.

2026-09-22 status: Compatibility range 8.29.1–8.30.1 implemented and tested.
Local dependency instructions now use the maintained Homebrew Gitleaks formula.
See docs/GITLEAKS_COMPATIBILITY.md. The toolkit tap/release archives remain next.

2026-09-22 plan: See docs/HOMEBREW_PLAN.md for implementation checkpoints,
packaging/lifecycle tests, release decisions, and publication boundaries. One
bounded sub-agent review informed the plan; implementation has not started.
