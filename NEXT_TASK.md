# Next Task

_Last updated: 2026-08-02 (GitHub Actions CI repair locally verified; independent acceptance pending)_

## Single next action

Create a fresh clean read-only GPT-5.6-sol review of exact range
`0aa93021e533114eb6b742fe518c2d09194c3394..HEAD` on
`codex/ci-repair-20260802`. Review findings first with P0-P3 severity, then finish
with explicit `GO` or `REVISE`. Do not edit, commit, merge, move refs, push,
release, or access private source or Demo material.

Verify that:

- `pyproject.toml` declares every direct test import needed during collection,
  while runtime dependencies remain unchanged.
- `.github/workflows/tests.yml` installs `.[test]`; both workflows use real
  published `actions/checkout@v6` and `actions/setup-python@v6` releases.
- Windows verification waits for both a valid `/api/snapshot` response and the
  exact launcher-owned readiness file before API checks or process termination.
- The opt-in readiness file cannot change ordinary browser-first launcher use,
  and the new regression would fail if HTTP health alone returned early.
- No engine, Campaign, Schema, save, public content, or private-material boundary
  changed outside the authorized CI repair.

## Candidate evidence

- Clean `.[test]` installation and `pip check` pass with `jsonschema 4.26.0`,
  `referencing 0.37.0`, `pytest 8.4.2`, and `pytest-xdist 3.8.0`.
- Full unittest: 1383 passed, 12 platform/privilege skips.
- Serial and xdist pytest: 1371 passed, 12 platform/privilege skips each.
- Pinned PyInstaller 6.21.0 Windows packaging suite: 14/14 passed, including
  real repository-external frozen and zipapp Web/console cold starts.
- Ruff, configured Pyright, compileall, original-demo validation, history safety,
  fsck, and diff checks pass.
- Baseline local `main` and local `origin/main` are `0aa9302`. A fresh direct
  GitHub query was reset by the network; refresh it before any authorized push.
- The main worktree's untracked `uv.lock` remains 14,471 bytes with SHA-256
  `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`.

## Boundaries

- Independent acceptance is pending; controller verification is not `GO`.
- Do not push, release, force-push, or begin another public slice.
- Do not add private source, canon, adaptation, content, save, image, candidate,
  or report material to the public repository.
- Preserve the user's untracked `uv.lock` exactly.
