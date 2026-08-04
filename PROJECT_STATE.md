# 项目状态 / Project State

_最后更新 / Last updated: 2026-08-04_

## 中文

### 目标

交付一个可由 Agent 调用的小说转文字游戏引擎：创作平面生成经过验证、可追溯的包，
确定性运行时平面负责执行，同时保持 V1 兼容性以及严格的公开/私有和权利边界。

### 当前状态

- 已核对的在线公开 `main` 是
  `564530d87aea17da26544b7793701e0dca0fe57d`；GitHub Actions tests
  `30846680303` 与 quality `30846680343` 成功。
- V2-1 隔离候选位于 `workstream/v2-1-game-session`，基于已获规划 TECH GO 的
  `1d4b26d9127d4229893911cf260cf3c2f4b0ce3a`。共享 `main` 未移动，没有 push、
  release 或 V2-2 工作。
- `src/lore2mud/application/` 已实现本地候选的 `GameIntent`、`GameSession`、
  `GameEvent`、`GameView` 和 `TurnResult`；`World` 仍是唯一玩法权威，CLI 与 Web
  保留解析和呈现职责。
- Controller 全量门禁已完成；本工作流只可继续创建连贯本地提交并对精确提交执行独立
  只读 TECH 验收。本文件不自我授予 TECH、PRODUCT 或 SECURITY PASS；最终 TECH
  verdict 只以本工作流的独立验收记录和 Controller 最终报告为准。

### 已实现

- 强类型冻结合同、确定性上下文、有序事件序列、typed 拒绝诊断和完整玩家安全投影。
- 只接受已声明的精确 Intent 类型及精确的 `str`、`int`、Enum 叶值；CLI/Web 在调用任何
  可重载方法或运算符前完成同一合同校验，恶意原始类型子类不能越过状态快照边界。
- 合同拒绝会恢复原 `World` 身份及规范化可持久化状态、RNG 位置、时钟输入和事件序列，
  且不产生转移事件；意外异常在恢复后继续上抛。
- `WorldRuleError`/`SaveLoadError` 的诊断先完成规范化，再在 `finally` 中执行最终恢复并投影
  view；异常对象的可重载格式化不能在回滚后重新改变权威状态。
- 拒绝快照保留原 `DeterminismContext` 身份及精确 `seed/clock`；即使冻结值被低层
  `object.__setattr__` 原地篡改，也会在返回或重新上抛前恢复同一对象及原值。
- `CommandProcessor` 保持兼容构造和动态 `.world`，但玩法 handler 只提交 Intent 并从
  `TurnResult`/`GameView` 呈现；Web `PlayerSession` 保持名称但包装同一应用会话。
- CLI 对话的当前编号菜单只从玩家安全 `GameView.dialogue.options` 呈现；有序 dialogue event
  继续记录转移事实，不能重新引入投影已判定不可执行的选项。
- Web JSON 新增 `status/events/view/diagnostics`，同时保留 `ok/event/snapshot`；浏览器从
  投影的具体 affordance 取得可用动作，不再复制锁、死亡、物品、交易、对话或战役规则。
- 兼容 `snapshot` 保留 V1 已有的显式空值字段；新的玩家安全 `view` 仍让不可用动作缺席。
  兼容 `event.data` 也从 typed event 恢复完整 V1 room、campaign effect 和显式空值形状。
  房间物品、怪物、角色及 campaign action 继续按内容声明顺序投影，CLI/Web 不会因
  V2-1 按 ID 重排。
- save v9 写入、v7/v8 读取门禁、内容 Schema/版本、公开 Demo 和 runtime campaign 格式
  均未改变。

### 验证状态

- 针对 Web 兼容形状、typed campaign effects 和 V1 可见顺序 findings 的聚焦回归：
  49 passed。
- `.venv\Scripts\python.exe -m unittest discover`：1414 tests，11 skipped，OK。
- 恢复开发后的第一次 `unittest discover` 未显式绑定隔离 worktree 的 `src`，因此项目
  `.venv` 的主仓库 editable install 混入旧模块并失败；设置 `PYTHONPATH=<worktree>/src`
  后同一完整命令通过。该失败准确保留为 harness 配置问题，不计作代码通过证据。
- `.venv\Scripts\python.exe -m pytest -q`：1403 passed，11 skipped；同一套件以
  `-n auto` 在显式仓库外 TEMP/TMP 与 `--basetemp` 下重跑：1403 passed，11 skipped。
  第一次 xdist 启动在用户 pytest 临时根目录遇到 `WinError 5`，未进入收集，已按 harness
  问题准确保留并由成功重跑关闭。
- `ruff check .`、`pyright`、`compileall -q src pipeline scripts tests`、
  `lore2mud validate --content examples/original_demo`、
  `check_repo_safety.py --history`、`git fsck --full --no-dangling`、working/staged
  `git diff --check` 均通过。
- Windows PyInstaller 与 zipapp 的构建、包内容和仓库外冷启动由全量测试真实覆盖。
- 独立验收不由本实现上下文自我决定；精确 verdict 见 Controller 最终报告。

### 角色与模型

- Controller/Implementation：当前根任务，负责接口冻结、集成、测试、提交和门禁。
- Product/Specification：只读验收矩阵；Architect/Engine Lead：只读运行时、存档和客户端
  边界检查。两者继承当前任务模型，工具未暴露更细的模型标识。
- Independent Acceptance：必须是未参与实现的新任务，严格只读审查精确提交。模型输出
  不是证据，结论必须由代码、测试和 Git 证据支撑。

### 保持的边界

- 私有源文本、canon、派生改编、图片、存档和报告不得访问或进入公开 Git。
- 不新增依赖，不改变 Schema、内容包版本或 save 格式，不实现 Capability、SDK、
  structured CLI、MCP、`SimulationReport`、proofing、迁移、插件、新 Demo 或 V2-2。
- 主检出目录的未跟踪 `uv.lock` 保持 14,471 字节，SHA-256
  `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`；隔离
  worktree 中不得出现该文件。

### 剩余风险

- 当前 V1 规则不消费 `DeterminismContext` 的 RNG/时钟；合同已保留并测试其拒绝不变性，
  但未来真正消费这些输入时仍需新的可观察确定性测试。
- 玩家 affordance 通过隔离 `deepcopy(World)` 探测现有规则，范围明确且不建立 V2-2
  通用动作目录，但大型内容包的性能仍需后续实测。
- `World`、loader、save 和传统命令渲染仍较大；V2-1 不授权整体拆分。

## English

### Objective

Deliver an Agent-callable novel-to-text-game engine whose Authoring Plane produces
validated, traceable packages for a deterministic Runtime Plane, while preserving V1
compatibility and strict public/private and rights boundaries.

### Current Status

- Verified live public `main` is
  `564530d87aea17da26544b7793701e0dca0fe57d`; GitHub Actions tests
  `30846680303` and quality `30846680343` succeeded.
- The isolated V2-1 candidate is on `workstream/v2-1-game-session`, based on the
  planning TECH-GO commit `1d4b26d9127d4229893911cf260cf3c2f4b0ce3a`.
  Shared `main` has not moved; there is no push, release, or V2-2 work.
- `src/lore2mud/application/` implements the local candidate's `GameIntent`,
  `GameSession`, `GameEvent`, `GameView`, and `TurnResult`. `World` remains the sole
  gameplay authority; CLI and Web retain parsing and rendering responsibilities.
- The controller full matrix is complete. This workstream may continue only by making
  a coherent local commit and running fresh read-only TECH acceptance on that exact
  commit. This file grants no TECH, PRODUCT, or SECURITY PASS itself; the final TECH
  verdict is authoritative only in this workstream's independent acceptance record
  and controller report.

### Implemented

- Typed frozen contracts, determinism context, ordered event sequence, typed rejection
  diagnostics, and a complete player-safe projection.
- Only exact declared intent types and exact `str`, `int`, and Enum leaf values are
  accepted. CLI/Web perform the same contract validation before invoking overridable
  methods or operators, so hostile primitive subclasses cannot cross the snapshot
  boundary.
- Contract rejection restores the original `World` identity plus canonical persistable
  state, RNG position, clock input, and event sequence, and emits no transition event;
  unexpected exceptions are re-raised after restoration.
- `WorldRuleError`/`SaveLoadError` diagnostics are normalized before a final restore in
  `finally` and before view projection, so overridable exception formatting cannot
  mutate authority again after rollback.
- Rejection snapshots retain the original `DeterminismContext` identity and exact
  `seed`/`clock` values. Even low-level in-place mutation through `object.__setattr__`
  is restored on the same object before return or re-raise.
- `CommandProcessor` keeps its compatible constructor and dynamic `.world`, while
  gameplay handlers only submit intents and render `TurnResult`/`GameView`; Web
  `PlayerSession` keeps its name but wraps the same application session.
- The CLI renders the current numbered dialogue menu only from the player-safe
  `GameView.dialogue.options`. Ordered dialogue events remain transition facts and
  cannot reintroduce options that the projection found inadmissible.
- Web JSON adds `status/events/view/diagnostics` while preserving
  `ok/event/snapshot`; the browser consumes concrete projected affordances instead of
  duplicating lock, death, item, trade, dialogue, or campaign rules.
- The compatibility `snapshot` retains V1's explicit nullable fields while unavailable
  actions remain absent from the new player-safe `view`. Compatibility `event.data`
  also reconstructs the complete V1 room, campaign-effect, and explicit-null shapes
  from typed events. Room items, monsters, characters, and campaign actions retain
  authored order instead of being re-sorted by V2-1.
- Save v9 writes, v7/v8 read gates, content Schema/version, the public Demo, and runtime
  campaign format are unchanged.

### Verification Status

- Finding-specific Web shape, typed campaign-effect, and V1 visible-order regressions:
  49 passed.
- `.venv\Scripts\python.exe -m unittest discover`: 1414 tests, 11 skipped, OK.
- The first resumed `unittest discover` did not explicitly bind the isolated
  worktree's `src`, so the project virtualenv's editable primary-checkout install mixed
  in stale modules and failed. The same full command passed with
  `PYTHONPATH=<worktree>/src`; the failed attempt is retained as a harness
  configuration issue and is not counted as passing evidence.
- `.venv\Scripts\python.exe -m pytest -q`: 1403 passed, 11 skipped. The same suite
  with `-n auto` and explicit repository-external TEMP/TMP plus `--basetemp`: 1403
  passed, 11 skipped. The first xdist startup hit `WinError 5` in the user's pytest
  temp root before collection; it is accurately retained as a harness issue and
  closed by the successful rerun.
- `ruff check .`, `pyright`, `compileall -q src pipeline scripts tests`,
  `lore2mud validate --content examples/original_demo`,
  `check_repo_safety.py --history`, `git fsck --full --no-dangling`, and working/staged
  `git diff --check` all pass.
- Full tests execute real Windows PyInstaller and zipapp build, content, and
  repository-external cold-start coverage.
- Independent acceptance is not self-decided by this implementation context; consult
  the controller's final report for the exact verdict.

### Roles And Models

- Controller/Implementation: the current root task, owning interface freeze,
  integration, tests, commit, and gates.
- Product/Specification: read-only acceptance matrix; Architect/Engine Lead: read-only
  runtime, save, and client boundary review. Both inherited the current task model;
  the tool did not expose a finer model identifier.
- Independent Acceptance: a fresh task that did not implement the candidate and must
  review the exact commit strictly read-only. Model output is not evidence; code,
  tests, and Git facts must support the verdict.

### Preserved Boundaries

- Private source text, canon, derived adaptations, images, saves, and reports are not
  accessed and cannot enter public Git.
- No new dependency, Schema/content/save version, Capability, SDK, structured CLI,
  MCP, `SimulationReport`, proofing, migration, plugin, new Demo, or V2-2 work.
- The primary checkout's untracked `uv.lock` remains 14,471 bytes, SHA-256
  `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`;
  it must remain absent from the isolated worktree.

### Residual Risks

- Current V1 rules do not consume the `DeterminismContext` RNG/clock. Rejection
  invariance is preserved and tested, but future real consumers require new observable
  determinism tests.
- Player affordances probe existing rules on isolated `deepcopy(World)` values. This
  is bounded and does not create the V2-2 general action catalog, but large-pack
  performance remains to be measured later.
- `World`, loader, save, and legacy command rendering remain large; V2-1 does not
  authorize wholesale decomposition.
