# 项目状态 / Project State

_最后更新 / Last updated: 2026-08-05_

## 中文

### 目标

交付一个可由 Agent 调用的小说转文字游戏引擎：创作平面生成经过验证、可追溯的包，
确定性运行时平面负责执行，同时保持 V1 兼容性以及严格的公开/私有和权利边界。

### 当前状态

- 已实时核对公开远端 `main` 为
  `564530d87aea17da26544b7793701e0dca0fe57d`；本阶段没有移动 `main`。
- V2-1 的精确产品候选是
  `c8ee518ef39f938ece374cbd3f7c9bca06de2408`，位于远端
  `workstream/v2-1-game-session`，规划祖先是
  `1d4b26d9127d4229893911cf260cf3c2f4b0ce3a`。
- 产品候选已获得全新的独立 TECH `GO` 与 SECURITY `GO`，两者 P0-P3 均为空；
  产品所有者于 2026-08-05 明确给出该 SHA 的 `PRODUCT PASS`。
- 候选提交的 GitHub Actions 已成功：tests `30967325238`、quality
  `30967325246`。当前后续封存只改交接/决策文档，不改变已验收产品字节。
- V2-1 已完成并发布到工作流分支。没有 release、`main` 集成或 V2-2 工作；唯一下一
  门禁是产品所有者另行明确授权开始 V2-2，并确认其起始基线。

### 已实现

- `CLI/Web parsing -> GameIntent -> GameSession -> TurnResult -> transport rendering`
  已成为共享公共应用边界；`World` 仍是唯一玩法权威，Web `PlayerSession` 保持兼容名称。
- typed/frozen `GameIntent`、`GameEvent`、`GameView`、`TurnResult` 与拒绝诊断保持稳定顺序，
  CLI 和 Web 只负责解析及呈现，不复制玩法可用性规则。
- 合同拒绝在权威状态改变前或失败回滚后返回，无转移事件；原 `World` 对象图、规范化
  save 状态、RNG、`DeterminismContext` 身份与 seed/clock、事件序列及存档可见元数据
  保持不变。已接受的游戏内失败仍沿用现有 `World` 结果。
- 新的内部有界 JSON 读取器在 domain validation 前限制单文件 8 MiB、深度 64、
  200,000 节点、单字符串 1,000,000 字符与整数 64 位十进制数字，并统一归一化 UTF-8、
  JSON、递归、数值与 I/O 错误。内容包转换为 `ContentValidationError`，存档转换为
  `SaveLoadError`/`PERSISTENCE_ERROR`。
- 对话事件的公共选项从同一回合最终 `GameView` 重建；campaign 公共事件不再携带会
  泄露 narrative state、离屏 actor、scene stage 或 knowledge 转移的原始 effect outcomes。
  新 `events` 与兼容 `event.data` 共用同一玩家安全 typed payload。
- pytest 测试约束更新为 `pytest>=9.0.3,<10`；不可序列化的 unittest `subTest` 标签改为
  稳定字符串/序号，serial 与 xdist 语义保持一致。Windows zipapp 明确覆盖新增模块。
- save 仍写 v9，v7/v8 读取条件、Schema、内容包版本、公开 `original_demo` 与 runtime
  campaign 格式均未改变；未新增运行时依赖。

### 验证状态

- 安全/兼容聚焦串行与 xdist 矩阵：`435 passed, 6 skipped, 308 subtests passed`；跳过项
  均为当前 Windows 主机缺少符号链接权限。
- 首次完整 `unittest discover` 因共享 `.venv` 的主仓库 editable install 混入旧模块，
  同时暴露新增文件尚未进入 Git 索引导致 zipapp 遗漏；绑定隔离 worktree 的
  `PYTHONPATH=src` 并纳入 tracked-file 清单后重跑：1418 tests，11 skipped，OK。
- 完整 pytest serial：`1407 passed, 11 skipped, 554 subtests passed`；完整 xdist：
  `1407 passed, 11 skipped, 554 subtests passed`。
- `ruff check .`、`pyright`、`compileall -q src pipeline scripts tests`、
  `lore2mud validate --content examples/original_demo`、`pip check`、
  `check_repo_safety.py --history`、`git fsck --full --no-dangling` 与 working/staged
  `git diff --check` 均通过。
- 全新独立 TECH 验收在精确候选上运行 267 个聚焦测试，并以 pytest 9/xdist 运行
  `352 passed, 6 skipped, 300 subtests passed`，最终 P0-P3 全空、`GO`。
- 全新独立 SECURITY 验收运行 `290 passed, 208 subtests passed`，另验证 byte/string/
  integer/depth/node 的 exact/over 边界、surrogate、non-finite、无效 UTF-8、missing/IO、
  全响应泄露与事务不变性，最终 P0-P3 全空、`GO`。

### 角色与模型

- Controller/Implementation：当前根任务，负责范围、接口冻结、实现、集成、门禁、提交、
  publication 与最终交接；工具未暴露可审计的精确模型标识。
- Security Scope/Jason：编码前后的只读安全预审，发现公共事件泄露、无界 JSON、pytest
  约束与旧交接状态问题；该预审不是最终 verdict，也未参与修复。
- Independent TECH Acceptance：未参与实现的新任务，严格只读验收精确 SHA，输出 `GO`。
- Independent SECURITY Acceptance：未参与实现且不复用预审 verdict 的新任务，严格只读
  验收精确 SHA，输出 `GO`。
- 两个独立验收任务继承 Controller 可用模型；工具未返回更细模型 ID。所有结论均由代码、
  自动化测试和 Git 证据支持，Implementation 未自我批准。
- Product Owner：于 2026-08-05 对 `c8ee518` 明确给出 `PRODUCT PASS`。

### 保持的边界

- 未访问私人小说、canon、派生内容、图片、存档或报告；这些材料未进入公开 Git。
- 未实现 Capability、SDK、structured CLI、MCP、`SimulationReport`、proofing、迁移、
  动态插件、新 Demo、V2-2 或整体 `World` 拆分。
- 没有移动 `main`、创建 release 或改动 Schema、内容包版本、save 写入/读取版本。
- 主工作区未跟踪 `uv.lock` 保持 14,471 字节，SHA-256
  `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`；隔离
  worktree 不包含该文件。

### 剩余风险

- 当前 V1 规则仍不实际消费 `DeterminismContext` RNG/时钟；未来消费者需要新的可观察
  确定性测试。
- 玩家 affordance 通过隔离 `deepcopy(World)` 探测现有规则；大型内容包性能仍需后续实测。
- 有界 JSON 是单文件边界；未来若扩大受信内容规模，必须通过明确产品决策调整限制并保持
  拒绝事务测试。
- V2-1 只发布在工作流分支，尚未集成 `main`；V2-2 的起始分支/基线必须由下一次授权明确。

## English

### Objective

Deliver an Agent-callable novel-to-text-game engine whose Authoring Plane produces
validated, traceable packages for a deterministic Runtime Plane, while preserving V1
compatibility and strict public/private and rights boundaries.

### Current Status

- Live public remote `main` is verified at
  `564530d87aea17da26544b7793701e0dca0fe57d`; this stage did not move `main`.
- The exact V2-1 product candidate is
  `c8ee518ef39f938ece374cbd3f7c9bca06de2408` on remote
  `workstream/v2-1-game-session`, with planning ancestor
  `1d4b26d9127d4229893911cf260cf3c2f4b0ce3a`.
- The candidate received fresh independent TECH `GO` and SECURITY `GO`, both with
  empty P0-P3 findings. The product owner explicitly granted `PRODUCT PASS` for this
  SHA on 2026-08-05.
- Candidate GitHub Actions succeeded: tests `30967325238` and quality `30967325246`.
  The following seal changes handoff/decision documents only, not accepted product
  bytes.
- V2-1 is complete and published on the workstream branch. There is no release,
  `main` integration, or V2-2 work. The sole next gate is separate product-owner
  authorization to start V2-2 and select its baseline.

### Implemented

- `CLI/Web parsing -> GameIntent -> GameSession -> TurnResult -> transport rendering`
  is the shared public application boundary. `World` remains the only gameplay
  authority, and Web `PlayerSession` retains its compatibility name.
- Typed/frozen `GameIntent`, `GameEvent`, `GameView`, `TurnResult`, and rejection
  diagnostics preserve stable order. CLI and Web only parse and render; they do not
  duplicate gameplay availability rules.
- Contract rejection occurs before authoritative mutation or after full rollback and
  emits no transition event. The original `World` object graph, canonical save state,
  RNG, `DeterminismContext` identity and seed/clock, event sequence, and save-visible
  metadata remain unchanged. Accepted in-world failures retain existing `World`
  outcomes.
- A new internal bounded JSON reader limits each file before domain validation to
  8 MiB, depth 64, 200,000 nodes, 1,000,000 characters per string, and 64 decimal
  integer digits. It normalizes UTF-8, JSON, recursion, numeric, and I/O failures.
  Content packages raise `ContentValidationError`; saves raise `SaveLoadError` and
  become typed `PERSISTENCE_ERROR` rejections.
- Public dialogue-event options are rebuilt from the final same-turn `GameView`.
  Public campaign events no longer carry raw effect outcomes that expose narrative
  state, off-screen actors, scene stages, or knowledge transitions. New `events` and
  compatibility `event.data` share the same player-safe typed payload.
- The test constraint is now `pytest>=9.0.3,<10`. Unserializable unittest `subTest`
  values use stable string/index labels so serial and xdist semantics match. Windows
  zipapp coverage explicitly includes the new module.
- Saves still write v9; v7/v8 read conditions, Schemas, content-pack versions, the
  public `original_demo`, and runtime-campaign formats are unchanged. No runtime
  dependency was added.

### Verification Status

- Focused security/compatibility serial and xdist matrix:
  `435 passed, 6 skipped, 308 subtests passed`. Skips are only unavailable symlink
  privileges on this Windows host.
- The first full `unittest discover` mixed stale primary-checkout modules through the
  shared virtualenv's editable install and also exposed that the new file was not yet
  in the Git index used by the zipapp allowlist. After binding `PYTHONPATH=src` to the
  isolated worktree and adding the tracked file, the rerun passed 1418 tests with
  11 skips.
- Full serial pytest: `1407 passed, 11 skipped, 554 subtests passed`; full xdist:
  `1407 passed, 11 skipped, 554 subtests passed`.
- `ruff check .`, `pyright`, `compileall -q src pipeline scripts tests`,
  `lore2mud validate --content examples/original_demo`, `pip check`,
  `check_repo_safety.py --history`, `git fsck --full --no-dangling`, and working/staged
  `git diff --check` all passed.
- Fresh independent TECH acceptance ran 267 focused tests plus pytest 9/xdist at
  `352 passed, 6 skipped, 300 subtests passed`, ending with empty P0-P3 and `GO`.
- Fresh independent SECURITY acceptance ran `290 passed, 208 subtests passed` plus
  exact/over byte, string, integer, depth, and node probes; surrogate, non-finite,
  invalid UTF-8, missing/I/O, whole-response leakage, and transaction-invariance
  checks; it ended with empty P0-P3 and `GO`.

### Roles And Models

- Controller/Implementation: the current root task, owning scope, interface freeze,
  implementation, integration, gates, commits, publication, and final handoff. The
  tool did not expose an auditable exact model identifier.
- Security Scope/Jason: read-only pre-review before the repair, finding public-event
  leakage, unbounded JSON, the pytest constraint, and stale handoff state. This was
  not the final verdict, and Jason did not implement the repair.
- Independent TECH Acceptance: a fresh non-implementing task that reviewed the exact
  SHA strictly read-only and returned `GO`.
- Independent SECURITY Acceptance: a fresh non-implementing task that did not reuse
  the pre-review verdict, reviewed the exact SHA strictly read-only, and returned
  `GO`.
- Both independent tasks inherited the controller's available model; the tool returned
  no finer model ID. Code, automated tests, and Git evidence support every verdict;
  Implementation did not self-approve.
- Product Owner: explicitly granted `PRODUCT PASS` for `c8ee518` on 2026-08-05.

### Preserved Boundaries

- Private novels, canon, derived content, images, saves, and reports were not accessed
  and did not enter public Git.
- No Capability, SDK, structured CLI, MCP, `SimulationReport`, proofing, migration,
  dynamic plugin, new Demo, V2-2, or wholesale `World` decomposition was implemented.
- `main` was not moved; no release, Schema/content-version, or save-version change was
  made.
- The primary checkout's untracked `uv.lock` remains 14,471 bytes, SHA-256
  `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`;
  it is absent from the isolated worktree.

### Residual Risks

- Current V1 rules still do not consume the determinism RNG/clock; future consumers
  require new observable determinism tests.
- Player affordances probe existing rules on isolated `deepcopy(World)` values; large
  content-pack performance remains to be measured.
- Bounded JSON limits are per file. Any future trusted-scale increase needs an explicit
  product decision and preserved rejection-transaction tests.
- V2-1 is published only on the workstream branch, not integrated into `main`. The next
  authorization must select the V2-2 starting branch/baseline.
