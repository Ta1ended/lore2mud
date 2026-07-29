# Next Task

_Last updated: 2026-07-29（M7.1 已本地实现并验证，等待独立验收）_

## Single next action

由 GPT-5.6-sol 对 M7.1 第二个原创遭遇进行独立验收：核对碎讯支线与火花巡兽的双向引用、
观测站触发的 `quest_clear_spark_hound`、既有确定性战斗/任务结算、内容包 0.7.0 与 save v7，
以及仓库外 CLI/save 证据。验收前不得把 M7 表述为 GO，不得开始 M7.2 或 push。

## Review focus

- 核对本切片只新增原创内容和相应测试/文档；`src/`、Schema、命令、存档格式与私有资料均未改动。
- 核对观测站 east 与碎讯支线 west 互相指向，火花巡兽只在碎讯支线，任务只在进入观测站后接取。
- 核对击败火花巡兽使用现有 `monster_defeated` 结算一次，0.6.0 内容包存档由 v7 既有版本检查拒绝。
- 复跑 4 项 M7、15 项 loot、595 项全量测试、compileall、内容校验、安全扫描、diff 检查与
  仓库外 CLI/save v7；确认 M7 仍只有 4/8 房间和 2/4 怪物，尚未完成。

## Queue

- 只有 M7.1 独立验收 GO 且项目负责人再次明确授权后，才能开始下一项 M7 内容扩容切片。
