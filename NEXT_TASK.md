# Next Task

_Last updated: 2026-07-31（已验收候选已同步到本地 main；等待 push 授权）_

## Single next action

项目负责人明确授权后，由中控 push 当前干净的本地 `main`。本地 `main` 已通过
fast-forward 接收集成封板 `3dafa23bfcfbda63263b65080a96d602f2d5ccbd`，其中的
已验收代码候选为 `a172a82a0c70812b8ff5429de3ec4b309ad75cd5`；其后只有
记录本地同步状态的交接文档提交。

## Publish gate

- 独立验收已经完成，不再重复运行第三轮全量验收（DEC-0068）。
- 发布前重新 fetch，并确认直接查询的 GitHub `main` 仍与本地 tracking
  `origin/main=13be791bc0a116f6596267b5d914a8a63e511f1f` 一致。本轮远端查询曾遇到
  connection reset，因此不得省略该刷新。
- 确认本地 `main` 工作树干净，且 `origin/main..main` 只包含已验收集成提交和纯交接提交；
  若远端或候选代码发生变化，停止并重新评估差异，不盲目 push。
- push 后再次核对 GitHub `main` 与本地 `main` 指向同一封板提交，并保留产物来源提交
  `a172a82a0c70812b8ff5429de3ec4b309ad75cd5` 的 manifest/hash 证据。

## Queue After Publish

- 基于已交付的 Core、Forge、Player、Quality 和 Ship 能力，重新规划下一轮责任域；在新的
  明确授权前不自动启动实现、release 或私有小说处理。

## Boundaries

- 全程使用 GPT-5.6-sol；不可用时停止并报告，不静默切换模型。
- 后续 `main` 修改、push 和 release 都不自动执行，必须由项目负责人明确授权。
- 不读取、扫描或复制私有小说、摘要、canon 或改编内容。
