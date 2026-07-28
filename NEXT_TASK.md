# Next Task

_Last updated: 2026-07-28_

## Status

`drop <物品ID或名称>` 已完成：它只把背包中的未装备物品放入当前房间，且成功后可再次
`take`；缺失、同名歧义、hand/body 已装备物品均在变更前被拒绝。现有 room/inventory
save v5 状态已覆盖其存档往返，无格式或内容包契约升级。11 项 `tests/test_drop.py` 测试和
完整 400 项测试、安全历史扫描、编译、原创内容校验、真实 `take → drop → look → take` CLI
试玩均于 2026-07-28 通过。

在本切片开始前，`HEAD`、`origin/main` 和直接查询的远端 `main` 都是
`1936e913348d3d46278ffaae2cfabf6502020835`；此前“仍为 `6c13fca`、尚待发布”的表述已
失效。当前本地检查点不自动推送，恢复时必须运行 `git status --short --branch`、
`git rev-list --left-right --count HEAD...origin/main`，并在发布前重新查询远端。

本切片依据项目负责人的临时流程例外由 Codex / GPT-5.6-terra 自审并执行；它不是独立
GPT-5.6-sol 验收。所有工作仍只涉及公共引擎与原创演示，未读取、复制、扫描或接入私有
小说资料。

## Single next action

在同样的修改前审计门禁后，完成一个确定性的单物品怪物战利品纵向切片：为怪物增加可选、
类型化的 `loot_item_id` 内容字段；怪物首次被击败时将该未摆放奖励物品放入当前房间，供玩家
用现有 `take` 拾取。

## Acceptance criteria

- 内容加载器、模型和 schema 对 `loot_item_id` 进行严格稳定 ID 与跨文件引用校验；奖励物品
  初始不得摆放在房间，也不得与对话奖励重复。
- `World.attack()` 仍是唯一战斗状态权威；战利品只在该怪物首次击败时出现一次，不能靠重复
  攻击复制，且失败路径不改变世界状态。
- 使用原创演示中的一件新、完全原创且初始隐藏的物品验证“击败 → 房间可见 → take”；不读取
  或引用私有小说内容。
- 利用现有 room/inventory 存档状态验证“击败后未拾取 → save → load → take”；除非新证据证明
  必要，不升级 save v5。
- 为领域、加载失败、命令/CLI 和存档往返添加聚焦测试；运行全量 unittest、compileall、
  原创内容校验、`scripts/check_repo_safety.py --history`、真实 CLI 试玩和 `git diff --check`。
- 完成后以实际 Git/远端证据同步四个交接文件；仅本地提交，不自动 `git push`。
