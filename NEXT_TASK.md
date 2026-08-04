# 下一任务 / Next Task

_最后更新 / Last updated: 2026-08-04_

## 中文

### 唯一下一行动

**V2-1：设计并实现与传输方式无关的 `GameSession` 合同，用它包装现有 `World`，
但不拆分游戏玩法系统。**

此任务已路由但尚未开始。当前已独立验收并发布的在线 `main` 是
`564530d87aea17da26544b7793701e0dca0fe57d`。全新任务必须先核对实时引用和绿色
在线 `main` 证据，并确认该提交仍是预期顶端，或是后来已接受提交的祖先。如果存在
尚未审查的后续变更，必须停止并重新计算基线、范围与门禁，不能沿用本交接。
DEC-0088 路由 V2-1；DEC-0091 细化里程碑归属与参考模式。编辑前，先报告具体数据流、
精确改动路径、风险、非目标与验证计划。

### 权威数据流

```text
CLI/Web 解析 -> GameIntent -> GameSession -> TurnResult -> 传输层呈现
```

### 范围

- 在权威 `World` 外建立最小的强类型、传输无关会话/应用边界；CLI 与 Web 只保留各自的
  解析与呈现职责，不新增玩法规则。
- `GameIntent` 只是对现有引擎动作的强类型请求，不是插件 payload、直接状态补丁或可执行
  扩展。
- `GameSession` 包装现有 `World`，并返回包含合同状态、有序事件、当前玩家安全视图和最小
  运行时拒绝诊断的 `TurnResult`。
- `GameEvent` 是已接受转移产生的有序不可变事实，不是事件总线，也不是第二套事件溯源
  权威；V1 权威仍是 `World`。
- `GameView` 是当前回合完整的玩家安全投影；隐藏状态和不可用动作必须缺席，而不是以
  隐藏标记泄露。
- 畸形、不可采纳或其他合同层拒绝的 Intent 必须在权威状态改变前拒绝，不产生转移事件。
  已接受的动作仍可按现有 `World` 规则产生确定性的游戏内失败结果。
- 保持 V1 公开内容、save v9 写入、受支持的 v7/v8 读取、运行时战役行为、确定性结果和
  现有客户端可见行为。
- 增加聚焦的合同、拒绝不变性、CLI、Web、内容和存档回归，然后运行完整 TECH 与仓库
  安全矩阵。

### 非目标

- 不做 Capability、`CapabilityDescriptor`、静态能力目录或能力解析。
- 不做 `GameBlueprint`、`GameProject`、`AuthoringDiagnostic`、`SimulationReport`、
  通用 `admissible_intents` 创作接口、SDK、structured CLI、MCP 或 proofing 表示。
- 不做插件、生成代码、迁移、新依赖/框架、新内容或存档版本。
- 不创建新 Demo，不访问、改编、检查或发布私有材料。
- 不整体分解 `World`，不重写玩法系统，不开始 V2-2。
- 本实现切片不 push、不移动 `main`、不 release 或 publish。

### 验收与门禁

- CLI 与 Web 共用一个应用/会话层；`World` 仍是权威兼容实现。
- 相同内容/包、权威状态、时钟、种子和 Intent 序列，跨传输方式产生等价的 `status`、
  有序 events、玩家安全 view 和保存状态。
- 合同层拒绝不产生转移事件。拒绝前后的规范化可持久化权威状态字节或哈希完全一致，
  包括玩法状态、RNG 位置、时钟、事件序列和存档可见元数据。
- 已接受动作的确定性游戏内失败结果继续兼容，不被错误改写成合同拒绝。
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

This task is routed but not started. The current independently accepted and published
live `main` is `564530d87aea17da26544b7793701e0dca0fe57d`. A fresh task must first
check live refs and green live-`main` evidence, then confirm that commit remains the
expected tip or is an ancestor of later accepted commits. If later unreviewed changes
exist, stop and recompute the baseline, scope, and gates instead of using this handoff.
DEC-0088 routes V2-1; DEC-0091 refines milestone ownership and reference patterns.
Before editing, report the concrete data flow, exact changed paths, risks, non-goals,
and verification plan.

### Authoritative Data Flow

```text
CLI/Web parsing -> GameIntent -> GameSession -> TurnResult -> transport rendering
```

### Scope

- Establish the smallest typed, transport-neutral session/application boundary around
  authoritative `World`; CLI and Web retain parsing/rendering responsibilities only
  and add no gameplay rules.
- `GameIntent` is a typed request for an existing engine action, not a plugin payload,
  direct state patch, or executable extension.
- `GameSession` wraps existing `World` and returns a `TurnResult` containing contract
  status, ordered events, the current player-safe view, and minimal runtime rejection
  diagnostics.
- `GameEvent` is an ordered immutable fact from an accepted transition, not an event
  bus or a second event-sourced authority; `World` remains the V1 authority.
- `GameView` is the complete player-safe projection for the current turn. Hidden state
  and unavailable actions are absent rather than leaked through hidden flags.
- A malformed, inadmissible, or otherwise contract-rejected intent must reject before
  authoritative mutation and produce no transition events. An accepted action may
  still produce a deterministic unsuccessful in-world outcome under existing `World`
  rules.
- Preserve V1 public content, save v9 writes, supported v7/v8 reads, runtime campaign
  behavior, deterministic outcomes, and existing client-visible behavior.
- Add focused contract, rejection-invariance, CLI, Web, content, and save regressions,
  then run the full TECH and repository-safety matrix.

### Non-Goals

- No Capability, `CapabilityDescriptor`, static capability catalog, or capability
  resolution.
- No `GameBlueprint`, `GameProject`, `AuthoringDiagnostic`, `SimulationReport`, general
  authoring `admissible_intents` interface, SDK, structured CLI, MCP, or proofing
  representation.
- No plugins, generated code, migrations, new dependency/framework, or new content/save
  version.
- No new Demo and no access, adaptation, inspection, or publication of private material.
- No wholesale `World` decomposition, gameplay-system rewrite, or V2-2 work.
- No push, `main` movement, release, or publication in this implementation slice.

### Acceptance And Gates

- CLI and Web share one application/session layer; `World` remains the authoritative
  compatibility implementation.
- Identical content/package, authoritative state, clock, seed, and intent sequence
  produce equivalent `status`, ordered events, player-safe view, and saved state across
  transports.
- Contract rejection produces no transition events. Canonical persistable authoritative
  state bytes or hashes are identical before and after rejection, including gameplay
  state, RNG position, clock, event sequence, and save-visible metadata.
- Deterministic unsuccessful in-world outcomes from accepted actions remain compatible
  and are not incorrectly rewritten as contract rejection.
- Existing public content and supported saves do not regress.
- Every implementation, architecture, and acceptance task or subagent must explicitly
  use `gpt-5.6-sol` with reasoning `xhigh` or higher. Stop if unavailable; never
  silently downgrade.
- Implementation cannot self-approve. Obtain a fresh findings-first independent TECH
  decision for the exact commit/range; keep PRODUCT and SECURITY decisions separate
  and owner-controlled. Commit, push, `main` movement, and release remain separate
  controller gates.
