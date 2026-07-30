# Project State

_Last updated: 2026-07-30（M8 独立验收 GO；M1–M8 公共引擎交接封板）_

## Objective
提供可公开托管的 Python 文字 MUD 引擎与小说资料处理基底，让私人小说原文和
改编内容始终与通用代码、原创示例分离。中期目标是在该引擎成熟后、保持私有素材
不进入公开仓库的前提下，制作仅供项目负责人游玩的个人 MUD 试玩版；当前阶段只扩展
通用引擎和原创示例。

## Current status

M1 死亡/失败处理和 M2 typed stacks 均保留其历史 GPT-5.6-sol 独立验收 GO；M3 三类任务
也已于 2026-07-29 独立验收 GO（DEC-0026）。这些历史验收不延伸为本切片的验收结论。

M4+M5 已由 Codex 实现，并由 GPT-5.6-sol 于 2026-07-29 独立验收 GO（DEC-0028）。
首次验收发现 M5 空栈买入绕过 `stack_limit` 的 P1；Codex 在 `59ca3cd` 修正后，聚焦复验
确认 P1 已关闭、无 findings。

项目负责人随后明确授权 M6。Codex 在 `53a071f` 已实现 `World.examine()` 三分支 frozen typed
outcomes、公开 `examine`、兼容 `inspect`、集中 `CommandSpec` 路由/帮助/死亡元数据和
`help [command]`（DEC-0029）。查看范围仅限当前房间物品、背包物品、当前房间怪物与角色；
跨类型同名或重复 ID 必须显式限定类型，歧义夹具只存在于测试内存。GPT-5.6-sol 已于
2026-07-29 对 M6 独立验收 GO、无 findings（DEC-0030）。项目负责人已明确授权 M7；
Codex 在 M7.1 只扩充完全原创内容：新增碎讯支线、火花巡兽和观测站触发的清除任务
（DEC-0031）。GPT-5.6-sol 已于 2026-07-30 对 M7.1 独立验收 GO、无 findings（DEC-0032）。
项目负责人随后授权 M7.2 的较大纯内容扩容包：Codex 新增四个原创房间、两只怪物和两条
唯一怪物目标任务（DEC-0033）。GPT-5.6-sol 已于 2026-07-30 对 `147633e` 相对 `5497859`
完成独立验收：M7.2 GO、整体 M7 GO，均无 findings（DEC-0034）。该 GO 先封板 M7 原创
内容规模；GPT-5.6-sol 随后对 M8 聚焦复核给出 GO、关闭 Git 快照 P2、无新增 findings
（DEC-0036），因此 M1–M8 范围内公共引擎完成。

M8 技术审计基线为 `f486e12`，审计记录为 `6510e2d`，Git 快照 P2 修正为 `6502a72`。独立
验收时本地 `HEAD=origin/main=6502a72`、工作树干净、ahead/behind 为 0/0；GitHub Desktop push
已反映到本地跟踪分支，命令行远端直查超时。该里程碑结论不授权 M9、新功能、发布或私有小说事实层。

当前公开契约为 content pack 0.8.0、save v7、强类型有序 `DialogueEffect`、World-owned
`flags`、非负 `coins` 和冻结的固定无限商店目录。`World` 预检并原子执行 effects/买入；
`accept_quest` 显式重复会整体失败；`load` 只恢复状态，绝不重放效果、自动接取、检查、奖励
或交易。`shop`/`buy`/`sell` 不引入可变库存。M7.2 未改变 Schema、引擎、命令或 save v7；
0.7.0 内容包存档由既有版本检查拒绝。original_demo 现有 8/8 房间、4/4 怪物和 7 条任务，
M7 内容规模条件已由独立验收确认满足；M8 的后续独立验收已完成 M1–M8 公共引擎路线，但不扩展
到任何后续路线图或私有事实层。

M4+M5 独立验收记录的证据为 12 项 M4 专项、13 项 M5 专项和 569 项全量 unittest，以及
compileall、original_demo 校验、历史安全扫描、diff 检查和仓库外 CLI 流程。CLI 精确覆盖
“拾取 3 → 卖出 3 → 买入 6 被拒绝 → save/load”：金币保持 26、背包没有非法栈、v7 存档可读；
M4 effects 不重放，v6 与旧内容包存档继续拒绝。M6 独立验收证据为 22 项专项、187 项聚焦和
591 项全量 unittest，以及 compileall、original_demo 校验、历史安全扫描、diff、相对
`f0acd3f` 的 11 文件范围和仓库外 CLI/save v7；均通过且无 findings。验收时 main 工作树
干净、ahead/behind 为 1/0，直查远端 main 为 `f0acd3f`；发布或 push 前必须再次直查。
M7.1 的 Codex 本地证据为 4 项新场景测试、15 项 loot 回归和 595 项全量 unittest，以及
compileall、original_demo 校验、历史安全扫描、diff 检查和仓库外 CLI/save v7；均通过。GPT-5.6-sol
随后相对 `086cda8` 对 `9786325` 独立验收 GO、无 findings：范围为 1 个提交、22 文件、+333/-55，
且 `src/`、`schemas/`、依赖文件与私有资料路径均为 0。真实 CLI 和存档确认新任务完成、玩家位于
新房间、火花巡兽 HP 为 0 且已从房间移除，save 保持 v7/0.7.0；远端直查仍为 `f0acd3f`，未 push。
M7.2 的本地证据为 8 项 M7 场景测试、15 项 loot 回归和 599 项全量 unittest，以及 compileall、
original_demo 校验、历史安全扫描、diff 检查和仓库外 CLI/save v7；均通过。CLI 完成两条新分支、
两只新怪物、两条新任务和 save/load，保存中 pack 为 0.8.0、玩家位于余辉信标台、两只新怪物
HP 为 0 且均已从房间移除。GPT-5.6-sol 的独立验收随后核对 22 个内容、测试和公开文档文件，
确认 `src/`、Schema、依赖与私有资料路径均为 0；23 项 M7/loot 聚焦、599 项全量、图与唯一性
审计、compileall、内容校验、安全扫描、diff、真实 CLI/save 与死亡恢复均通过，无 findings。M7
当前为 8/8 房间、4/4 怪物、7 条任务，已独立验收 GO；唯一下一动作见 `NEXT_TASK.md`。

## Historical current-status snapshot (2026-07-28, pre-M2; not current)

> 下列快照保留当时的 save v5、0.2.7、旧 Git 与旧执行流程事实；当前状态以上文
> v7、0.8.0、M7 独立验收 GO、M7.1/M4+M5 GO、M3/M2 GO 和
> Codex 执行模式为准。

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

> 历史记录说明：本节中 save v3–v5、内容包 0.2.x、旧 API 名称、旧测试数和旧 Git
> 状态均为对应切片当时的事实；当前契约以“Current status”的 v7、0.8.0 和 M7 独立验收状态为准。

- `src/lore2mud/` 实现标准库运行时、双 CLI 入口和领域模块。
- `examples/original_demo/` 提供八个原创房间、六个物品、四只怪物、一个角色（老陈）和七条
  任务；保留灰壳兽的唯一消耗品战利品，并新增不引入新机制的火花巡兽、雾核潜行者和棱镜哨卫遭遇。
- `pipeline/` 支持 UTF-8/GBK/GB18030、章卷分离、稳定顺序 ID 和 manifest v2。
  私有拆章重建校验通过（字符数 + SHA-256 一致）。
- `schemas/` 与 `src/lore2mud/content/` 定义并校验内容契约。
- `scripts/check_repo_safety.py` 与 `.gitignore` 建立公开/私有内容边界。
- 安全门覆盖 private novel 的 raw/chapters/summaries/canon/extractions、私有/
  生成内容、存档、模型、索引、数据库、日志、本地配置和有限常见凭据模式；CI 使用
  `--history` 扫描所有可达历史树和 blob。
- 生产工作流明确 GPT-5.6-sol 为顾问、Codex 为唯一执行者，项目负责人负责人工
  转交；仍要求先审数据契约和验收方案，再完成单一纵向切片。
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
- M2 typed stacks（`ItemStackDefinition`/`ItemStack` + `stack_limit` + `item_stacks` +
  `Inventory.stacks` + typed `loot_item`/`grant_item` + `take/drop/use` 数量 + loot
  预检 + save v6 + content pack 0.3.0）由 Hermes agent 实现；GPT-5.6-sol 已独立
  验收 GO。验收证据为 530 项全量、56 项专项测试及既定编译、内容、安全、diff 和 CLI
  验证。
- M3 三类任务系统由 Codex 实现，并由 GPT-5.6-sol 独立验收 GO：frozen `QuestDefinition` tagged union、严格 loader/
  Schema、World 统一的接取/检查/奖励、任务 ID 字典序的 `quest_outcomes` / level gains、
  移动/拾取/战斗/对话奖励的局部回滚、兼容 `World.move() -> Room` 的
  `move_with_outcome()`、0.4.0 original_demo 和 v6 不重算读档。聚焦复验已关闭唯一 P2
  交接问题，未发现其他问题。
- M4 强类型对话效果和 M5 固定金币商店由 Codex 实现，并由 GPT-5.6-sol 独立验收 GO。
  M5 首次验收的空栈超 `stack_limit` P1 已由 `59ca3cd` 修正并在聚焦复验中关闭；save v7、
  content pack 0.6.0、固定无库存目录和 M4 effects/load 不重放契约保持不变。
- M6 `examine`、`help [command]` 和集中 `CommandSpec` 注册表由 Codex 在 `53a071f`
  实现，并由 GPT-5.6-sol 独立验收 GO（DEC-0030），无 findings。可见性、跨类型歧义、
  `inspect` 兼容、死亡/对话边界和只读状态不变性均已封板；M6 未改变 Schema、内容包 0.6.0
  或 save v7。

## In progress

- Phase 1.1 Schema allOf/additionalProperties P1 已关闭（DEC-0043）。
  237 项聚焦测试通过，816 项全量测试通过。等待 GPT-5.6-sol 聚焦复验。

## Blockers

- 无技术阻塞；后续工作受项目负责人新的明确授权门槛约束。

## Verification

- Phase 1.0 independent acceptance GO（2026-07-30，GPT-5.6-sol，DEC-0039）：
  聚焦复验确认 DEC-0038 三个 findings 全部关闭。131 项聚焦测试、730 项全量
  unittest、compileall、original-demo 校验、安全历史扫描和 diff 检查通过。
  9 个文件范围（相对 `e2b8136`）确认。初始实现 `e2b8136`（119 聚焦/718 全量）
  为 NO-GO；修正 `3442d2d` 为 GO 基线。独立验收时、封板提交前的快照为
  HEAD=`3442d2d`，`origin/main`=`afdb235`，ahead/behind=2/0，工作树干净，
  未 push。本轮顾问直查远端因连接重置未刷新；恢复或 push 前须重新直查。
- Phase 1.0 local verification（2026-07-30，Hermes）：
  119 项 `tests.test_fact_candidates` 聚焦测试通过；718 项全量 unittest 通过；
  compileall、`lore2mud validate --content examples/original_demo`、
  `check_repo_safety.py --history`、`git diff --check` 全部通过。新增 5 个文件
  （`pipeline/fact_candidates.py`、`schemas/fact_candidate.schema.json`、
  `tests/test_fact_candidates.py`、`tests/fixtures/fact_candidates/valid_character.json`、
  `docs/fact_candidate_format.md`）；更新 6 个文件（`docs/novel_pipeline.md`、
  `CHANGELOG.md`、`DECISIONS.md`、`PROJECT_MEMORY.md`、`PROJECT_STATE.md`、
  `NEXT_TASK.md`）；`src/`、现有 Schema、original_demo、save 格式和依赖未修改。
- M8 独立验收 GO（2026-07-30，GPT-5.6-sol）：聚焦复核关闭 Git 快照 P2、无新增 findings，
  并确认 M1–M8 范围内公共引擎完成。599 项全量 unittest、compileall、original-demo 内容校验、
  `check_repo_safety.py --history`、`git diff --check` 和 `git fsck --full --no-dangling` 全部通过；
  既有 216 项专项、375 项 save 矩阵、35 项内容/CLI/安全矩阵和真实 CLI 证据仍有效。技术基线为
  `f486e12`、审计记录为 `6510e2d`、P2 修正为 `6502a72`；验收时本地
  `HEAD=origin/main=6502a72`、工作树干净、ahead/behind 为 0/0。GitHub Desktop push 已反映到
  本地跟踪分支，命令行远端直查超时；后续发布前必须重新实时检查 Git。
- M8 只读审计基线（2026-07-30，Codex，后续已独立验收）：以 `f486e12` 为基线，599 项全量
  unittest、compileall、`lore2mud validate --content examples/original_demo`、
  `check_repo_safety.py --history`、`git diff --check` 与 `git fsck --full --no-dangling` 全部通过。
  真实 CLI 主流程完成 M7.2 两条新分支、save/load v7/0.8.0；另一全新 CLI 进程直达余辉信标台，
  证明棱镜哨卫击杀玩家后的死亡门禁、`recover`、回到余烬渡台以及 v7 save/load。审计本身未修改
  引擎、内容或契约；其后交接记录提交为 `6510e2d`，因此验收快照为 `HEAD=6510e2d`、
  `origin/main` 与远端 `main=f486e12`、ahead/behind `1/0`、工作树干净。后续交接提交后必须
  重新实时检查 Git。
- M7.2 与 M7 独立验收 GO（2026-07-30，GPT-5.6-sol，无 findings）：相对 `5497859` 的
  `147633e` 为 1 个提交、22 个内容、测试和公开文档文件，`src/`、Schema、依赖文件和私有资料
  路径均为 0。23 项 M7/loot 聚焦、599 项全量 unittest、图与唯一性审计、compileall、
  original_demo 内容校验、`check_repo_safety.py --history` 和 `git diff --check` 通过。真实 CLI/
  save 和死亡恢复通过；v7/0.8.0 存档确认玩家位于新增房间，两只新增怪物 HP=0 且已移除，
  `quest_clear_mist_crawler` 与 `quest_clear_prism_sentinel` 均已完成。验收时直查远端 `main`
  为 `f0acd3f`，未 push；M7 GO 不等同公共引擎完成。
- M7.2 本地验证（2026-07-30，独立验收前）：新增 4 个房间、2 只怪物、2 条唯一怪物目标任务，
  内容包为 0.8.0、save 保持 v7，旧 0.7.0 内容包存档被拒绝。8 项
  `tests.test_m7_second_encounter` / `tests.test_m7_content_scale`、15 项 `tests.test_loot`
  和 599 项全量 unittest 通过；compileall、original_demo 校验、`check_repo_safety.py --history`
  与 `git diff --check` 通过。仓库外 CLI 完成“装备 → 击败灰壳兽 → 击败火花巡兽 → 断轨岔口 →
  雾凝机井 → 击败雾核潜行者 → 余辉信标台 → 击败棱镜哨卫 → save/load”；存档确认 v7、0.8.0、
  玩家位于余辉信标台、两只新怪物 HP 为 0 且已移除、两条新任务完成。该本地证据随后获得独立验收。
- M7.1 独立验收 GO（2026-07-30，GPT-5.6-sol，无 findings）：相对 `086cda8` 的 `9786325`
  为 1 个提交、22 文件、+333/-55；`src/`、`schemas/`、依赖文件和私有资料路径均为 0。19 项
  M7/loot 聚焦与 595 项全量 unittest 通过；compileall、original_demo 校验、
  `check_repo_safety.py --history` 和基线范围 `git diff --check` 通过。真实 CLI 完成“进入观测站并
  接取任务 → 击败灰壳兽 → 进入碎讯支线 → 击败火花巡兽 → 完成任务 → save/load”；存档确认 v7、
  content pack 0.7.0、玩家位于新房间、火花巡兽 HP=0 且已移除、
  `quest_clear_spark_hound` 已完成。直查远端 `main` 为 `f0acd3f`，未 push。该 GO 仅适用于 M7.1。
- M7.1 本地验证（2026-07-29，非独立验收）：4 项 `tests.test_m7_second_encounter`、15 项
  `tests.test_loot` 和 595 项全量 unittest 通过；compileall、original_demo 校验、
  `check_repo_safety.py --history` 与 `git diff --check` 通过。仓库外 CLI 完成“进入观测站 →
  击败灰壳兽 → 进入碎讯支线 → 击败火花巡兽 → save/load”；v7 存档为 0.7.0、
  `quest_clear_spark_hound` 完成、火花巡兽 HP 为 0 且不在房间。旧 0.6.0 内容包存档被拒绝。
- M6 独立验收 GO（2026-07-29，GPT-5.6-sol）：对 `53a071f` 的 22 项
  `tests.test_examine_help`、187 项 M6/inspect/commands/recover/dialogue 聚焦回归和
  591 项全量 unittest 通过；compileall、original_demo 校验、历史安全扫描、`git diff --check`、
  相对 `f0acd3f` 的 11 文件范围和仓库外 CLI/save v7 都通过，无 findings。CLI 覆盖房间、
  物品、角色和怪物查看、类型化缺失错误、`help examine`、活动对话中的 `examine 1`、save/load；
  保存文件仍为 v7、内容包仍为 0.6.0。
- M4+M5 独立验收 GO（2026-07-29，GPT-5.6-sol）：首次 M5 空栈 `buy` ×6 超
  `stack_limit=5` 的 P1 已由 `59ca3cd` 修正并关闭，聚焦复验无 findings。12 项 M4 专项、
  13 项 M5 专项、569 项全量 unittest、compileall、original_demo 校验、历史安全扫描和
  diff 检查通过；仓库外 CLI 确认买入拒绝后金币 26、背包为空、v7 save/load 成功，M4 effects
  不重放，v6 与旧内容包存档继续拒绝。
- M3 独立验收 GO（2026-07-29，GPT-5.6-sol）：540 项全量 unittest、31 项
  `tests.test_quest`、56 项 `tests.test_item_stacks` 通过；compileall、original_demo
  内容校验、`check_repo_safety.py --history`、`git diff --check` 通过；仓库外临时存档
  目录的 CLI 完成 collect/reach/monster 三类任务、战利品拾取、save、读档和状态恢复。对
  `dca629b` 的聚焦复验确认 `5527faa` 已关闭先前唯一 P2，结论为无 findings。
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
- M2 独立验收（2026-07-29，`3161d52` / `1ee0b30`）：530 项全量 unittest、56 项
  `tests.test_item_stacks` 通过；compileall、original_demo 内容校验、
  `check_repo_safety.py --history`、`git diff --check` 均通过；真实 CLI 覆盖数量拾取、
  受伤后 `use` ×2 恢复至 20/20、战斗掉落、丢弃和 save/load。GPT-5.6-sol
  独立验收结论 GO。
- M1 独立验收（2026-07-28，`c329546`）：59 项 recover 专项测试通过；474 项全量
  unittest 通过；compileall、original_demo 内容校验、`check_repo_safety.py --history`、
  `git diff --check` 均通过；真实 CLI（倒下 → 移动拒绝 → 死亡存档 → recover → 20/20 →
  可继续游戏）通过；Git main、ahead 2 / behind 0、工作树干净、未 push。
  GPT-5.6-sol 独立验收结论 GO。

## Key paths

- `PROJECT_MEMORY.md` - fresh-session restart instructions and pause rules.
- `AGENTS.md` - GPT-5.6-sol 顾问、Codex 唯一执行者与人工转交约束。
- `docs/production_workflow.md` - GPT-5.6-sol 顾问与 Codex 执行的生产流程。
- `docs/engine_completion_milestones.md` - M1–M8 引擎完成路线图。
- `NEXT_TASK.md` - exactly one recommended continuation.
- `src/lore2mud/engine/world.py` - authoritative state for quests, effects, flags,
  coins, fixed shops, inventory, equipment, and dialogue.
- `src/lore2mud/engine/save.py` - strict v7 save/load service with coins and flags.
- `src/lore2mud/engine/commands.py` - command rendering for effects, shops, status,
  dialogue, and the death gate.
- `tests/test_recover.py` - defeat recovery, death gate invariance, and save/load round-trip.
- `tests/test_item_stacks.py` - typed-stack contracts, quantities, preflight, and save v7 coverage.
- `tests/test_dialogue_effects.py` - M4 union, atomicity, flags, outcomes, and v7 coverage.
- `tests/test_shop.py` - M5 catalogs, trade atomicity, coins, CLI, and save coverage.
- `tests/test_inspect.py` - visible-item inspection state-invariance and round-trip coverage.
- `tests/test_examine_help.py` - M6 typed visibility, ambiguity, exact help/error
  contracts, death/dialogue boundaries, and complete read-only invariance.
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

- M3 implements the fixed `monster_defeated`, `reach_room`, and `collect_item`
  quest kinds; any further quest kind requires an explicit contract and vertical slice.
- The one-target-monster-per-quest constraint will need revisiting if shared-target
  quests are ever needed.
- M4's four effect kinds and M5's fixed-price shop scope are closed; new effect kinds,
  dialogue currency effects, dynamic pricing, discounts, stock, or post-M6 command
  changes require a separately approved vertical slice.
- M6 is independently accepted. The `CommandSpec` registry intentionally centralizes
  current CLI routes; future commands must add their route, help, aliases, and death
  rule together and extend the bidirectional consistency test in a separately
  authorized vertical slice.
- M7.2 reaches all M7 content-scale counts (eight rooms, four monsters, and seven
  quests) without a new engine contract and is independently accepted together with
  M7. M8 is also independently accepted, completing the M1–M8 public-engine scope;
  do not infer authorization to expand scope or enter the private fact layer.
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
