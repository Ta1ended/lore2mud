# Next Task

_Last updated: 2026-08-02 (CI repair independently accepted and branch workflows green; acceptance seal pending review)_

## Single next action

Create a fresh clean focused read-only GPT-5.6-sol review of exact range
`9c2f4db818e2b3bb6f7bc05659c8bb654f73c635..HEAD` on
`codex/ci-repair-20260802`. Review findings first with P0-P3 severity, then finish
with explicit `GO` or `REVISE`. Do not edit, commit, merge, move refs, push,
create or merge a PR, release, or access private source or Demo material.

Verify that:

- The range changes only `PROJECT_MEMORY.md`, `PROJECT_STATE.md`, `NEXT_TASK.md`,
  `DECISIONS.md`, and `CHANGELOG.md`.
- The source, workflows, dependency metadata, tests, packaging, Schema, examples,
  and scripts remain byte-identical to independently accepted commit `9c2f4db`.
- The records accurately state independent `GO`, normal branch-only push, remote
  branch identity, successful GitHub runs, unchanged `main`, and preserved
  untracked `uv.lock`.
- No statement turns repair-branch success into a claim that `main` is updated,
  or expands CI repair acceptance into Campaign/private scope.

## Accepted evidence

- Independent review accepted exact commit `9c2f4db` with no P0-P3 findings after
  all named dependency, test, Windows packaging, quality, safety, and Git gates.
- Successful pre-push refresh found GitHub `main=0aa9302` and no remote repair
  branch. Normal push created `origin/codex/ci-repair-20260802=9c2f4db`.
- GitHub `quality` run `30765851991` and `tests` run `30765852001` both succeeded;
  the latter includes successful Python 3.11/3.12/3.13 and Windows candidate jobs.
- Local `main` and local `origin/main` remain `0aa9302`; no PR was created or merged.
- The main worktree's untracked `uv.lock` remains 14,471 bytes with SHA-256
  `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`.

## Boundaries

- This focused review accepts only the documentation seal, not new code.
- Do not push the seal until focused `GO`; after GO, update only the existing
  repair branch with a normal non-force push.
- Do not create/merge a PR, update `main`, release, force-push, or begin another slice.
- Do not add private source, canon, adaptation, content, save, image, candidate,
  or report material to the public repository.
- Preserve the user's untracked `uv.lock` exactly.
