# Next Task

_Last updated: 2026-07-31（L2W-5 本地实现与验证完成；远端同步门）_

## Single next action

由项目负责人使用 GitHub Desktop push 当前本地 `main`，使 GitHub 与包含 DEC-0065 的
L2W-5 实现/交接提交同步。恢复后 Codex 首先核对工作树、`origin/main`、GitHub `main` 和
ahead/behind；在远端不再落后本地超过 5 个提交前，不启动新实现或独立验收。

## Push gate

- 提交前 GitHub API 已确认 `main=a89fdc6d819b976b80b82a74e575ff851ba86448`；
  L2W-5 baseline 为 `9f09d9691a236919648cea294c31fcdf0f105ff9`，当时 ahead/behind `5/0`。
- L2W-5 的实现提交是 baseline 后第一个、同时包含 DEC-0065 的本地提交；以恢复时真实
  `git rev-parse HEAD` 为准。
- 本地提交不会由 Codex 自动 push。网络不佳时只使用 GitHub Desktop，不反复重试长时间
  命令行 push。

## Queue After Push

- 使用新的 GPT-5.6-sol Codex 任务或干净上下文，对 baseline `9f09d969` 到 L2W-5
  实现提交执行只读独立验收并给出 GO/REVISE。复核真实 diff、精确 ID selection、完整
  entity/member/candidate/claim 复制、claim-source 子集、冲突和外部 relation 保留、Schema、
  golden、原子 writer、input/output alias、真实 CLI、安全门和 Git 快照。
- GO 后追加 DEC-0066（或对应后续决定）并同步交接；REVISE 时只修复 findings，不扩大
  L2W-5。独立验收前后均不读取私有资料，不启动 fuzzy/full-text/semantic search、mutable
  registry、adaptation、多房间扩容、`src/`、original_demo、save 或依赖变更。

## Boundaries

- 全程使用 GPT-5.6-sol；不可用时停止并报告，不切换模型。
- 当前 L2W-5 只有本地验证，独立验收 pending；实现上下文不得自宣 GO。
- 不自动 push，不发布，不读取、扫描或复制私有小说、摘要、canon 或改编内容。
