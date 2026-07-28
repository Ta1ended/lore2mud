# Project State

_Last updated: 2026-07-28_

## Objective
提供可公开托管的 Python 文字 MUD 引擎与小说资料处理基底，让私人小说原文和
改编内容始终与通用代码、原创示例分离。

## Current status
装备系统已实现 hand 和 body 双槽位，存档格式升级至 v5。对话系统已实现——
原创 NPC 老陈带有确定性分支对话和一次性普通物品奖励，内容包版本升至 0.2.5。生产安全门已扩展为
当前 Git 候选与可达历史的双层检查。

## Completed

- `src/lore2mud/` 实现标准库运行时、双 CLI 入口和领域模块。
- `examples/original_demo/` 提供三个原创房间、五个物品（一个消耗品、一个武器、
  一个护甲、一个隐藏对话奖励）、一个怪物、一个角色（老陈）和一个任务。
- `pipeline/` 支持 UTF-8/GBK/GB18030、章卷分离、稳定顺序 ID 和 manifest v2。
  私有拆章重建校验通过（字符数 + SHA-256 一致）。
- `schemas/` 与 `src/lore2mud/content/` 定义并校验内容契约。
- `scripts/check_repo_safety.py` 与 `.gitignore` 建立公开/私有内容边界。
- 安全门覆盖 private novel 的 raw/chapters/summaries/canon/extractions、私有/
  生成内容、存档、模型、索引、数据库、日志、本地配置和有限常见凭据模式；CI 使用
  `--history` 扫描所有可达历史树和 blob。
- 生产工作流明确 GPT-5.6-sol 为顾问、Codex（GPT-5.6-terra）为执行者，要求先审
  数据契约和验收方案，再完成单一纵向切片。
- `tests/` 覆盖核心玩法、消耗品、装备（hand+body）、对话系统（77 项）、
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
  内容包 v0.2.4、77 项新测试。
- 对话物品奖励：`DialogueOption.grant_item_id`、`DialogueItemGrant` 和
  `TalkOutcome.granted_item`；加载器拒绝未知、空、非稳定、消耗品、房间摆放和重复
  奖励引用。`World.select_option()` 使用背包契约原子发放，失败不改变任何游戏状态；
  原创 `item_chen_token` 由老陈观测站对话结束选项发放。
- 内容包版本升至 0.2.5；存档格式保持 v5。

## In progress

- None.

## Blockers

- None.

## Verification

- `python -m unittest discover -s tests -v` - 348 tests passed (2026-07-28).
- tests/test_dialogue.py: 91 tests, including typed item reward loading, state
  invariance, save/load and CLI rendering.
- `python scripts/check_repo_safety.py` - passed (2026-07-28).
- `python scripts/check_repo_safety.py --history` - required for CI/release;
  records only limited path and credential pattern detection, not a complete secret audit.
- `python -m compileall -q src pipeline scripts tests` - passed (2026-07-28).
- `python -m lore2mud validate --content examples/original_demo` - passed (2026-07-28).
- `git diff --check` - clean (2026-07-28).

## Key paths

- `PROJECT_MEMORY.md` - fresh-session restart instructions and pause rules.
- `AGENTS.md` - GPT-5.6-sol 顾问与 Codex 执行约束。
- `docs/production_workflow.md` - GPT-5.6-sol 顾问与 Codex 执行的生产流程。
- `NEXT_TASK.md` - exactly one recommended continuation.
- `src/lore2mud/engine/world.py` - authoritative runtime state with quest,
  item use, equipment, and dialogue logic.
- `src/lore2mud/engine/save.py` - save/load service (format v5).
- `src/lore2mud/engine/commands.py` - command processor with dialogue rendering.
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
  generic effect dictionaries, item dropping and repeatable rewards remain out of scope.
- Private corpus summaries, canon facts and game adaptation content have not been
  generated or reviewed.
- The provider's privacy claim about model visibility is not independently verified;
  do not send the entire corpus to a cloud model by default.
- History rewriting can leave Git hosting caches and pre-existing external clones with
  old objects; repository checks only cover currently reachable refs.
