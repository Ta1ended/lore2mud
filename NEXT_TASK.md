# 下一任务 / Next Task

更新日期：2026-08-07

## 中文

### 唯一下一任务

**等待独立 PRODUCT PASS、SECURITY PASS 或明确的 workstream 发布授权；在获得授权前不执行任何远端或后续里程碑操作。**

### 当前依据

- 分支：`workstream/v2-3-capability-modules`；精确技术候选为
  `aa56770ccbefa77ab405ef5739dab769e6536592`，基线为
  `c37969f6b6958e66474738f88a53b9d5c2f50d99`。
- 全新只读 TECH acceptance 已在该 SHA 上独立复现 1,024/1,025 边界，P0-P3 全空并给出 `GO`；本地
  documentation-only handoff seal 已记录该 verdict。
- 授权基线：`c37969f6b6958e66474738f88a53b9d5c2f50d99`；本候选已完成 preview、
  mixed simulation/replay/checkpoint、proofing、SDK/CLI/Web 通用集成。
- 当前修复验证：边界回归 `13 passed`；`unittest` `1566 OK (skipped=12)`；serial pytest
  `1554 passed, 12 skipped`；xdist pytest `1554 passed, 12 skipped, 924 subtests passed`。
- Ruff、Pyright、compileall、Demo validate、`pip check`、history safety、fsck 和两类 diff checks 均通过。
  12 个 skip 是本机缺少 PyInstaller toolchain 及 Windows symlink 权限，验收报告必须准确保留为 skip。
- `git ls-remote` 超时，但 GitHub REST 已确认 live `main=ba729be8d80dbcbefe90a1dc801003deec7c4c95`，
  PR #1 是 head `c37969f6b6958e66474738f88a53b9d5c2f50d99` 的 draft；没有 remote write。

### 当前边界

- TECH `GO` 只封存 V2-3 技术候选，不等于 PRODUCT PASS、SECURITY PASS、workstream push、`main` 移动/合并或 release。
- 不分发 unsealed preview/report，不访问私人材料，不进入 V2-4/V2-5；任何后续动作都必须等待对应明确授权。

### 已完成证据

- 空 `capability_requirement_ids` 的 V2-2 object type、canonical bytes、fingerprints、SDK/CLI
  envelopes 与 Web snapshots 保持 byte-for-byte 兼容。
- `reference_counter` capability 的 preview、mixed simulation、events/views、checkpoint
  restore、replay、proofing、SDK/CLI/Web generic transport 均有可复现证据。
- Schema/runtime 都对 `admissible_intents` 执行相同的 1,024 上限；1,025 项 projection 在 public output 前
  拒绝且保持 capability state/event sequence 不变。
- `aa56770` 候选及本 seal 提交后工作树必须保持干净；独立 findings-first TECH verdict 为 P0-P3 全空 `GO`。

### 暂停与边界

- 本 Goal 的 V2-3 TECH 与 documentation-only seal 已完成；保持候选冻结，不自动执行任何后续授权门槛。
- 不 push、不移动或合并 `main`、不 release、不分发 unsealed preview/report、不访问私人材料、不进入 V2-4/V2-5。

### 后续队列

1. 等待明确 PRODUCT PASS、SECURITY PASS 或 workstream 发布授权。
2. 只有获得对应授权后，另行执行被授权的动作；不自动推进 `main` 或 release。

## English

### Single Next Task

**Await explicit PRODUCT PASS, SECURITY PASS, or workstream-publication authorization; take no remote or later-milestone action before it arrives.**

### Current Basis

- Branch: `workstream/v2-3-capability-modules`; exact technical candidate
  `aa56770ccbefa77ab405ef5739dab769e6536592`, baseline
  `c37969f6b6958e66474738f88a53b9d5c2f50d99`.
- Fresh read-only TECH acceptance on that SHA independently reproduced the 1,024/1,025 boundary, found P0-P3 empty,
  and returned `GO`; the local documentation-only handoff seal records it.
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

### Current Boundaries

- TECH `GO` freezes the V2-3 technical candidate only; it does not grant PRODUCT PASS, SECURITY PASS, workstream push,
  `main` movement/merge, or release authority.
- Do not distribute unsealed preview/report artifacts, access private material, or enter V2-4/V2-5; every later action
  waits for its own explicit authorization.

### Completed Evidence

- Empty `capability_requirement_ids` keeps V2-2 object types, canonical bytes, fingerprints, SDK/CLI
  envelopes, and Web snapshots byte-for-byte compatible.
- `reference_counter` preview, mixed simulation, events/views, checkpoint restore, replay, proofing, and
  generic SDK/CLI/Web transport have reproducible evidence.
- Schema and runtime enforce the same 1,024-item `admissible_intents` limit; a 1,025-item projection rejects before
  public output while capability state and the event sequence remain unchanged.
- The `aa56770` candidate and documentation-only seal leave a clean tree; the independent findings-first TECH verdict is
  P0-P3 empty `GO`.

### Pause and Boundaries

- This Goal's V2-3 TECH acceptance and documentation-only seal are complete; keep the candidate frozen and take no
  automatic action across later gates.
- Do not push, move/merge `main`, release, distribute unsealed preview/report artifacts, access private material, or
  enter V2-4/V2-5.

### Queue

1. Await explicit PRODUCT PASS, SECURITY PASS, or workstream-publication authorization.
2. Only after the corresponding authorization may a separately scoped action run; never infer `main` or release authority.
