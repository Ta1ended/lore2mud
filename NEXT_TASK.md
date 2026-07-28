# Next Task

_Last updated: 2026-07-28（M1 recovery 完成后）_

## Status

M1 确定性死亡恢复已完成并自审：`World.recover()` + `_require_alive()` 统一门禁 +
命令层门禁 + 55 项新测试，全量 470 项测试通过、编译、内容校验、安全扫描和真实 CLI
冒烟均通过。save format 保持 v5，内容包保持 v0.2.7。本地提交不自动推送。

本阶段由 Hermes agent 自审与执行，不构成独立 GPT-5.6-sol 验收。

## Single next action

在通常的修改前自审门禁后，完成一个**第二原创遭遇闭环**：仅用现有内容契约，为
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
