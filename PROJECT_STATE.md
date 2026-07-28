# Project State

_Last updated: 2026-07-28（M1 独立验收封板）_

## Objective
提供可公开托管的 Python 文字 MUD 引擎与小说资料处理基底，让私人小说原文和
改编内容始终与通用代码、原创示例分离。中期目标是在该引擎成熟后、保持私有素材
不进入公开仓库的前提下，制作仅供项目负责人游玩的个人 MUD 试玩版；当前阶段只扩展
通用引擎和原创示例。

## Current status
装备系统已实现 hand 和 body 双槽位，存档格式为 v5。对话系统已实现——原创 NPC 老陈带有
确定性分支对话和一次性普通物品奖励；琉草小径西向出口要求持有该铜牌，`look` 会只读显示
门禁所需物品与持有状态。`inspect` 仅查看当前房间或背包内物品的稳定 ID 和描述，不改变
任何运行时状态；新增 `save [槽位]` / `load [槽位]`，在默认 `default.json` 之外支持安全的
命名本地存档槽位。写入端文件系统 `OSError` 现在会被 `SaveLoadService` 转换为带 cause 的
`SaveLoadError`，CLI 能稳定返回失败文本。新增 `drop <物品ID或名称>`：仅将背包中未装备的
物品放入当前房间，hand/body 装备必须先 `unequip`，以免隐式改变有效战斗属性。新增可选的
`loot_item_id`：怪物首次被击败时才把唯一、初始未摆放的战利品放入当前房间，玩家可用现有
`take` 拾取；`World.attack()` 在战斗变更前预检位置冲突，战利品不会由重复攻击复制。该机制
沿用现有 room/inventory 存档状态，未升级 save v5；原创内容包现为 v0.2.7。生产安全门已扩展为
当前 Git 候选与可达历史的双层检查。2026-07-28 切片前，`HEAD`、`origin/main` 和直接查询的
远端 `main` 都是 `1936e913348d3d46278ffaae2cfabf6502020835`，因此此前“仍为 `6c13fca`、
尚待发布”的交接表述已确认过期。本地提交按项目负责人指示不自动推送；恢复时必须重新检查
实时远端同步状态。本切片依项目负责人临时授权由 Hermes agent 自审并执行，不构成独立
GPT-5.6-sol 验收。2026-07-28 的只读公共核心 readiness audit 以
`d81310c08ada7d2950dbfbcd1c431d42773c056e` 为基线，确认工作树干净、远端仍为
`1936e913348d3d46278ffaae2cfabf6502020835`、ahead/behind 为 `2/0`，结论为
`CONDITIONAL GO`：可以继续扩展完全原创的公共可玩内容，但这不等于引擎功能已全部完成，
更不授权小说事实层访问。M1 死亡/失败处理已由 GPT-5.6-sol 于 2026-07-28 对
`c329546` 完成独立验收，结论 GO。公共引擎仍在开发中。

## Completed

- `src/lore2mud/` 实现标准库运行时、双 CLI 入口和领域模块。
- `examples/original_demo/` 提供三个原创房间、六个物品、一个怪物、一个角色（老陈）和一个任务；
  新增一件仅由该怪物首次击败后掉落的原创消耗品。
- `pipeline/` 支持 UTF-8/GBK/GB18030、章卷分离、稳定顺序 ID 和 manifest v2。
  私有拆章重建校验通过（字符数 + SHA-256 一致）。
- `schemas/` 与 `src/lore2mud/content/` 定义并校验内容契约。
- `scripts/check_repo_safety.py` 与 `.gitignore` 建立公开/私有内容边界。
- 安全门覆盖 private novel 的 raw/chapters/summaries/canon/extractions、私有/
  生成内容、存档、模型、索引、数据库、日志、本地配置和有限常见凭据模式；CI 使用
  `--history` 扫描所有可达历史树和 blob。
- 生产工作流明确 GPT-5.6-sol 为顾问、Hermes agent 为执行者，要求先审
  数据契约和验收方案，再完成单一纵向切片。
- `tests/` 覆盖核心玩法、消耗品、装备（hand+body）、对话系统（91 项）、
  非法内容引用、拆章和安全检查。
- 私有小说已在仓库外完成一次受控拆章；原文未修改，章节重建校验通过。
- `docs/`、`AGENTS.md`、GitHub 基础文件和项目交接文件已建立。
- 版本化本地存档/读档：`save`/`load` 指令、`SaveLoadService`、原子写入、
  严格验证和 CLI 冒烟测试通过。
- 存档 v5 进一步收紧：顶层、`content_pack`、`player`、每个房间和每个怪物对象
  均拒绝未知字段；校验失败在构造替换 `World` 前返回错误。
- 内容包校验 CLI：`lore2mud validate --content <dir>`、旧命令隐式 play
  fallback、`_read_json` UnicodeDecodeError 处理。
- 原创确定性任务闭环：自动接取、怪物击败条件、经验奖励、`quests` 命令。
- 消耗品系统：`heal_amount` 字段、`use` 命令、`World.use()` + `UseOutcome`、
  满血/死亡边界检查、读档往返验证、17 项新测试。
- 装备系统 hand：`attack_bonus` 字段、`equip`/`unequip` 命令、
  `World.effective_attack` 动态计算、存档 v3、49 项新测试。
- 装备系统 body：`defense_bonus` 字段、`World.effective_defense` 动态计算、
  `player_defense` combat 参数、`unequip` 带槽位参数、存档 v4（双键必填）、
  19 项新测试（含 World 状态不变性 + save v4 非法矩阵）。
- 对话系统：`talk` 命令、裸整数选项选择（`^[1-9][0-9]{0,4}$`）、`bye` 命令、
  `World.start_dialogue()`/`select_option()`/`end_dialogue()` 域 API、
  `TalkOutcome`/`DialogueEndOutcome` 结构化结果、终端节点自动结束、
  `look` 显示角色、save v5（`active_dialogue` 必填 + 严格拒绝）、
  内容包已从 v0.2.4 扩展至 v0.2.5、91 项相关测试。
- 对话物品奖励：`DialogueOption.grant_item_id`、`DialogueItemGrant` 和
  `TalkOutcome.granted_item`；加载器拒绝未知、空、非稳定、消耗品、房间摆放和重复
  奖励引用。`World.select_option()` 使用背包契约原子发放，失败不改变任何游戏状态；
  原创 `item_chen_token` 由老陈观测站对话结束选项发放。
- 内容包版本升至 0.2.5；存档格式保持 v5。
- 持有物品门禁出口：不可变 `ExitDefinition` 将旧字符串和对象出口统一规范化；对象可选
  `required_item_id`。加载器校验目标/物品引用、稳定 ID、严格对象字段及 casefold 方向重复。
  `World.move()` 在变更房间、任务和对话前检查背包，失败不改变任何状态、成功不消耗物品；
  原创演示琉草小径西向出口要求 `item_chen_token`，内容包升至 v0.2.6，存档保持 v5。
- `look` 的出口行现在只读显示门禁所需物品的名称、稳定 ID 和“未持有”/“已持有”状态；
  普通出口仍只显示方向。展示层不复刻门禁规则，`World.move()` 仍是唯一规则权威；内容包
  版本与 save v5 格式均未变更。
- 可见物品查看：`World.inspect_item()` 只从当前房间和背包解析物品，返回结构化
  `InspectItemOutcome`；同名时要求稳定 ID，其他房间与未发放对话奖励不可见。`inspect`
  命令只渲染 ID 和描述，且不会改变房间、背包、装备、任务、活动对话或怪物状态。
  内容包版本与 save v5 格式均未变更。
- 命名存档槽位：`SaveLoadService.save/load` 可选一个受限槽位名，`save` / `load` 无参数仍
  使用 `default.json`。槽位名仅允许 1–32 位小写 ASCII 字母、数字、`-`、`_`，且必须以
  字母或数字开头，并拒绝路径、扩展名和 Windows 保留设备名；它只选择保存目录内的文件，
  失败不会写入文件或替换当前 `World`。save v5 JSON 格式保持不变。
- 写入错误契约：`SaveLoadService.save()` 仅把 `_atomic_write()` 产生的文件系统 `OSError`
  转为带原始 cause 的 `SaveLoadError`；命令层据此返回“存档失败”文本。既有原子写入、
  临时文件清理和非 I/O 编程错误传播语义不变。
- 丢弃物品：`World.drop()` 是唯一规则权威，按背包中稳定 ID 或唯一显示名解析物品；所有
  校验完成后才从背包移动到当前房间。缺失、同名歧义、已装备 hand/body 物品均不改变运行时
  状态；成功丢弃不结束活动对话，且 save v5 往返后可再次拾取。
- 确定性怪物战利品：`MonsterDefinition.loot_item_id` 和运行时 `Monster.loot_item_id`
  可选且严格校验；它引用的物品必须存在、初始不在房间、不会与对话奖励或另一只怪物重复。
  `World.attack()` 在击败时把战利品置入当前房间并返回 `LootOutcome`，存活怪物战利品若已在
  保存的房间/背包状态中出现则拒绝读档。save v5 格式未变。
- M1 死亡/失败处理（`World.recover()` + `_require_alive()` 统一门禁 + 命令层门禁 +
  59 项测试）已由 GPT-5.6-sol 于 2026-07-28 对 `c329546` 独立验收，结论 GO。
  验收证据：59 项专项 + 474 项全量测试通过、编译、内容校验、安全扫描、真实 CLI 通过。

## In progress

- None.

## Blockers

- None.

## Verification

- 公共核心 readiness audit（2026-07-28）：完整 415 项测试和 248 项聚焦的
  content/save/dialogue/gate/drop/inspect/loot/safety 测试通过；编译、原创内容包校验、
  `check_repo_safety.py --history`、`git diff --check`、`git fsck --full --no-dangling`
  与真实 CLI 主循环均通过。CLI 覆盖装备、对话奖励、持有物品门禁、消耗、战斗、掉落、
  拾取和丢弃；没有读取私有小说目录。
- `python -m unittest discover -s tests -v` - 474 tests passed (2026-07-28).
- `python -m unittest tests.test_loot -v` - 15 tests passed (2026-07-28), covering
  loader contracts, one-time placement, state invariance, CLI, and save/load.
- `python -m unittest tests.test_drop -v` - 11 tests passed (2026-07-28), covering
  ID/name resolution, state invariance, equipped rejection, dialogue preservation,
  CLI rendering, and save/load.
- `python -m unittest tests.test_save_slots tests.test_save -v` - 90 tests
  passed (2026-07-28), including named-slot isolation, input safety, default
  compatibility, write-I/O translation, CLI text, and failure invariance.
- tests/test_dialogue.py: 91 tests, including typed item reward loading, state
  invariance, save/load and CLI rendering.
- `python scripts/check_repo_safety.py` - passed (2026-07-28).
- `python scripts/check_repo_safety.py --history` - required for CI/release;
  records only limited path and credential pattern detection, not a complete secret audit.
- `python -m compileall -q src pipeline scripts tests` - passed (2026-07-28).
- `python -m lore2mud validate --content examples/original_demo` - passed (2026-07-28).
- `git diff --check` - clean (2026-07-28).
- M1 独立验收（2026-07-28，`c329546`）：59 项 recover 专项测试通过；474 项全量
  unittest 通过；compileall、original_demo 内容校验、`check_repo_safety.py --history`、
  `git diff --check` 均通过；真实 CLI（倒下 → 移动拒绝 → 死亡存档 → recover → 20/20 →
  可继续游戏）通过；Git main、ahead 2 / behind 0、工作树干净、未 push。
  GPT-5.6-sol 独立验收结论 GO。

## Key paths

- `PROJECT_MEMORY.md` - fresh-session restart instructions and pause rules.
- `AGENTS.md` - GPT-5.6-sol 顾问与 Hermes agent 执行约束。
- `docs/production_workflow.md` - GPT-5.6-sol 顾问与 Hermes agent 执行的生产流程。
- `docs/engine_completion_milestones.md` - M1–M8 引擎完成路线图。
- `NEXT_TASK.md` - exactly one recommended continuation.
- `src/lore2mud/engine/world.py` - authoritative runtime state with quest,
  item inspection/use, equipment, and dialogue logic.
- `src/lore2mud/engine/save.py` - save/load service with safe local slot paths (format v5).
- `src/lore2mud/engine/commands.py` - command processor with dialogue rendering and death gate.
- `tests/test_recover.py` - defeat recovery, death gate invariance, and save/load round-trip.
- `tests/test_inspect.py` - visible-item inspection state-invariance and round-trip coverage.
- `tests/test_drop.py` - inventory-to-current-room drop, failure invariance, and
  save/load coverage.
- `tests/test_loot.py` - deterministic monster loot contracts, one-time placement,
  command rendering, and save/load coverage.
- `tests/test_save_slots.py` - named-slot safety, isolation, and command coverage.
- `src/lore2mud/content/loader.py` - schema-like and reference validation.
- `src/lore2mud/cli.py` - CLI entry point with play/validate subcommands.
- `src/lore2mud/combat/service.py` - deterministic combat with player_attack/defense.
- `examples/original_demo/` - public, original playable fixture with dialogue.
- `D:\MUD game kaifa\小说\processing\` - private external processing output; never commit.

## Risks and unknowns

- Only one quest type (monster_defeated) is implemented; more types need explicit
  decisions.
- The one-target-monster-per-quest constraint will need revisiting if shared-target
  quests are ever needed.
- Dialogue grants only one typed item effect; quest triggers, experience effects,
  generic effect dictionaries, and repeatable rewards remain out of scope.
- `drop` can deliberately leave a gate item in the current room and therefore block
  a gated exit until the player takes it again; this is explicit player intent.
  Equipped items are intentionally rejected instead of silently changing combat stats.
- Private corpus summaries, canon facts and game adaptation content have not been
  generated or reviewed.
- The provider's privacy claim about model visibility is not independently verified;
  do not send the entire corpus to a cloud model by default.
- History rewriting can leave Git hosting caches and pre-existing external clones with
  old objects; repository checks only cover currently reachable refs.
- 项目负责人提供的历史 GPT-5.6-sol 审计已在 `2ecead1` 上完成，结论为 `CONDITIONAL GO`：
  写入 I/O 错误契约已补齐；审计报告的 43 个 dangling blob 未读取内容，也不受可达历史
  安全扫描覆盖。当前 `drop` 切片仅在项目负责人授权的 Terra 临时流程下自审，不得表述为
  独立 Sol 验收；后续发布前仍须重新核对远端，若远端变动则停止发布并重新审查。
- 公共核心 readiness audit 的结论是 `CONDITIONAL GO`，不是“引擎开发完成”的认证。
  其证据足以支持下一步继续扩展完全原创的公共内容，但新的玩法机制仍应保持小纵向切片。
- 项目负责人已明确将小说事实层延后至公共引擎开发完成之后；无论公共审计结论如何，私有
  facts/canon/摘要/派生内容仍禁止访问，届时也必须重新获得明确、范围受限的授权。
