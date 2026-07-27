# Project State

_Last updated: 2026-07-28_

## Objective

提供可公开托管的 Python 文字 MUD 引擎与小说资料处理基底，让私人小说原文和
改编内容始终与通用代码、原创示例分离。

## Current status

版本化本地存档/读档功能已实现并通过全部验证。游戏支持 `save`/`load` 指令，
存档包含完整可变状态快照，加载时严格校验不可信数据，写入使用原子替换。

## Completed

- `src/lore2mud/` 实现标准库运行时、双 CLI 入口和领域模块。
- `examples/original_demo/` 提供三个原创房间、一个物品和一个怪物。
- `pipeline/` 支持 UTF-8/GBK/GB18030、章卷分离、稳定顺序 ID 和 manifest v2。
- `schemas/` 与 `src/lore2mud/content/` 定义并校验内容契约。
- `scripts/check_repo_safety.py` 与 `.gitignore` 建立公开/私有内容边界。
- `tests/` 覆盖核心玩法、非法内容引用、拆章和安全检查。
- 私有小说已在仓库外完成一次受控拆章；原文未修改，章节重建校验通过。
- `docs/`、`AGENTS.md`、GitHub 基础文件和项目交接文件已建立。
- 版本化本地存档/读档：`save`/`load` 指令、`SaveLoadService`、原子写入、
  严格验证、54 项新测试、CLI 冒烟测试通过。

## In progress

- None.

## Blockers

- None.

## Verification

- `python -m unittest discover -s tests -v` - 90 tests passed (2026-07-28).
- `python scripts/check_repo_safety.py` - passed (2026-07-28).
- `python -m compileall -q src pipeline scripts tests` - passed (2026-07-28).
- CLI save/load smoke test - passed (2026-07-28).

## Key paths

- `PROJECT_MEMORY.md` - fresh-session restart instructions and pause rules.
- `AGENTS.md` - Hermes and other Agent constraints.
- `NEXT_TASK.md` - exactly one recommended continuation.
- `src/lore2mud/engine/world.py` - authoritative runtime state.
- `src/lore2mud/engine/save.py` - save/load service with atomic writes.
- `src/lore2mud/content/loader.py` - schema-like and reference validation.
- `pipeline/split_novel.py` - private-corpus preprocessing tool.
- `examples/original_demo/` - public, original playable fixture.
- `D:\MUD game kaifa\小说\processing\` - private external processing output; never commit.

## Risks and unknowns

- Quest and character formats are validation placeholders without gameplay behavior.
- Private corpus summaries, canon facts and game adaptation content have not been
  generated or reviewed.
- The provider's privacy claim about model visibility is not independently verified;
  do not send the entire corpus to a cloud model by default.
