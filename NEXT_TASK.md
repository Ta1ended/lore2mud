# Next Task

_Last updated: 2026-08-02 (combined controller gates passed; fresh integration review pending)_

## Single next action

Create a separate clean read-only review of the exact
`812a00fe4412f4fc7068ac2e188c5c26d0a03157..HEAD` range on
`coord/demo-1-58-public-integration`. Report findings first as P0-P3 and finish
with an explicit `GO` or `REVISE`. The reviewer must verify the merge ancestry,
Runtime/CampaignSpec interaction, handoff accuracy, and the named evidence; it
must not edit, commit, merge, fast-forward `main`, push, release, or access any
private source or Demo material.

## Candidate evidence

- Combined code commit `1a9fcf607806b7f66e04545c1878bdd7ac16047b` has merge
  parents `91e5258` and accepted CampaignSpec candidate `15f47ca`; accepted
  Runtime candidate `2615418` is an ancestor.
- Controller gates passed: 65 focused tests with 2 Windows symlink-permission
  skips; 1381 unittest tests with 12 skips; serial and xdist pytest each reported
  1369 passed / 12 skipped; Ruff, two Pyright scopes, and compileall passed.
- Draft 2020-12 Schema/fixture validation, three public content validations,
  repository-external CampaignSpec golden bytes, the full Forge lifecycle,
  history safety, fsck, and both diff checks passed.
- Repository-external zipapp and PyInstaller 6.21.0 candidates both passed Web
  and console cold starts. Their SHA-256 values are `aa7a25ced70b41c92d8e39fa547296b94197c3ab04bd354a5d50d7eb5a42f608`
  and `68020fc96be68106b577f376c64a2ec34ab66086522ae9a1ed83653b98096431`.

## Boundaries

- Shared local `main` and local `origin/main` remain at `812a00f`; the
  integration worktree is clean. A live remote refresh failed after a connection
  reset, so GitHub `main` must be queried again immediately before any local
  fast-forward.
- Do not push, release, force push, or add private source, canon, adaptation,
  content, save, image, or report material to the public repository.
