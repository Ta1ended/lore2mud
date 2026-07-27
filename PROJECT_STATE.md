# Project State

_Last updated: 2026-07-28_

## Objective
提供可公开托管的 Python 文字 MUD 引擎与小说资料处理基底，让私人小说原文和
改编内容始终与通用代码、原创示例分离。

## Current status
消耗品系统已实现。玩家可以拾取并使用恢复生命的物品。内容包版本升至 0.2.1。

## Completed

- `src/lore2mud/` 实现标准库运行时、双 CLI 入口和领域模块。
- `examples/original_demo/` 提供三个原创房间、两个物品（一个消耗品）、一个怪物和一个任务。
- `pipeline/` 支持 UTF-8/GBK/GB18030、章卷分离、稳定顺序 ID 和 manifest v2。
- `schemas/` 与 `src/lore2mud/content/` 定义并校验内容契约。
- `scripts/check_repo_safety.py` 与 `.gitignore` 建立公开/私有内容边界。
- `tests/` 覆盖核心玩法、消耗品、非法内容引用、拆章和安全检查。
- 私有小说已在仓库外完成一次受控拆章；原文未修改，章节重建校验通过。
- `docs/`、`AGENTS.md`、GitHub 基础文件和项目交接文件已建立。
- 版本化本地存档/读档：`save`/`load` 指令、`SaveLoadService`、原子写入、
  严格验证和 CLI 冒烟测试通过。
- 内容包校验 CLI：`lore2mud validate --content <dir>`、旧命令隐式 play
  fallback、`_read_json` UnicodeDecodeError 处理。
- 原创确定性任务闭环：自动接取、怪物击败条件、经验奖励、`quests` 命令、
  存档 v2、内容包 0.2.0。
- 消耗品系统：`heal_amount` 字段、`use` 命令、`World.use()` + `UseOutcome`、
  满血/死亡边界检查、读档往返验证、17 项新测试。
- 内容包版本升至 0.2.1（旧 0.2.0 存档被版本检查拒绝）。

## In progress

- None.

## Blockers

- None.

## Verification

- `python -m unittest discover -s tests -v` - 160 tests passed (2026-07-28).
- `python scripts/check_repo_safety.py` - passed (2026-07-28).
- `python -m compileall -q src pipeline scripts tests` - passed (2026-07-28).
- CLI validate smoke test - passed (2026-07-28).
- CLI play smoke test with quests - passed (2026-07-28).
- `git diff --check` - clean (2026-07-28).

## Key paths

- `PROJECT_MEMORY.md` - fresh-session restart instructions and pause rules.
- `AGENTS.md` - Hermes and other Agent constraints.
- `NEXT_TASK.md` - exactly one recommended continuation.
- `src/lore2mud/engine/world.py` - authoritative runtime state with quest and item use logic.
- `src/lore2mud/engine/save.py` - save/load service (format v2).
- `src/lore2mud/content/loader.py` - schema-like and reference validation.
- `src/lore2mud/cli.py` - CLI entry point with play/validate subcommands.
- `pipeline/split_novel.py` - private-corpus preprocessing tool.
- `examples/original_demo/` - public, original playable fixture.
- `D:\MUD game kaifa\小说\processing\` - private external processing output; never commit.

## Risks and unknowns

- Only one quest type (monster_defeated) is implemented; more types need explicit
  decisions.
- The one-target-monster-per-quest constraint will need revisiting if shared-target
  quests are ever needed.
- Private corpus summaries, canon facts and game adaptation content have not been
  generated or reviewed.
- The provider's privacy claim about model visibility is not independently verified;
  do not send the entire corpus to a cloud model by default.
