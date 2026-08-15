# 下一任务 / Next Task

更新日期：2026-08-15

## 中文

### 唯一下一任务

**请求一名未参与编写的只读 TECH reviewer，审查本地 V2-4B 候选的精确 commit；要求 findings-first，按 P0–P3 输出，最终只能是 `GO` 或 `REVISE`。**

### 当前依据

- 候选 worktree：`D:\MUD game kaifa\.codex-worktrees\v2-4b-player-experience-20260815`；基线为
  `7470c5b5344df9d184828d20e37032c5bc5f57bd`，候选 commit 已固定；精确 SHA 记录在私有验证矩阵与 handoff。
- 全量 pytest 为 `1627 passed, 2 skipped, 1078 subtests passed`；显式绑定候选 `src` 的全量 unittest 为
  `1629 tests OK, skipped=2`；Ruff、Pyright、compileall、`pip check` 和 `git diff --check` 已通过。
- 上述全量数字来自 `D:\MUD game kaifa\lore2mud\.venv\Scripts\python.exe`（Python 3.13.14、
  PyInstaller 6.21.0），并以覆盖式 `PYTHONPATH=<candidate>\src` 绑定候选源码。
- 授权的外部私有内容候选、存档、截图、日志和报告均位于仓库外；其技术封存不可分发，且不等于 PRODUCT PASS、
  SECURITY PASS 或发布授权。私有矩阵与证据不进入公共 Git。

### 审查边界

- reviewer 只读访问本候选 worktree、选定引擎 checkout 和允许的私有内容目录；不得编辑、移动 ref、push、merge、
  查询远端、重封包或启动 V2-5。
- 验收必须绑定最终候选 commit，优先检查 Schema/loader/runtime/CLI/Web 等价、完成态持久化、玩家安全投影、
  V1 兼容、测试证据与 Git 私有边界；发现问题按 P0–P3 列出，末尾只给 `GO` 或 `REVISE`。

### 后续队列

- TECH `GO` 后停止，等待产品负责人对扩写版重新真人试玩并给出新的 `PRODUCT PASS`。
- `SECURITY PASS`、push、`main` 快进、release、分发和 V2-5 均是独立后续门禁。

## English

### Single Next Task

**Request a fresh read-only TECH reviewer who did not write the change to inspect the exact local V2-4B candidate commit; require findings-first P0–P3 findings and exactly one final `GO` or `REVISE`.**

### Current Basis

- Candidate worktree: `D:\MUD game kaifa\.codex-worktrees\v2-4b-player-experience-20260815`; baseline
  `7470c5b5344df9d184828d20e37032c5bc5f57bd`; the candidate commit is fixed, with its exact SHA recorded in the private verification matrix and handoff.
- Full pytest is `1627 passed, 2 skipped, 1078 subtests passed`; full unittest with the candidate `src`
  explicitly selected is `1629 tests OK, skipped=2`; Ruff, Pyright, compileall, `pip check`, and `git diff --check` pass.
- Those full-suite numbers use `D:\MUD game kaifa\lore2mud\.venv\Scripts\python.exe` (Python 3.13.14,
  PyInstaller 6.21.0) with `PYTHONPATH=<candidate>\src` replacing the package import path.
- The authorized external private content candidate, saves, screenshots, logs, and reports remain outside the
  repository. Its technical seal is non-distributable and is not a PRODUCT PASS, SECURITY PASS, or release
  authorization. Private matrices and evidence stay out of public Git.

### Review Boundary

- The reviewer is read-only and may access only this candidate worktree, the selected engine checkout, and the
  explicitly permitted private content directory; no edits, ref movement, push, merge, remote query, resealing, or V2-5.
- Acceptance must bind to the final candidate commit and focus on Schema/loader/runtime/CLI/Web equivalence,
  completion persistence, player-safe projection, V1 compatibility, test evidence, and the Git/private boundary.
  Findings are P0–P3 first, ending with only `GO` or `REVISE`.

### Queue After The Gate

- After TECH `GO`, stop and wait for the product owner to replay the expanded build and issue a fresh `PRODUCT PASS`.
- `SECURITY PASS`, push, fast-forward `main`, release, distribution, and V2-5 remain separate later gates.
