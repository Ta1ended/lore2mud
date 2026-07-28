# Next Task

_Last updated: 2026-07-28_

## Status

公共核心 readiness audit 已完成，结论为 `CONDITIONAL GO`：在
`d81310c08ada7d2950dbfbcd1c431d42773c056e` 上，工作树干净，直接远端和
`origin/main` 均为 `1936e913348d3d46278ffaae2cfabf6502020835`，ahead/behind 为
`2/0`。完整 415 项测试、248 项聚焦测试、编译、原创内容包校验、历史安全门、Git
完整性检查和真实公开 CLI 主循环均通过。

这项 GO 只允许继续扩展完全原创的公共可玩内容；它不是引擎开发完成认证。项目负责人已将
小说事实层延后到公共引擎开发完成之后，私有小说的正文、事实、canon、摘要和派生内容继续
禁止读取、扫描、复制或提交，未来仍须新的明确范围授权。本地提交绝不自动 `git push`。

本阶段由 Codex / GPT-5.6-terra 自审与执行，不构成独立 GPT-5.6-sol 验收。

## Single next action

在通常的修改前 Terra 自审门禁后，完成一个**第二原创遭遇闭环**：仅用现有内容契约，为
`examples/original_demo/` 新增一间原创房间、一只新的确定性怪物和一条新的
`monster_defeated` 任务，使演示从三房间/一怪物/一任务扩展到四房间/两怪物/两任务。
不得增加新引擎机制、存档字段、私有事实或第三方内容。

## Acceptance criteria

- 数据流保持 `rooms.json` / `monsters.json` / `quests.json` → 既有 loader 跨引用校验 →
  `World.move()` / `World.attack()` / quest state → 既有 room/inventory save v5；游戏规则不移入 CLI。
- 只修改原创演示内容、相关公开测试/README/交接记录和必要的内容格式文档；不改
  `src/lore2mud/engine`，除非修改前审计发现明确且不可绕过的引擎缺口。
- 新实体使用稳定 ID，所有房间出口、怪物位置和任务目标一致且唯一；内容包版本由 v0.2.7
  升至 v0.2.8，save JSON 格式仍为 v5，旧内容包版本存档按既有规则被拒绝。
- 新增针对第二遭遇的加载、领域任务闭环、失败不变性、save/load 和真实 CLI 覆盖；运行全量
  unittest、compileall、原创内容校验、安全历史扫描、`git diff --check` 与真实 CLI 试玩。
- 完成后用实时 Git/远端证据更新 handoff；仅本地提交，不自动推送。
