# Next Task

_Last updated: 2026-07-31（L2W-4 本地实现与验证完成；独立验收 pending）_

## Single next action

使用新的 GPT-5.6-sol Codex 任务或干净上下文，对当前 L2W-4 本地实现提交执行只读独立
验收：复核真实 diff、严格 plan/manifest 合同、golden/CLI/loader/World 证据、安全门和
Git 快照，并给出 GO 或 REVISE。实现上下文不得自宣 GO。

## Acceptance scope

- 新人工计划必须显式选择 registry entity 与复合 claim 来源，不得从冲突 claims 中静默
  选择、合并或推断游戏文本/数值。
- 输出规模和游戏行为保持 L2W-2 micro profile，不扩展多房间、怪物、商店、效果或 save。
- `canon_ref` 与 manifest 能追溯 registry ID、registry version、来源 promotions/chapters 和
  每条采用 claim 的 `(promotion_id, source_entity_id, source_claim_id)`。
- 已新增严格 Python 验证、Draft 2020-12 Schema、公开虚构 golden fixture、格式文档、
  原子 CLI writer、真实 loader/playthrough 和失败不写入测试；复验时须重新运行关键证据。
- 保持现有 CanonDraft + AdaptationPlan v1 路径兼容；不修改 `src/`、original_demo、save、
  依赖或任何私有资料。

## Boundaries

- L2W-3 已独立验收 GO（DEC-0062）；项目负责人已恢复持续 goal 与开发。
- L2W-4 不包含语义冲突裁决、mutable registry/query、多房间扩容或私有资料处理。
- 全程使用 GPT-5.6-sol；不可用时停止并报告，不切换模型。
- 本地提交不自动 push；恢复时先实时核实 Git，网络不佳可由项目负责人使用 GitHub Desktop。

## Queue

- 独立验收结论 GO 后，记录 DEC-0064（或对应后续决定），同步本地提交快照；REVISE
  则只修复 findings，不扩大 L2W-4 范围。
