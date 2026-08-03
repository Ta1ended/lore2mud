# 下一任务 / Next Task

_最后更新 / Last updated: 2026-08-03_

## 中文

### 唯一下一行动

**V2-1：设计并实现与传输方式无关的 `GameSession` 合同，用它包装现有 `World`，
但不拆分游戏玩法系统。**

此任务已路由但尚未开始。V2-0 已接受并发布的最终目标是
`077b8eb568f193b0b3ccab47410bec35dc4c2a9c`。全新任务必须先核对当前引用和绿色的
在线 `main` 证据，并确认该提交是预期的在线 `main` 顶端，或是后来已接受提交的祖先。
如果存在尚未审查的后续变更，必须停止并重新计算基线、范围与门禁，不能沿用本交接。
DEC-0088 记录产品方向；DEC-0089 记录双语交接维护政策。编辑前，先报告具体数据流、
精确改动路径、风险、非目标与验证计划。

### 范围

- 在权威 `World` 外建立最小的强类型、传输无关会话/应用边界。
- 仅按此边界所需定义确定性的 `GameIntent`、`TurnResult`、`GameEvent` 和玩家安全的
  `GameView`；无效意图必须在持久状态改变前被拒绝。
- 让 CLI 与 Web 的回合行为经过同一会话层，同时保留各自的解析与呈现职责。
- 保持 V1 公开内容、save v9 与受支持的 v7/v8 读取、运行时战役行为、确定性结果和
  现有客户端可见行为。
- 增加聚焦的合同、失败不变性、CLI、Web、内容和存档回归，然后运行完整 TECH 与
  仓库安全矩阵。

### 非目标

- 不做 Capability 或 `CapabilityDescriptor`、SDK、MCP、插件、生成代码或新依赖/框架。
- 不创建新 Demo，不访问、改编、检查或发布私有材料。
- 不整体分解 `World`，不重写玩法系统，不改变内容/存档版本，不开始 V2-2。
- 本实现切片不 push、不移动 `main`、不 release 或 publish。

### 验收与门禁

- CLI 与 Web 共用一个应用/会话层，不新增玩法规则；`World` 仍是权威兼容实现。
- 相同内容、状态、时钟/种子输入和意图序列，跨传输方式产生等价的结果、事件、视图和
  存档状态；失败意图不改变权威状态。
- 现有公开内容和受支持存档不得回归。
- 所有实现、架构和验收任务或子 Agent 必须明确使用 `gpt-5.6-sol`，reasoning 为
  `xhigh` 或更高；不可用时停止，不可静默降级。
- 实现不得自我批准。对精确提交/范围取得一次全新、先列发现的独立 TECH 决定；PRODUCT
  与 SECURITY 决定继续分离并由所有者控制。提交、push、移动 `main` 和 release 仍是
  分开的控制器门禁。

## English

### Single Next Action

**V2-1: design and implement a transport-neutral `GameSession` contract that wraps
the existing `World` without splitting gameplay systems.**

This task is routed but not started. The accepted and published V2-0 final target is
`077b8eb568f193b0b3ccab47410bec35dc4c2a9c`. A fresh task must first check current
refs and green live-`main` evidence, then confirm that commit is the expected live-main
tip or an ancestor of later accepted commits. If later unreviewed changes exist, stop
and recompute the baseline, scope, and gates instead of using this handoff. DEC-0088
records product direction; DEC-0089 records the bilingual handoff maintenance policy.
Before editing, report the concrete data flow, exact changed paths, risks, non-goals,
and verification plan.

### Scope

- Establish the smallest typed, transport-neutral session/application boundary around
  the authoritative `World`.
- Define deterministic `GameIntent`, `TurnResult`, `GameEvent`, and player-safe
  `GameView` values only as needed by that boundary; invalid intents must reject before
  durable state mutation.
- Route CLI and Web turn behavior through one shared session layer while preserving
  their transport-specific parsing and rendering responsibilities.
- Preserve V1 public content, save v9 plus supported v7/v8 reads, runtime campaign
  behavior, deterministic outcomes, and existing client-visible behavior.
- Add focused contract, failure-invariance, CLI, Web, content, and save regressions,
  then run the full TECH and repository-safety matrix.

### Non-Goals

- No Capability or `CapabilityDescriptor` work, SDK, MCP, plugins, generated code, or
  new dependency/framework.
- No new Demo and no access, adaptation, inspection, or publication of private material.
- No wholesale `World` decomposition, gameplay-system rewrite, content/save version
  change, or V2-2 work.
- No push, `main` movement, release, or publication in this implementation slice.

### Acceptance And Gates

- CLI and Web share one application/session layer and gain no new gameplay rules;
  `World` remains the authoritative compatibility implementation.
- Identical content, state, clock/seed inputs, and intent sequences produce equivalent
  results, events, views, and saved state across transports; failed intents leave
  authoritative state unchanged.
- Existing public content and supported saves do not regress.
- Every implementation, architecture, and acceptance task or subagent must explicitly
  use `gpt-5.6-sol` with reasoning `xhigh` or higher. Stop if unavailable; never
  silently downgrade.
- Implementation cannot self-approve. Obtain a fresh findings-first independent TECH
  decision for the exact commit/range; keep PRODUCT and SECURITY decisions separate
  and owner-controlled. Commit, push, `main` movement, and release remain separate
  controller gates.
