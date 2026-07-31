# Next Task

_Last updated: 2026-07-31（L2W-4 独立验收 GO；L2W-5 已选定）_

## Single next action

实现 L2W-5：从经过验证的 CanonRegistry v1 与显式
`RegistryInspectionPlan v1` 生成确定性的只读 `RegistryInspectionReport v1`。
人工计划只按稳定 registry entity ID 选择一个或多个实体；报告完整保留所选实体的类型、
名称、aliases、members、candidates、全部复合 claim 来源和所需 source records，供后续
adaptation 规划前审阅。编译器不得搜索显示名称、推断身份、裁决冲突或修改输入。

## Acceptance scope

- Plan 必须精确匹配 registry ID/version，至少选择一个现有实体，拒绝重复、未知或
  非稳定 ID；报告必须恰好覆盖选择集合并使用确定排序。
- 每个选中实体必须逐字段保留 registry 中的 aliases、members、candidates 与 claims；
  复合 claim identity 保持 `(promotion_id, source_entity_id, source_claim_id)`，不得去重、
  改写或省略冲突 claims。
- 报告只包含所选 claims 实际引用的完整 source records，并校验 promotion/chapter 对应；
  输入 registry 在成功与失败路径都保持逐字节不变。
- 新增严格 Python 契约、Draft 2020-12 plan/report Schemas、公开虚构 golden fixture、格式文档、
  确定性 CLI 与原子单文件 writer；测试覆盖非法选择、完整性、golden bytes、失败不写入和真实 CLI。
- 保持 CanonRegistry、L2W-2 和 L2W-4 路径兼容；不修改 `src/`、original_demo、save 或依赖。

## Boundaries

- L2W-4 已独立验收 GO（DEC-0064）；L2W-5 只增加公开安全的只读 inspection artifact。
- 不读取、扫描或复制私有小说、摘要、canon 或改编内容；只使用公开虚构 fixture。
- 不增加模糊查询、全文/语义检索、mutable registry、冲突裁决、adaptation 或多房间输出。
- 全程使用 GPT-5.6-sol；不可用时停止并报告，不切换模型。
- 本地提交不自动 push；恢复时先实时核实 Git，网络不佳可由项目负责人使用 GitHub Desktop。

## Queue

- L2W-5 本地实现与全量验证后创建本地提交，再由新的 GPT-5.6-sol Codex 任务或干净上下文
  只读给出 GO/REVISE；REVISE 时只修复 findings，不扩大范围。
