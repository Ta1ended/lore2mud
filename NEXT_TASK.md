# Next Task

_Last updated: 2026-07-30（Phase 1.0 聚焦修正完成；聚焦复验待定）_

## Single next action

交回 GPT-5.6-sol 聚焦复验 Phase 1.0 fact-candidate validation（DEC-0037 + DEC-0038）。
复验通过前不得开始 Phase 1.1 或任何后续切片。

## Boundaries

- 聚焦修正关闭 P1-1（enum TypeError）、P1-2（numeric int precision）、P2（Schema 约束）。
- 131 项聚焦测试通过；730 项全量测试通过；compileall、内容校验、安全扫描和 diff 检查均通过。
- 相对 e2b8136 的 diff 仅含允许文件。

## Queue

- 无排队实施项；后续事项（manifest 跨文件校验、审核、归并、canon、模型调用）
  均须聚焦复验通过后由项目负责人重新明确授权。
