# Next Task

_Last updated: 2026-07-30（Phase 1.0 实现完成；独立验收待定）_

## Single next action

交回 GPT-5.6-sol 独立验收 Phase 1.0 fact-candidate document validation contract（DEC-0037）。
验收通过前不得开始 Phase 1.1 或任何后续切片。

## Boundaries

- Phase 1.0 实现位于 `pipeline/fact_candidates.py`，不涉及 `src/`、现有 Schema、
  original_demo 或 save 格式。
- 119 项聚焦测试和 718 项全量测试通过；compileall、内容校验、安全扫描和 diff 检查均通过。
- 新增 5 个文件，更新 6 个文件（详见 DEC-0037）。
- 实现完成不等于独立验收 GO。

## Queue

- 无排队实施项；后续事项（manifest 跨文件校验、审核、归并、canon、模型调用）
  均须独立验收通过后由项目负责人重新明确授权。
