# Project State

_Last updated: 2026-07-27_

## Objective

提供可公开托管的 Python 文字 MUD 引擎与小说资料处理基底，让私人小说原文和
改编内容始终与通用代码、原创示例分离。

## Current status

项目已暂停在一个可恢复的验证检查点。公共代码基线为提交 `79aa3d5`；
本次检查点已保存为本地 handoff 提交，待网络可用时再推送到 `origin/main`。
游戏基底和小说拆章管线均已验证；私有小说章节及 manifest 保存在仓库外。
存档/读档尚未实现，下一次恢复应从 `NEXT_TASK.md` 的唯一任务开始。

## Completed

- `src/lore2mud/` 实现标准库运行时、双 CLI 入口和领域模块。
- `examples/original_demo/` 提供三个原创房间、一个物品和一个怪物。
- `pipeline/` 支持 UTF-8/GBK/GB18030、章卷分离、稳定顺序 ID 和 manifest v2。
- `schemas/` 与 `src/lore2mud/content/` 定义并校验内容契约。
- `scripts/check_repo_safety.py` 与 `.gitignore` 建立公开/私有内容边界。
- `tests/` 覆盖核心玩法、非法内容引用、拆章和安全检查。
- 私有小说已在仓库外完成一次受控拆章；原文未修改，章节重建校验通过。
- `docs/`、`AGENTS.md`、GitHub 基础文件和项目交接文件已建立。

## In progress

- None. 项目当前是有意暂停，不代表存档功能已完成。

## Blockers

- None.

## Verification

- `python -m unittest discover -s tests -v` - 36 tests passed (2026-07-27).
- `python scripts/check_repo_safety.py` - passed (2026-07-27).
- `python -m compileall -q src pipeline scripts tests` - passed (2026-07-27).
- Private corpus reconstruction - decoded source and split chapters matched in
  character count and SHA-256 (2026-07-27).
- `git status --porcelain` - clean before this handoff; code baseline `79aa3d5`
  was on `origin/main` (2026-07-27).

## Key paths

- `PROJECT_MEMORY.md` - fresh-session restart instructions and pause rules.
- `AGENTS.md` - Hermes and other Agent constraints.
- `NEXT_TASK.md` - exactly one recommended continuation.
- `src/lore2mud/engine/world.py` - authoritative runtime state.
- `src/lore2mud/content/loader.py` - schema-like and reference validation.
- `pipeline/split_novel.py` - private-corpus preprocessing tool.
- `examples/original_demo/` - public, original playable fixture.
- `docs/hermes_workflow.md` - GPT adviser and Hermes execution loop.
- `D:\MUD game kaifa\小说\processing\` - private external processing output; never commit.

## Risks and unknowns

- Runtime state is in memory only; no save/load compatibility contract exists yet.
- Quest and character formats are validation placeholders without gameplay behavior.
- Private corpus summaries, canon facts and game adaptation content have not been
  generated or reviewed.
- The provider's privacy claim about model visibility is not independently verified;
  do not send the entire corpus to a cloud model by default.
