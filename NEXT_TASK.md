# Next Task

_Last updated: 2026-08-02 (first review P2 corrected; fresh re-review pending)_

## Single next action

Create a fresh clean read-only re-review of the exact
`812a00fe4412f4fc7068ac2e188c5c26d0a03157..HEAD` range on
`coord/demo-1-58-public-integration`. Reproduce the prior empty-dialogue-node P2
against `7f1ceff`, verify that code commit `22a05d1` closes it across Schema,
loader, and real CLI validation, then audit the complete integrated candidate.
Report P0-P3 findings first and finish with explicit `GO` or `REVISE`. Do not
edit, commit, merge, fast-forward `main`, push, release, or access any private
source or Demo material.

## Corrected candidate evidence

- Combined merge `1a9fcf607806b7f66e04545c1878bdd7ac16047b` retains exact
  parents `91e5258` and accepted CampaignSpec candidate `15f47ca`; accepted
  Runtime candidate `2615418` remains an ancestor. Code commit `22a05d1` is the
  narrow post-review parity correction.
- Controller gates passed: 66 focused tests with 2 Windows symlink-permission
  skips; 1382 unittest tests with 12 skips; serial and xdist pytest each reported
  1370 passed / 12 skipped; Ruff, two Pyright scopes, and compileall passed.
- Draft 2020-12 Schema/fixture validation, three public content validations,
  repository-external CampaignSpec golden bytes, the full Forge lifecycle,
  history safety, fsck, and both diff checks passed.
- Repository-external zipapp and PyInstaller 6.21.0 candidates both passed Web
  and console cold starts. Their SHA-256 values are
  `4e011c22a67a4db774e26353ce7c09b4568fa6a39571254bd793c0c4de163a6e`
  and `cfde8f6a87c22b5a6fde2d1a00ab501fdd5e4897d319f72d3f817f403aabf269`.

## Boundaries

- Shared local `main` and local `origin/main` remain at `812a00f`; the
  integration worktree is clean. A live remote refresh failed after a connection
  reset, so GitHub `main` must be queried again immediately before any local
  fast-forward.
- Do not push, release, force push, or add private source, canon, adaptation,
  content, save, image, or report material to the public repository.
