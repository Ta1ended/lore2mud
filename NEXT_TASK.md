# Next Task

_Last updated: 2026-08-01（Windows CI UTF-8 热修独立验收 GO；本地 main 待 push）_

## Single next action

项目负责人从 `D:\MUD game kaifa\lore2mud` push 当前本地 `main` 到 GitHub。
该分支只比已发布基线 `6761e0850a367308a29f9b8189cb08715fb0cb03` 多一个
已验收 Windows UTF-8 热修提交（DEC-0070）。

## Publish gate

- push 前 fetch 或直接查询 GitHub `main`，确认它仍为 `6761e08`；若远端已变化，
  停止 push 并重新核对 ancestry，不做强制推送。
- 确认工作树干净，`git rev-list --left-right --count origin/main...main` 为 `0 1`，
  且唯一新增提交只包含 `src/lore2mud/cli.py`、Windows launcher、CLI 回归测试和
  五个同步交接文件。
- push 后确认 GitHub `main` 等于本地 `HEAD`，并观察新的 `quality` 与 `tests`
  workflow；特别确认 `windows-candidate` 的 `Test Windows packaging` 和后续
  clean candidate 冷启动均成功。

## Acceptance evidence

- DEC-0070 对相对 `6761e08` 的完整 diff 给出 GO、无 P0-P3 findings。
- 真实 pinned PyInstaller 6.21.0 与 zipapp 的仓库外诊断、console、Web/API 冷启动通过；
  全量 unittest `1254 / 7 skipped`，聚焦 pytest `38 passed`，xdist pytest
  `1247 passed / 7 skipped`，Ruff、Pyright、compileall、内容校验、安全扫描、fsck
  和 diff 检查全部通过。

## Boundaries

- 全程使用 GPT-5.6-sol；不可用时停止并报告，不静默切换模型。
- 不自动 release 或启动下一切片；本任务按项目负责人要求停在本地可推送状态。
- 不读取、扫描或复制私有小说、摘要、canon 或改编内容。
