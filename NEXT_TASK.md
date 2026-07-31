# Next Task

_Last updated: 2026-08-01（GEN-1 REVISE 修复已本地验证；独立复验待办）_

## Single next action

为 `D:\MUD game kaifa\.codex-worktrees\gen1-narrative-conditions` 的
`codex/gen1-narrative-conditions` 发起新的 GPT-5.6-sol 干净上下文、只读独立验收。
验收范围是 `e6070bd7ba31e0a5e45dfdf4e213b51e9f3f0ca1..HEAD`；先运行
`git rev-parse HEAD` 记录最终候选提交。不要以实现任务自身的本地测试代替该结论。

## Re-review gate

- 确认显式 JSON `minimum: null` 和 `maximum: null` 均由内容 loader 拒绝，而缺失字段
  仍表示无整数边界。
- 确认 `packaging/windows/README.md` 的 save 目录、兼容性和 Ship contract 都描述
  original_demo `0.10.0` 与 save v8，且 v7 只对无状态定义内容包只读兼容。
- 确认 `PROJECT_MEMORY.md`、`PROJECT_STATE.md`、`NEXT_TASK.md`、`CHANGELOG.md` 和
  `DECISIONS.md` 均准确记录初审 REVISE、修复和“独立复验 pending”。
- 复核 17 项 GEN-1、13 项 Windows packaging、1272 项 full unittest 和 1265 项 pytest
  （各 7 skips）、Ruff、Pyright、compileall、`lore2mud validate --content examples/original_demo`、
  `check_repo_safety.py --history`、`git fsck --full --no-dangling` 与 `git diff --check`。

## Boundaries

- 本次 GEN-1 复验职责仅覆盖三项 REVISE 修复；不修改独立的 NarrativeModel 工作流或
  任何其他责任域。
- 不修改 `main`、不整合、不 push、不 release；得到新的独立 `GO` 后也仍需项目负责人
  明确授权这些动作。
- 不读取、扫描或复制私有小说、章节、摘要、canon 或派生改编内容。
