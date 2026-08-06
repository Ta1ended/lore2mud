# 下一任务 / Next Task

更新日期：2026-08-05

## 中文

### 唯一下一门禁

**人类明确授权开始 V2-3。**

### 当前依据

- 产品候选 tree 为 `f7c12fda17257f7a6b539bbbfce97da18452a961`，父提交正是绿色
  V2-1 文档头 `eb972903a0b959f09a647a1727a6ed66f2d098f7`。
- 全新 Reviewer 13 对该精确候选给出 P0-P3 全空与 TECH `GO`。
- 产品所有者已明确对同一产品 SHA 给出 PRODUCT PASS，并授权把当前
  `workstream/v2-2-agent-authoring` 正常推送到同名远端分支。
- 推送前实时 `git ls-remote` 显示远端 `main=bf3f8b93`、V2-1 workstream=`eb972903`，
  且远端尚无 V2-2 workstream；因此授权操作只创建新分支，不覆盖或 force-push ref。
- 首次推送在精确文档头 `8eb549e` 创建了远端 workstream，但 Ubuntu Actions 在产品 CLI
  启动前暴露 POSIX surrogate argv 测试夹具问题。verification-only 提交 `2dc9475e` 只改
  一个测试文件，产品路径相对 `ec60cb0` 零差异；全新 Reviewer 14 给出 P0-P3 全空与 `GO`。
- 最终远端文档头 `2ae85937` 的 GitHub Actions tests `31046078308` 与 quality
  `31046078333` 均绑定精确 SHA 并为 `completed/success`；远端 `main` 保持 `bf3f8b93`。
- 安全门禁权限方已对精确产品 SHA 明确给出 `SECURITY PASS`。TECH、PRODUCT 与 SECURITY
  决定均绑定产品 SHA，不绑定 documentation seal、preview/report fingerprint 或未来
  package/evidence identity。
- 产品所有者已明确授权把当前 SECURITY PASS 与 README documentation-only seal 正常
  fast-forward 推送到同名远端 workstream。Controller 必须在推送后确认精确 head 的
  GitHub Actions tests 与 quality 均为绿色，然后停止。

### V2-3 授权边界

- V2-3 只能在新的明确人类授权后开始；TECH、PRODUCT、SECURITY 和本次文档推送均不自动
  授予该权限。
- V2-3 授权不自动允许移动/合并 `main`、release 或分发 preview/report；这些仍需分别授权。
- 不访问私人小说、canon、派生内容、图片、存档或私人报告；只使用公开安全或合成材料。
- 不把未封存 preview、SimulationReport 或 fingerprint 作为可分发 package、release
  evidence 或安全证明。
- 保留主工作区未跟踪 `uv.lock` 的 14,471 字节和 SHA-256
  `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`。

### 停止规则

documentation-only seal 推送并确认 Actions 绿色后立即停止：不移动或合并 `main`，不
release，不开始 V2-3，不发布 preview/report。等待新的明确 V2-3 授权。

## English

### Single Next Gate

**Explicit human authorization to begin V2-3.**

### Current Basis

- The product candidate tree is `f7c12fda17257f7a6b539bbbfce97da18452a961`, with
  exact parent `eb972903a0b959f09a647a1727a6ed66f2d098f7`, the green V2-1 documentation
  head.
- Fresh Reviewer 13 returned P0-P3 empty and TECH `GO` for that exact candidate.
- The product owner explicitly granted PRODUCT PASS for the same product SHA and
  authorized a normal push of the current `workstream/v2-2-agent-authoring` branch to
  the matching remote branch.
- The pre-push live `git ls-remote` showed remote `main=bf3f8b93`, V2-1
  workstream=`eb972903`, and no remote V2-2 workstream. The authorized operation therefore
  creates a branch without overwriting or force-pushing a ref.
- The first push created the remote workstream at exact documentation head `8eb549e`,
  but Ubuntu Actions exposed a POSIX surrogate-argv test-harness issue before the product
  CLI started. Verification-only commit `2dc9475e` changes one test file, leaves every
  product path identical to `ec60cb0`, and received P0-P3 empty with `GO` from fresh
  Reviewer 14.
- Final remote documentation head `2ae85937` has GitHub Actions tests `31046078308` and
  quality `31046078333` both bound to the exact SHA with `completed/success`; remote
  `main` remained `bf3f8b93`.
- The security gate authority explicitly returned `SECURITY PASS` for the exact product
  SHA. TECH, PRODUCT, and SECURITY decisions bind to the product SHA, not the
  documentation seal, preview/report fingerprints, or a future package/evidence identity.
- The product owner explicitly authorized a normal fast-forward publication of the
  current SECURITY PASS and README documentation-only seal to the matching remote
  workstream. The controller must verify exact-head GitHub Actions tests and quality as
  green after the push, then stop.

### V2-3 Authorization Boundary

- V2-3 may begin only after new explicit human authorization. TECH, PRODUCT, SECURITY,
  and this documentation push do not grant that authority automatically.
- V2-3 authorization would not automatically permit moving/merging `main`, release, or
  preview/report distribution; those remain separately controlled.
- Do not access private novels, canon, derived content, images, saves, or private
  reports. Review remains public-safe or synthetic.
- Do not present the unsealed preview, SimulationReport, or fingerprints as a
  distributable package, release evidence, or security proof.
- Preserve the primary checkout's untracked `uv.lock` at 14,471 bytes and SHA-256
  `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`.

### Stop Rule

Stop after publishing the documentation-only seal and verifying green Actions: do not
move or merge `main`, release, begin V2-3, or publish previews/reports. Wait for new
explicit V2-3 authorization.
