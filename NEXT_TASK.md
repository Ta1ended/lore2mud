# Next Task

_Last updated: 2026-07-29（M6 已本地实现并验证，等待独立验收）_

## Single next action

由 GPT-5.6-sol 对 M6 `examine`、`help [command]`、集中命令注册表、死亡/对话边界、
只读状态不变性和真实 CLI/save v7 证据进行独立验收。验收前不得把 M6 表述为 GO，
不得开始 M7 或其他功能实现。

## Review focus

- 核对 `World.examine()` 只暴露当前房间/背包可见实体，其他房间、未掉落战利品和
  未获得对话奖励保持不可见。
- 核对无类型精确 ID 优先、跨类型同名/重复 ID 歧义，以及显式
  `item|monster|character` 限定；歧义夹具必须仅存在于测试内存。
- 核对 `examine` 空参数、`room|here` 保留词、额外参数、空目标和数字目标的精确文本；
  `inspect` 的物品专用 API/输出及裸数字对话兼容必须保持。
- 核对 `CommandSpec` 与真实路由、别名、总帮助、`help [command]` 和死亡允许集合双向
  一致，且 DEC-0020 死亡门禁仍先于对话和未知命令判断。
- 复跑 22 项 M6 专项、相关回归、591 项全量测试、compileall、内容包校验、安全扫描、
  diff 检查及仓库外 CLI；确认 original_demo 仍为 0.6.0、save 仍为 v7。

## Queue

- M7 仅可在 M6 独立验收 GO 后，由项目负责人另行明确授权。
