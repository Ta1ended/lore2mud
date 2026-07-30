# Next Task

_Last updated: 2026-07-31（L2W-3 验收修正完成；第二次独立验收 pending）_

## Single next action

使用新的 Codex GPT-5.6-sol 任务或干净上下文，对 L2W-3 初始提交
`a89fdc6d819b976b80b82a74e575ff851ba86448` 到恢复时的当前修正 HEAD 做只读
独立复验，并给出 GO/REVISE。复验任务不得修改代码或仅复述实现报告。

## Acceptance scope

- 确认 relation claim 的 registry 目标必须恰好含一个相同 `promotion_id` member，不能
  指向仅由其他章节 member 支撑的现存 entity。
- 确认 `(promotion_id, source_candidate_id)` 在所有 registry members 中唯一，并保留既有
  source entity、claim、chapter 与审核 provenance 约束。
- 确认 writer、同进程 CLI 和真实 subprocess CLI 输出与 `expected_registry.json` bytes
  完全相等，包含 UTF-8、缩进和末尾换行。
- 确认 output 与输入的普通路径、hardlink、可创建时的 symlink 别名均拒绝且输入不变。
- 回归核对 RegistryPlan/CanonRegistry v1 的严格字段、稳定 ID、NFKC、冻结模型、2+ 来源、
  完整覆盖、类型一致、relation 改写、冲突 claim 保留、确定性与原子 writer 契约。
- 重跑 `python -m unittest tests.test_canon_registry -v`、全量 unittest、compileall、
  original-demo 校验、历史安全检查、fsck、diff 检查和仓库外真实 CLI 往返。
- 确认 diff 不含私有小说、`src/`、游戏内容 Schema、original_demo、save 或依赖改动。

## Boundaries

- 当前修正只有本地验证，不是独立验收 GO（DEC-0061）。
- 不开始 L2W-4、语义冲突裁决、mutable registry/query、一般化游戏改编或私有资料处理。
- 本地提交不自动 push；需要 push 时先实时核实 Git，再由项目负责人明确授权，网络不佳时
  可由项目负责人使用 GitHub Desktop 手动完成。

## Queue

- 独立验收 GO 后记录验收决定并同步交接，再按项目负责人当前持续授权自主选择下一个
  范围受限、可验证的纵向切片。
