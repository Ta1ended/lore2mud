# 下一任务 / Next Task

更新日期：2026-08-07

## 中文

### 唯一下一任务

**在提交本修复后的替代候选后，对其精确 SHA 执行 fresh、read-only、未参与实现的 V2-3 TECH acceptance。**

### 当前依据

- 分支：`workstream/v2-3-capability-modules`；此前候选
  `14954070238ec6e3f2255b1c18d31214b3172d49` 的独立 TECH verdict 是 `REVISE`。其唯一 P2 是
  runtime 接受 1,025 个 `admissible_intents`，而公开 Schema 上限为 1,024；不得复用该 verdict 或 reviewer。
- 修复后的替代候选必须以 `git rev-parse HEAD` 记录精确 SHA：generic runtime 在 player-safe view 输出前
  拒绝超过 1,024 项的 capability projection，1,024/1,025 回归证明拒绝不改变 capability state 或 event sequence。
- 授权基线：`c37969f6b6958e66474738f88a53b9d5c2f50d99`；本候选已完成 preview、
  mixed simulation/replay/checkpoint、proofing、SDK/CLI/Web 通用集成。
- 当前修复验证：边界回归 `13 passed`；`unittest` `1566 OK (skipped=12)`；serial pytest
  `1554 passed, 12 skipped`；xdist pytest `1554 passed, 12 skipped, 924 subtests passed`。
- Ruff、Pyright、compileall、Demo validate、`pip check`、history safety、fsck 和两类 diff checks 均通过。
  12 个 skip 是本机缺少 PyInstaller toolchain 及 Windows symlink 权限，验收报告必须准确保留为 skip。
- `git ls-remote` 超时，但 GitHub REST 已确认 live `main=ba729be8d80dbcbefe90a1dc801003deec7c4c95`，
  PR #1 是 head `c37969f6b6958e66474738f88a53b9d5c2f50d99` 的 draft；没有 remote write。

### 验收步骤

1. 由一个不同于 `1495407` 旧验收者的新任务，从精确替代候选 `HEAD` 读取代码、基线 diff、文档和验证证据；不编辑、不提交、不移动 refs、
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
- Schema/runtime 都对 `admissible_intents` 执行相同的 1,024 上限；1,025 项 projection 在 public output 前
  拒绝且保持 capability state/event sequence 不变。
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

**After committing this repaired replacement candidate, perform fresh, read-only, non-implementing V2-3 TECH acceptance on its exact SHA.**

### Current Basis

- Branch: `workstream/v2-3-capability-modules`; prior candidate
  `14954070238ec6e3f2255b1c18d31214b3172d49` received independent TECH `REVISE`. Its sole P2 was that
  runtime accepted 1,025 `admissible_intents` while the public Schema caps them at 1,024; do not reuse its verdict or reviewer.
- Record the repaired replacement candidate's exact SHA with `git rev-parse HEAD`: the generic runtime rejects a
  capability projection over 1,024 entries before player-safe view output, and 1,024/1,025 regression coverage
  proves rejection does not alter capability state or the event sequence.
- Authorized baseline: `c37969f6b6958e66474738f88a53b9d5c2f50d99`; this candidate includes
  preview, mixed simulation/replay/checkpoint, proofing, and generic SDK/CLI/Web integration complete.
- Current repair verification: boundary regression `13 passed`; `unittest` `1566 OK (skipped=12)`;
  serial pytest `1554 passed, 12 skipped`; xdist pytest `1554 passed, 12 skipped, 924 subtests passed`.
- Ruff, Pyright, compileall, Demo validation, `pip check`, history safety, fsck, and both diff checks passed.
  The 12 skips are the local absence of the PyInstaller toolchain and Windows symlink privilege, and the acceptance
  report must preserve them as skips.
- `git ls-remote` timed out, but GitHub REST confirmed live
  `main=ba729be8d80dbcbefe90a1dc801003deec7c4c95` and draft PR #1 head
  `c37969f6b6958e66474738f88a53b9d5c2f50d99`; no remote write occurred.

### Acceptance Steps

1. A new task, different from the prior `1495407` reviewer, inspects the exact replacement candidate `HEAD`,
   baseline diff, documents, and verification evidence; do not edit,
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
- Schema and runtime enforce the same 1,024-item `admissible_intents` limit; a 1,025-item projection rejects before
  public output while capability state and the event sequence remain unchanged.
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
