# Next Task

_Last updated: 2026-08-01（NarrativeModel v1 已本地验证；独立验收待办）_

## Single next action

为 `D:\MUD game kaifa\.codex-worktrees\narrative-model-v1` 的
`workstream/narrative-model-v1` 发起新的 GPT-5.6-sol 干净上下文、只读独立验收。验收
范围是 `e6070bd7ba31e0a5e45dfdf4e213b51e9f3f0ca1..HEAD`；先运行
`git rev-parse HEAD` 记录最终候选提交。不得以实现任务自己的本地验证替代独立 `GO`。

## Re-review gate

- 审核严格 plan/model Schema、真实整数版本、完整 claim use/omission 记账、来源 promotion
  snapshot、phase 连续性、DAG/引用/披露规则以及确定性排序。
- 审核 compiler 对未知实体、foreign/missing claims、非 canonical typed input 的拒绝，以及
  writer 的 prevalidation、atomic replace、failure preservation 与 alias 防护。
- 复核 43 项专门测试（2 Windows symlink 权限跳过）、1297 项 full unittest 和 1288 项
  pytest（各 9 skips）、Ruff、Pyright、compileall、original demo 校验、history safety、
  fsck、diff 检查和仓库外 CLI/golden bytes。
- 复核 `PROJECT_MEMORY.md`、`PROJECT_STATE.md`、`NEXT_TASK.md`、`CHANGELOG.md` 和
  `DECISIONS.md` 的描述仍为“独立验收 pending”，不提前宣称 GO。

## Boundaries

- 本次验收只覆盖 NarrativeModel v1；不修改 GEN-1 或其他责任域。
- 不修改 `main`、不整合、不 push、不 release；独立 GO 后也仍需项目负责人明确授权。
- 不读取、扫描或复制私有小说、章节、摘要、canon 或派生改编内容。
