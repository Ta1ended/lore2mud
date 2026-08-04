# 下一任务 / Next Task

_最后更新 / Last updated: 2026-08-04_

## 中文

### 唯一下一门禁

**产品所有者另行明确授权或拒绝将已取得 TECH GO 与 PRODUCT PASS 的精确 V2-1
产品候选推送到远端工作流分支。**

精确产品候选 `d642a9d5e3ab9d9628d0f5cb8fa04a38d74de8d5` 已取得全新独立 TECH GO，
产品所有者已于 2026-08-04 明确给出 PRODUCT PASS。后续文档封存提交不得被误当作新的
产品候选。当前仍没有 push 授权；在新的明确授权前必须保持本地停止状态。

### 发布检查范围

- 使用实时 `git ls-remote` 和 GitHub Actions 重新确认远端 `main`、目标分支、祖先关系和
  绿色状态；本地 `origin/main` 不能代替实时证据。
- 只允许推送 `workstream/v2-1-game-session`，不得借此移动 `main`、创建 release 或开始
  V2-2；推送前必须再次确认 fast-forward/无冲突状态。
- 若命令行网络在获得 push 授权后再次失败，可使用 GitHub Desktop 添加隔离 worktree，
  核对分支与 HEAD、Fetch origin，再执行 Publish/Push；不得跳过远端祖先检查。

### 所需证据

- 人类产品所有者对 push/publication 的单独明确授权。
- 已获 TECH GO 与 PRODUCT PASS 的精确产品候选 SHA，以及仅文档封存提交的路径证明。
- 实时远端 SHA、目标分支 fast-forward 状态、GitHub Actions 和干净工作树证据。

### 禁止越界

- PRODUCT PASS 本身不授权 push、移动 `main`、SECURITY PASS、release 或 V2-2。
- 没有明确的新 push 授权，不得执行 Git CLI 或 GitHub Desktop 推送。
- 不得在产品门禁中扩展 Capability、SDK、structured CLI、MCP、`SimulationReport`、
  proofing、迁移、插件、新内容或新 save 版本。

## English

### Single Next Gate

**The product owner separately authorizes or declines pushing the exact V2-1 product
candidate that has received both TECH GO and PRODUCT PASS to the remote workstream
branch.**

Exact product candidate `d642a9d5e3ab9d9628d0f5cb8fa04a38d74de8d5` received fresh
independent TECH GO, and the product owner explicitly granted PRODUCT PASS on
2026-08-04. Later documentation-seal commits are not new product candidates. Push is
still unauthorized; the workstream must remain stopped locally until new explicit
authorization is received.

### Publication Review Scope

- Reconfirm live remote `main`, target branch, ancestry, and green GitHub Actions with
  `git ls-remote`; local `origin/main` is not live evidence.
- Only `workstream/v2-1-game-session` may be pushed. Do not move `main`, create a
  release, or start V2-2; reconfirm fast-forward/no-conflict status before push.
- If CLI networking fails after push authorization, GitHub Desktop may add the isolated
  worktree, verify branch and HEAD, Fetch origin, then Publish/Push. It must not bypass
  the live ancestry check.

### Required Evidence

- Separate explicit human authorization for push/publication.
- The exact TECH-GO and PRODUCT-PASS product SHA plus proof that later seal changes are
  documentation only.
- Live remote SHA, target-branch fast-forward status, GitHub Actions, and clean-tree
  evidence.

### Boundaries

- PRODUCT PASS does not authorize push, `main` movement, SECURITY PASS, release, or
  V2-2.
- Do not push with Git CLI or GitHub Desktop without new explicit push authorization.
- The product gate cannot expand into Capability, SDK, structured CLI, MCP,
  `SimulationReport`, proofing, migrations, plugins, new content, or a new save version.
