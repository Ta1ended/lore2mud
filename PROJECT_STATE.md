# Project State

_Last updated: 2026-07-27_

## Objective

提供可公开托管的 Python 文字 MUD 引擎与小说资料处理基底，让私人小说原文和
改编内容始终与通用代码、原创示例分离。

## Current status

0.1.0 仓库基底已形成可安装、可玩的本地单人纵向闭环。内容包会在创建世界前
检查结构、稳定 ID、未知字段与跨文件引用；原创演示可完成查看、移动、拾取、
背包、两回合战斗和升级。

## Completed

- `src/lore2mud/` 实现标准库运行时、双 CLI 入口和领域模块。
- `examples/original_demo/` 提供三个原创房间、一个物品和一个怪物。
- `pipeline/` 提供保守拆章和 manifest 生成入口。
- `schemas/` 与 `src/lore2mud/content/` 定义并校验内容契约。
- `scripts/check_repo_safety.py` 与 `.gitignore` 建立公开/私有内容边界。
- `tests/` 覆盖核心玩法、非法内容引用、拆章和安全检查。
- `docs/`、`AGENTS.md` 与 GitHub 基础文件已建立。

## In progress

- None.

## Blockers

- None.

## Verification

- `python -m unittest discover -s tests -v` - 20 tests passed (2026-07-27).
- `python scripts/check_repo_safety.py` - passed (2026-07-27).
- `python -m compileall -q src pipeline scripts tests` - passed (2026-07-27).
- Editable install plus `python -m pip check` - passed (2026-07-27).
- Installed `lore2mud` and `python -m lore2mud` smoke runs - passed (2026-07-27).

## Key paths

- `AGENTS.md` - Hermes and other Agent constraints.
- `src/lore2mud/engine/world.py` - authoritative runtime state.
- `src/lore2mud/content/loader.py` - schema-like and reference validation.
- `examples/original_demo/` - public, original playable fixture.
- `docs/hermes_workflow.md` - GPT adviser and Hermes execution loop.
- `NEXT_TASK.md` - single recommended continuation.

## Risks and unknowns

- Runtime state is in memory only; no save/load compatibility contract exists yet.
- Quest and character formats are validation placeholders without gameplay behavior.
- The default chapter-heading pattern is deliberately conservative and must be
  adapted and verified for each private novel source.
