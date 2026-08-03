# Next Task

_Last updated: 2026-08-03_

## Single Next Action

Complete the two V2-0 gates for the exact V2 Product & Architecture Reset commit:
fresh independent read-only TECH review, then explicit user PRODUCT PASS.

The TECH reviewer must resolve the full branch-tip SHA, confirm its parent is
`1a5a8857579ebf840de4e39e414b52592baea6ba` and its subject is
`docs: establish v2 product and architecture reset`, and review that exact commit.
The implementation context cannot declare GO.

## Scope

- Expected change set: exactly the 13 Markdown files named in the V2-0 reset task.
- Verify that source, pipeline, schemas, examples, tests, workflows, packaging,
  dependencies, content/save versions, and private material are byte-unchanged.
- Review product identity, roles, modes, PLAT-1, metrics/non-goals, V1/V2 distinction,
  code-map accuracy, Authoring/Runtime planes, contract names, capability safety,
  approved V2-0..V2-5 roadmap, model floor, separated passes, and Git gates.
- Prove `CampaignSpec` is consistently described as authoring IR, not runtime input.
- Confirm the primary untracked `uv.lock` boundary is recorded exactly and no
  `uv.lock` exists in the candidate worktree or commit.

## Required Decision

1. Independent TECH review reports findings first with P0-P3 and ends with exactly
   one `GO` or `REVISE`. It is read-only: no edits, ref movement, push, release,
   private access, or new scope.
2. After TECH GO, the user gives PRODUCT PASS or requested revisions for the product
   boundaries, vocabulary, roadmap, PLAT-1, and development model.

## Exit

After both passes, the root controller may create a documentation-only seal that
records the gates and routes `NEXT_TASK.md` to the first authorized V2-1 Public
Runtime Boundary slice. Until then, do not implement V2-1, push, move `main`, release,
or access private material.

## If Blocked

If the exact `gpt-5.6-sol` reviewer at reasoning `xhigh` or higher is unavailable,
stop and report; do not downgrade. If PRODUCT PASS is withheld, record the owner's
requested changes and keep V2-1 blocked.
