# Next Task

_Last updated: 2026-08-02 (Runtime and CampaignSpec individual reviews are GO; combined candidate pending)_

## Single next action

Verify the exact `coord/demo-1-58-public-integration` HEAD as one combined public
candidate. Run the full focused, full-suite, quality, Schema, external CLI,
Windows delivery, history-safety, fsck, and diff gates, then obtain a separate
clean read-only `GO` or `REVISE` for that integrated commit. Do not fast-forward
local `main`, push, or release before the combined decision is GO.

## Completed evidence

- Runtime Campaign Foundation `2615418` received a fresh read-only GO with no
  P0-P3 findings: 17 focused tests, 1333 unittest tests with 10 skips, 1323
  pytest tests with 10 skips, and all named quality/safety gates passed.
- CampaignSpec v1 `15f47ca` received a fresh read-only GO with no P0-P3
  findings: 48 focused tests with 2 Windows symlink-permission skips, 1364
  unittest tests with 12 skips, 1352 pytest tests with 12 skips, and all named
  quality/Schema/golden gates passed.
- The public integration branch combines the accepted candidates in dependency
  order. Combined-candidate verification and acceptance are not yet complete.

## Boundaries

- Shared `main` remains at the pre-integration baseline until combined GO.
- Do not push, release, force push, or add private source, canon, adaptation,
  content, save, image, or report material to the public repository.
