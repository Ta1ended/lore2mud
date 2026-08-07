# 下一任务 / Next Task

更新日期：2026-08-07

## 中文

### 唯一下一任务

**等待独立 PRODUCT PASS 与 SECURITY PASS，并在两者完成后等待明确 release 授权；V2-3 workstream 已发布并合并到 `main`，不再重复远端操作。**

### 当前依据

- 分支：`workstream/v2-3-capability-modules`；精确技术候选为
  `aa56770ccbefa77ab405ef5739dab769e6536592`，基线为
  `c37969f6b6958e66474738f88a53b9d5c2f50d99`。
- 全新只读 TECH acceptance 已在该 SHA 上独立复现 1,024/1,025 边界，P0-P3 全空并给出 `GO`；本地
  documentation-only handoff seal 已记录该 verdict。
- 授权基线：`c37969f6b6958e66474738f88a53b9d5c2f50d99`；本候选已完成 preview、
  mixed simulation/replay/checkpoint、proofing、SDK/CLI/Web 通用集成。
- 当前修复验证：边界回归 `13 passed`；发布前最终 xdist pytest 为
  `1564 passed, 2 skipped, 927 subtests passed`；PyInstaller packaging 聚焦矩阵为 `17 passed, 12 subtests passed`。
- Ruff、Pyright、compileall、Demo validate、`pip check`、history safety、fsck 和两类 diff checks 均通过。
  独立 reviewer 的早期验收记录保留 12 个工具缺口 skip；最终全量剩余的 2 个 skip 是 POSIX-only symlink 测试。
- 发布前 live ref 核对确认 `main` 与 V2-3 workstream 均为
  `26fe8428d39f366e068ba7986975322e72d0f355`；该发布操作随后正常完成，旧 PR/旧 main 快照不再是当前状态依据。
- 产品负责人于 2026-08-07 明确授权 push 与合并 `main`；documentation seal
  `26fe8428d39f366e068ba7986975322e72d0f355` 已正常快进发布到
  `origin/workstream/v2-3-capability-modules` 与 `origin/main`，发布操作完成时两个 ref 精确一致。
- 对精确 `26fe842` 的 GitHub Actions tests `31156995926`、`31156931379` 与 quality `31156995982`、`31156931281`
  均为 `completed/success`；发布前最终 xdist pytest 为 `1564 passed, 2 skipped, 927 subtests passed`，
  PyInstaller packaging 为 `17 passed, 12 subtests passed`，Windows symbolic-link 手工检查成功。

### 当前边界

- TECH `GO` 加上已完成的 workstream 发布与 `main` 合并，仍不等于 PRODUCT PASS、SECURITY PASS、release 或分发授权。
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

- 本 Goal 的 V2-3 TECH、documentation-only seal、workstream 发布与 `main` 合并均已完成；保持产品候选冻结，
  不自动执行后续授权门槛。
- 不 release、不分发 unsealed preview/report、不访问私人材料、不进入 V2-4/V2-5；`uv.lock` 仍为主工作树用户保留文件。

### 后续队列

1. 等待独立 PRODUCT PASS、SECURITY PASS 与明确 release 授权；在此之前不执行 release、分发或后续里程碑。

## English

### Single Next Task

**Await independent PRODUCT PASS and SECURITY PASS, then explicit release authorization; the V2-3 workstream is already published and merged to `main`, so do not repeat remote operations.**

### Current Basis

- Branch: `workstream/v2-3-capability-modules`; exact technical candidate
  `aa56770ccbefa77ab405ef5739dab769e6536592`, baseline
  `c37969f6b6958e66474738f88a53b9d5c2f50d99`.
- Fresh read-only TECH acceptance on that SHA independently reproduced the 1,024/1,025 boundary, found P0-P3 empty,
  and returned `GO`; the local documentation-only handoff seal records it.
- Authorized baseline: `c37969f6b6958e66474738f88a53b9d5c2f50d99`; this candidate includes
  preview, mixed simulation/replay/checkpoint, proofing, and generic SDK/CLI/Web integration complete.
- Current repair verification: boundary regression `13 passed`; final pre-publication xdist pytest was
  `1564 passed, 2 skipped, 927 subtests passed`; focused PyInstaller packaging passed `17` tests and `12` subtests.
- Ruff, Pyright, compileall, Demo validation, `pip check`, history safety, fsck, and both diff checks passed.
  The independent review's earlier 12 skips were tool-gap evidence; the two remaining full-suite skips are POSIX-only
  symlink tests, and manual Windows symbolic-link creation succeeded.
- The live pre-publication ref check found both `main` and the V2-3 workstream at
  `26fe8428d39f366e068ba7986975322e72d0f355`; publication then completed normally, so the older draft-PR snapshot is
  historical rather than current.
- The product owner explicitly authorized push and `main` integration on 2026-08-07. Documentation seal
  `26fe8428d39f366e068ba7986975322e72d0f355` was normally fast-forwarded to both
  `origin/workstream/v2-3-capability-modules` and `origin/main`, which matched exactly when publication completed.
- Exact-head Actions tests `31156995926`/`31156931379` and quality `31156995982`/`31156931281` all completed successfully;
  the final pre-publication local xdist matrix was `1564 passed, 2 skipped, 927 subtests passed`, focused packaging was
  `17 passed, 12 subtests passed`, and manual Windows symbolic-link creation succeeded.

### Current Boundaries

- TECH `GO` plus completed workstream publication and `main` integration still does not grant PRODUCT PASS, SECURITY PASS,
  release, or distribution authority.
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

- This Goal's V2-3 TECH acceptance, documentation-only seal, workstream publication, and `main` integration are complete;
  keep the candidate frozen and take no automatic action across later gates.
- Do not release, distribute unsealed preview/report artifacts, access private material, or enter V2-4/V2-5.

### Queue

1. Await independent PRODUCT PASS, SECURITY PASS, and explicit release authorization; before then, do not release, distribute,
   or start a later milestone.
