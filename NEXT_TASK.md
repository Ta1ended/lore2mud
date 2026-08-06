# 下一任务 / Next Task

更新日期：2026-08-06

## 中文

### 唯一下一任务

**对本候选提交执行 fresh、read-only、未参与实现的 V2-3 TECH acceptance。**

### 当前依据

- 分支：`workstream/v2-3-capability-modules`；验收精确目标为候选提交后的 `HEAD`，先用
  `git rev-parse HEAD` 记录 SHA。
- 授权基线：`c37969f6b6958e66474738f88a53b9d5c2f50d99`；本候选已完成 preview、
  mixed simulation/replay/checkpoint、proofing、SDK/CLI/Web 通用集成。
- Authoring/capability/Web 聚焦矩阵已通过：`169 passed, 480 subtests passed`（2026-08-06）。
- 完整矩阵已通过：`unittest` `1565 OK (skipped=11)`；serial/xdist pytest 均为
  `1554 passed, 11 skipped, 927 subtests passed`；Ruff、Pyright、compileall、Demo validate、
  `pip check`、history safety、fsck、diff checks 和 Windows packaging smoke 均通过。
- `git ls-remote` 超时，但 GitHub REST 已确认 live `main=ba729be8d80dbcbefe90a1dc801003deec7c4c95`，
  PR #1 是 head `c37969f6b6958e66474738f88a53b9d5c2f50d99` 的 draft；没有 remote write。

### 验收步骤

1. 从精确候选 `HEAD` 读取代码、基线 diff、文档和验证证据；不编辑、不提交、不移动 refs、
   不查询或写入远端、不访问私有材料。
2. 独立复现足以支撑 findings 的边界、兼容、运行时与测试证据；以 findings-first 形式输出
   P0-P3，最后只给 `GO` 或 `REVISE`。
3. 若 `REVISE`，将可复现 findings 交回实现工作树；若 `GO`，仅创建 documentation-only handoff
   seal，仍不得 push、合并 `main`、release 或进入 V2-4/V2-5。

### 接受标准

- 空 `capability_requirement_ids` 的 V2-2 object type、canonical bytes、fingerprints、SDK/CLI
  envelopes 与 Web snapshots 保持 byte-for-byte 兼容。
- `reference_counter` capability 的 preview、mixed simulation、events/views、checkpoint
  restore、replay、proofing、SDK/CLI/Web generic transport 均有可复现证据。
- 候选工作树干净；fresh TECH acceptance 给出 findings-first `GO` 或 `REVISE`。

### 暂停与边界

- 本候选提交后在独立 TECH 验收门槛暂停，不越过后续授权边界。
- 不 push、不移动或合并 `main`、不 release、不分发 unsealed preview/report、不访问私人材料、
  不进入 V2-4/V2-5。Goal 未完成，保持真实 `active`，不伪造 `blocked`/`complete`。

### 后续队列

1. 候选提交后的 fresh read-only TECH acceptance。
2. 仅在 `GO` 后创建 documentation-only handoff seal。
3. 等待独立 PRODUCT/SECURITY/发布授权；不自动推进 main 或 release。

## English

### Single Next Task

**Perform fresh, read-only, non-implementing V2-3 TECH acceptance on this candidate commit.**

### Current Basis

- Branch: `workstream/v2-3-capability-modules`; the exact acceptance target is the candidate
  commit's `HEAD`, recorded first with `git rev-parse HEAD`.
- Authorized baseline: `c37969f6b6958e66474738f88a53b9d5c2f50d99`; this candidate includes
  preview, mixed simulation/replay/checkpoint, proofing, and generic SDK/CLI/Web integration complete.
- Focused capability/authoring/Web matrix passed `169 tests` and `480 subtests` on 2026-08-06.
- The full matrix passed: `unittest` `1565 OK (skipped=11)`; serial/xdist pytest both
  `1554 passed, 11 skipped, 927 subtests`; Ruff, Pyright, compileall, Demo validate, `pip check`,
  history safety, fsck, diff checks, and Windows packaging smoke passed.
- `git ls-remote` timed out, but GitHub REST confirmed live
  `main=ba729be8d80dbcbefe90a1dc801003deec7c4c95` and draft PR #1 head
  `c37969f6b6958e66474738f88a53b9d5c2f50d99`; no remote write occurred.

### Acceptance Steps

1. Inspect the exact candidate `HEAD`, baseline diff, documents, and verification evidence; do not edit,
   commit, move refs, query or write remotes, or access private material.
2. Independently reproduce evidence sufficient for any findings, then report P0-P3 findings first and
   end with exactly `GO` or `REVISE`.
3. Return reproducible `REVISE` findings to the implementation worktree. After `GO`, create only a
   documentation-only handoff seal; do not push, merge `main`, release, or enter V2-4/V2-5.

### Acceptance Criteria

- Empty `capability_requirement_ids` keeps V2-2 object types, canonical bytes, fingerprints, SDK/CLI
  envelopes, and Web snapshots byte-for-byte compatible.
- `reference_counter` preview, mixed simulation, events/views, checkpoint restore, replay, proofing, and
  generic SDK/CLI/Web transport have reproducible evidence.
- The candidate tree is clean, and fresh TECH acceptance returns `GO` or `REVISE` after findings.

### Pause and Boundaries

- Pause at the fresh-TECH-acceptance gate after this candidate commit.
- Do not push, move/merge `main`, release, distribute unsealed preview/report artifacts, access private
  material, or enter V2-4/V2-5. The Goal is incomplete and remains truthfully `active`; do not fake
  `blocked` or `complete`.

### Queue

1. Fresh read-only TECH acceptance for the candidate commit.
2. Documentation-only handoff seal only after `GO`.
3. Await separate PRODUCT/SECURITY/publication authorization; never infer main or release authority.
