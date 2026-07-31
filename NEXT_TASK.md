# Next Task

_Last updated: 2026-07-31（五域整合候选已独立验收 GO；等待发布授权）_

## Single next action

项目负责人明确授权后，由中控将干净的 `coord/parallel-sprint-integration` 当前 HEAD
fast-forward 到 `main` 并 push。该分支包含已验收代码候选
`a172a82a0c70812b8ff5429de3ec4b309ad75cd5` 及其后的纯交接封板提交。

## Publish gate

- 独立验收已经完成，不再重复运行第三轮全量验收（DEC-0068）。
- 发布前重新 fetch 并核对本地 `main`、`origin/main` 与直接查询的 GitHub `main` 都仍为
  `13be791bc0a116f6596267b5d914a8a63e511f1f`，集成分支工作树干净且可 fast-forward。
- 只允许合入已经验收的集成提交和纯交接封板提交；若远端或候选代码发生变化，停止并重新
  评估差异，不盲目 push。
- push 后再次核对 GitHub `main` 与本地 `main` 指向同一封板提交，并保留产物来源提交
  `a172a82a0c70812b8ff5429de3ec4b309ad75cd5` 的 manifest/hash 证据。

## Queue After Publish

- 基于已交付的 Core、Forge、Player、Quality 和 Ship 能力，重新规划下一轮责任域；在新的
  明确授权前不自动启动实现、release 或私有小说处理。

## Boundaries

- 全程使用 GPT-5.6-sol；不可用时停止并报告，不静默切换模型。
- `main` 修改、push 和 release 都不自动执行，必须由项目负责人明确授权。
- 不读取、扫描或复制私有小说、摘要、canon 或改编内容。
