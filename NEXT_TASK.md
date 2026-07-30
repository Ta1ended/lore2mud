# Next Task

_Last updated: 2026-07-31（L2W-3 本地实现完成；独立验收 pending）_

## Single next action

使用新的 Codex GPT-5.6-sol 任务或干净上下文，对 L2W-3 从基线
`b22bee33cacb154a2efc7e4eef0e3182ccc8319c` 到恢复时的当前实施 HEAD 做只读
独立验收，并给出 GO/REVISE。验收任务不得修改代码或仅复述实现报告。

## Acceptance scope

- 核对 RegistryPlan/CanonRegistry v1 的严格字段、稳定 ID、NFKC 别名规则和冻结模型。
- 核对 2+ 唯一来源、source entity 恰好覆盖一次、合并类型一致、source/member/claim
  provenance 完整、每个 registry entity 每个 promotion 最多一个 member，以及同名或
  冲突 claim 不被去重或覆盖。
- 核对 relation 从章内 entity ID 到 registry ID 的确定性改写和悬空引用拒绝。
- 核对集合/JSON 顺序确定性、golden fixture、输入输出同文件拒绝、预校验、flush/fsync、
  原子替换、失败保留旧输出和临时文件清理。
- 重跑 `python -m unittest tests.test_canon_registry -v`、全量 unittest、compileall、
  original-demo 校验、历史安全检查、fsck、diff 检查和仓库外真实 CLI 往返。
- 确认 diff 不含私有小说、`src/`、游戏内容 Schema、original_demo、save 或依赖改动。

## Boundaries

- 当前只有本地验证，不是独立验收 GO（DEC-0060）。
- 不开始 L2W-4、语义冲突裁决、mutable registry/query、一般化游戏改编或私有资料处理。
- 本地提交不自动 push；需要 push 时先实时核实 Git，再由项目负责人明确授权，网络不佳时
  可由项目负责人使用 GitHub Desktop 手动完成。

## Queue

- 独立验收 GO 后记录验收决定并同步交接；后续切片仍需新的范围授权。
