# 下一任务 / Next Task

更新日期：2026-08-06

## 中文

### 唯一下一任务

**产品负责人审核本 planning PR 后，由一个全新的 Codex 会话执行 `docs/v2/v2_3_goal.md`，实现 V2-3 Capability Module Architecture。**

### 为什么现在做

- V2-2 精确产品候选已完成 TECH、PRODUCT 和 SECURITY 门禁。
- integration candidate `c37969f6b6958e66474738f88a53b9d5c2f50d99` 与 V2-2 tree 字节一致，PR #1 当前 clean、Draft、exact-head CI 绿色。
- 产品负责人已于 2026-08-06 明确授权开始 V2-3 开发，但要求先审核本 Goal，再交给新的 Codex 会话。

### 输入

- `docs/v2/v2_3_goal.md`
- `AGENTS.md`
- `PRODUCT.md`
- `PROJECT_STATE.md`
- `CODE_MAP.md`
- `docs/v2/architecture.md`
- `docs/v2/roadmap.md`
- `docs/v2/reference_patterns.md`
- `docs/v2/development_model.md`
- V2-2 integration candidate `c37969f6b6958e66474738f88a53b9d5c2f50d99`

### 步骤

1. 产品负责人审核本 planning PR 的 baseline、合同、非目标、模块归属、验证矩阵和停止规则。
2. 审核通过后，把 `docs/v2/v2_3_goal.md` 完整交给一个新的 Codex 会话。
3. 新会话立即创建 Goal，重新核对 live `main`、PR #1、Actions、祖先和 `uv.lock`，再按 Goal 在隔离 worktree 中执行。
4. 如果 `main` 已包含 `c37969f`，从实时绿色 `main` 开始；如果 PR #1 仍未合并但 exact `c37969f` 仍绿色，可从它创建 stacked V2-3 workstream，不得移动 `main`。
5. 完成 V2-3 产品候选、完整验证和全新只读 independent TECH acceptance 后停止，等待人类 PRODUCT PASS。

### 验收标准

- 新会话使用自包含 Goal，不依赖当前聊天历史。
- V2-3 只实现 engine-shipped static capability catalog、deterministic resolution、namespaced runtime、reference capability、checkpoint 和共享 SDK/CLI；不进入 V2-4/V2-5。
- 空 capability requirement 路径保持 V2-2 canonical bytes、fingerprints 和兼容行为。
- 最终候选获得 findings-first P0-P3 独立验收与唯一 `GO` 或 `REVISE` verdict。

### 如果阻塞

- 远端查询失败：报告 live evidence 不可用，不得使用本地 `origin/*` 代替。
- PR #1、integration tree 或 Actions 漂移：停止并由 Controller 重新计算 baseline。
- planning PR 未获产品负责人审核：不得启动 V2-3 实现。

### 队列

1. V2-3 PRODUCT PASS、SECURITY PASS 和 publication 均为产品候选完成后的独立门禁。
2. `main` integration 和 release 需要单独授权。
3. V2-4 仍未授权。

## English

### Single Next Task

**After product-owner review of this planning PR, a fresh Codex session executes `docs/v2/v2_3_goal.md` to implement the V2-3 Capability Module Architecture.**

### Why Now

- The exact V2-2 product candidate has completed TECH, PRODUCT, and SECURITY gates.
- Integration candidate `c37969f6b6958e66474738f88a53b9d5c2f50d99` is byte-identical to the V2-2 tree; PR #1 is currently clean, Draft, and green on exact-head CI.
- On 2026-08-06 the product owner explicitly authorized V2-3 development, while requiring review of this Goal before transfer to a fresh Codex session.

### Inputs

- `docs/v2/v2_3_goal.md`
- `AGENTS.md`
- `PRODUCT.md`
- `PROJECT_STATE.md`
- `CODE_MAP.md`
- `docs/v2/architecture.md`
- `docs/v2/roadmap.md`
- `docs/v2/reference_patterns.md`
- `docs/v2/development_model.md`
- V2-2 integration candidate `c37969f6b6958e66474738f88a53b9d5c2f50d99`

### Steps

1. The product owner reviews the planning PR baseline, contracts, non-goals, ownership, validation matrix, and stop rules.
2. After approval, transfer the complete `docs/v2/v2_3_goal.md` to a fresh Codex session.
3. The fresh session immediately creates a Goal, rechecks live `main`, PR #1, Actions, ancestry, and `uv.lock`, then executes in an isolated worktree.
4. If `main` contains `c37969f`, start from live green `main`. If PR #1 remains unmerged but exact `c37969f` remains green, start a stacked V2-3 workstream from it without moving `main`.
5. Stop after the V2-3 product candidate, full verification, and fresh read-only independent TECH acceptance; wait for human PRODUCT PASS.

### Acceptance Criteria

- The fresh session uses a self-contained Goal and does not depend on this chat history.
- V2-3 implements only the engine-shipped static capability catalog, deterministic resolution, namespaced runtime, reference capability, checkpoint, and shared SDK/CLI; it does not enter V2-4 or V2-5.
- The empty-capability path preserves V2-2 canonical bytes, fingerprints, and compatibility behavior.
- The final candidate receives findings-first P0-P3 independent acceptance ending in exactly `GO` or `REVISE`.

### If Blocked

- Remote query failure: report live evidence unavailable and do not substitute local `origin/*`.
- PR #1, integration tree, or Actions drift: stop and have the Controller recalculate the baseline.
- Planning PR not yet approved by the product owner: do not start V2-3 implementation.

### Queue

1. V2-3 PRODUCT PASS, SECURITY PASS, and publication remain separate gates after the product candidate.
2. `main` integration and release require separate authorization.
3. V2-4 remains unauthorized.
