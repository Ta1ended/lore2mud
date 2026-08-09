# 下一任务 / Next Task

更新日期：2026-08-08

## 中文

### 唯一下一任务

**等待产品所有者给出新的、明确的产品决定，指定 V2-4A 之后要做什么。**

### 当前依据

- V2-4A 产品候选为 `badc9a20816a9515b24c98199ca37323a02c1b00`，分支为
  `workstream/v2-4a-provenance-rights-20260807-r2`，基线为
  `36ff77fb5daa3407a79b0b2359a03a49a63003a0`。
- 全新只读 TECH reviewer 给出 `GO`，产品 reviewer 给出 `PRODUCT PASS`，独立 SECURITY reviewer
  给出 `GO`；三份 findings 均为 P0-P3 空。
- 最终矩阵包括 focused V2-4 `56 passed`、公开安全 30–60 分钟故事弧 smoke `1 passed`、全量 pytest
  `1619 passed, 3 skipped`、全量 unittest `1622 tests OK, skipped=3`，以及 Ruff、Pyright、compileall、
  Demo validation、`pip check`、history safety、fsck 和 diff checks 全部通过。
- 当前 local `main`、live `origin/main` 与 `origin/workstream/v2-3-capability-modules` 均为
  `36ff77fb5daa3407a79b0b2359a03a49a63003a0`。V2-4A 从未 push、合并或发布。

### 不得自动执行

- 不 push、不合并、不移动 `main`、不 release、不分发 sealed candidate，也不访问私人材料。
- 不自动进入 V2-5、Workbench、动态插件、多人运行或运行时模型裁决。
- 主工作树的未跟踪 `uv.lock` 是用户保留文件，不纳入候选或文档封存提交。

## English

### Single Next Task

**Await a new, explicit product-owner decision that names the work after V2-4A.**

### Current Basis

- The V2-4A product candidate is `badc9a20816a9515b24c98199ca37323a02c1b00` on
  `workstream/v2-4a-provenance-rights-20260807-r2`, based on
  `36ff77fb5daa3407a79b0b2359a03a49a63003a0`.
- A fresh read-only TECH reviewer returned `GO`, the product reviewer returned `PRODUCT PASS`, and an
  independent SECURITY reviewer returned `GO`; all three findings reports are P0-P3 empty.
- The final matrix includes focused V2-4 `56 passed`, public-safe 30–60 minute story-arc smoke `1 passed`, full
  pytest `1619 passed, 3 skipped`, full unittest `1622 tests OK, skipped=3`, plus passing Ruff, Pyright,
  compileall, Demo validation, `pip check`, history safety, fsck, and diff checks.
- Local `main`, live `origin/main`, and `origin/workstream/v2-3-capability-modules` are all
  `36ff77fb5daa3407a79b0b2359a03a49a63003a0`. V2-4A has never been pushed, merged, or released.

### Do Not Execute Automatically

- Do not push, merge, move `main`, release, distribute the sealed candidate, or access private material.
- Do not automatically enter V2-5, Workbench, dynamic plugins, multiplayer runtime, or runtime model adjudication.
- The main checkout's untracked `uv.lock` is user-owned and must not enter the candidate or handoff-seal commit.
