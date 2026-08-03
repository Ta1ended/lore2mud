# Next Task

_Last updated: 2026-08-03 (public original_demo experience repair locally verified; independent acceptance pending)_

## Single next action

Create a fresh clean GPT-5.6-sol read-only acceptance of the exact local
`0aa93021e533114eb6b742fe518c2d09194c3394..HEAD` range after the implementation
commit is created. Review findings first with P0-P3 severities and finish with exactly
one `GO` or `REVISE`. Do not edit, commit, move refs, push, release, or access any
private source, canon, adaptation, content pack, image, save, or report material.

Verify the expected 20-file public scope: item content/runtime/loader/save plumbing,
`schemas/item.schema.json`, the content-pack format guide, six `original_demo` files,
three focused test modules, and the five mandatory handoff files. Confirm the
pre-existing untracked `uv.lock` is unchanged and excluded from the commit.

## Required reproduction

1. Prove `droppable` defaults to `true`, rejects non-boolean values in both Draft
   2020-12 and `load_content_pack()`, and survives World creation plus save/load
   reconstruction without changing save v9 or content-pack 0.10.0.
2. Reach the beacon platform, defeat the sentinel, take `item_beacon_core`, attempt
   `drop item_beacon_core`, and prove the command is rejected with all placement
   state unchanged. Then go west/east, enter the heart, select the restore option,
   and confirm `quest_restore_beacon` plus `flag_beacon_restored=true`.
3. Inspect every `monster_defeated` quest description in `original_demo` and confirm
   none claims that a monster blocks movement. Separately prove movement remains free;
   do not add or infer a monster-gated-exit mechanic.
4. From a fresh game, use `look`, start Elder Chen's dialogue, choose the direct
   `4 -> 2` route, receive `item_chen_token`, and use the optional gated west exit.
   Also confirm the historical `1 -> 1 -> 2` reward route and opening option 3
   farewell remain compatible.
5. Run focused and full tests, compileall, original-demo validation, Draft 2020-12
   validation, Ruff, Pyright, history safety, fsck, and diff checks. Re-run the
   README walkthrough through beacon restoration and an ending save.

## Current local evidence

- 141 focused unittest tests passed.
- Full unittest: 1390 tests, 12 conditional skips.
- Full pytest: 1378 passed, 12 conditional skips.
- Draft 2020-12: 36 public original-demo instances passed.
- Compileall, `lore2mud validate`, Ruff, Pyright, history safety, fsck, and diff
  checks passed.
- README, protected-core, and direct-token real CLI flows passed using repository-
  external save directories.
- Independent acceptance remains pending; implementation context does not declare GO.

## Boundaries

- Public engine and `examples/original_demo` only; private content development is stopped.
- No monster-blocking system, combat expansion, campaign/narrative expansion, save-format
  bump, content-pack version bump, dependency change, push, release, or force-push.
