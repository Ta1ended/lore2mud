# 下一任务 / Next Task

_最后更新 / Last updated: 2026-08-04_

## 中文

### 唯一下一门禁

**产品所有者对已取得全新独立 TECH GO 的精确 V2-1 候选作出 PRODUCT PASS 或退回。**

当前 Controller 会在本工作流内完成最终门禁、连贯本地提交和精确提交上的只读独立
TECH 验收，因此这些步骤不是交给下一会话的任务。本交接只有在 Controller 最终报告明确
记录 `GO` 时才可执行；若 verdict 为 `REVISE`，Controller 只能修复 findings 并请求新的
独立验收，不能把候选交给产品门禁。

### 产品检查范围

- 确认 `CLI/Web 解析 -> GameIntent -> GameSession -> TurnResult -> 传输层呈现` 是预期的
  公共运行时工作流。
- 确认 `World` 继续作为 V1 玩法权威，CLI/Web 的兼容表面和玩家体验满足产品意图。
- 确认玩家安全 view 的信息边界和具体 affordance 行为适合后续 Agent/客户端使用。
- 确认本地 V2-1 候选可以进入下一控制器决策；PRODUCT PASS 不自动授权 push、移动
  `main`、SECURITY PASS、release 或 V2-2。

### 所需证据

- Controller 最终报告中的基线、精确目标 SHA/范围、实际命令与结果、干净 Git 状态。
- 未参与实现的新任务对该精确目标给出的 findings-first `GO`。
- V2-1 改动路径、跨 CLI/Web 等价证据、拒绝不变性、save/runtime campaign/公开内容回归。

### 禁止越界

- 没有明确的新授权，不得 push、移动 `main`、release、开始 V2-2 或访问私有材料。
- 不得把 TECH GO 当作 PRODUCT PASS 或 SECURITY PASS。
- 不得在产品门禁中扩展 Capability、SDK、structured CLI、MCP、`SimulationReport`、
  proofing、迁移、插件、新内容或新 save 版本。

## English

### Single Next Gate

**The product owner accepts or returns the exact V2-1 candidate after it has received
a fresh independent TECH GO.**

The current controller completes the final gates, coherent local commit, and read-only
independent TECH acceptance of the exact commit inside this workstream, so those are
not tasks for the next session. This handoff is executable only if the controller's
final report records `GO`. If the verdict is `REVISE`, the controller may only repair
the findings and request a fresh independent acceptance; the candidate cannot advance
to the product gate.

### Product Review Scope

- Confirm that `CLI/Web parsing -> GameIntent -> GameSession -> TurnResult -> transport
  rendering` is the intended public runtime workflow.
- Confirm that `World` remains the V1 gameplay authority and that the compatible
  CLI/Web surfaces and player experience meet product intent.
- Confirm that the player-safe view boundary and concrete affordance behavior are
  suitable for later Agent/client use.
- Decide whether the local V2-1 candidate may enter the next controller decision.
  PRODUCT PASS does not automatically authorize push, `main` movement, SECURITY PASS,
  release, or V2-2.

### Required Evidence

- The controller report's baseline, exact target SHA/range, commands and results, and
  clean Git status.
- A findings-first `GO` on that exact target from a fresh task that did not implement it.
- V2-1 changed paths, CLI/Web equivalence, rejection invariance, and
  save/runtime-campaign/public-content regression evidence.

### Boundaries

- No push, `main` movement, release, V2-2 start, or private-material access without a
  new explicit authorization.
- TECH GO is not PRODUCT PASS or SECURITY PASS.
- The product gate cannot expand into Capability, SDK, structured CLI, MCP,
  `SimulationReport`, proofing, migrations, plugins, new content, or a new save version.
