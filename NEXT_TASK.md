# Next Task

_Last updated: 2026-07-31（L2W-3 独立验收 GO；项目暂停）_

## Single next action

项目负责人恢复开发后，先确认 GPT-5.6-sol 可用并核实 `HEAD`、`origin/main`、实时远端
和 ahead/behind；随后实施一个范围受限的 L2W-4：让经过验证的 CanonRegistry v1 通过
显式人工计划生成与 L2W-2 相同规模的可玩 micro content pack（1 room、1 character、
1 item、1 game-only quest、1 game-only dialogue），同时保留多章复合 provenance。

## Acceptance scope

- 新人工计划必须显式选择 registry entity 与复合 claim 来源，不得从冲突 claims 中静默
  选择、合并或推断游戏文本/数值。
- 输出规模和游戏行为保持 L2W-2 micro profile，不扩展多房间、怪物、商店、效果或 save。
- `canon_ref` 与 manifest 能追溯 registry ID、registry version、来源 promotions/chapters 和
  每条采用 claim 的 `(promotion_id, source_entity_id, source_claim_id)`。
- 新增严格 Python 验证、Draft 2020-12 Schema、公开虚构 golden fixture、格式文档、原子
  CLI writer、真实 loader/playthrough 和失败不写入测试。
- 保持现有 CanonDraft + AdaptationPlan v1 路径兼容；不修改 `src/`、original_demo、save、
  依赖或任何私有资料。

## Boundaries

- L2W-3 已独立验收 GO（DEC-0062）；当前按项目负责人要求暂停，未授权今天继续实施。
- L2W-4 不包含语义冲突裁决、mutable registry/query、多房间扩容或私有资料处理。
- 全程使用 GPT-5.6-sol；不可用时停止并报告，不切换模型。
- 本地提交不自动 push；恢复时先实时核实 Git，网络不佳可由项目负责人使用 GitHub Desktop。

## Queue

- L2W-4 实施与本地验证完成后，使用新的 GPT-5.6-sol 任务或干净上下文只读验收真实提交。
