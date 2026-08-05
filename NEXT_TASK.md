# 下一任务 / Next Task

更新日期：2026-08-05

## 中文

### 唯一下一门禁

**对精确 V2-2 产品候选 `ec60cb0169678ba8d7ef1256a2f2d7cad27d1b60`
进行独立 SECURITY PASS。**

### 当前依据

- 产品候选 tree 为 `f7c12fda17257f7a6b539bbbfce97da18452a961`，父提交正是绿色
  V2-1 文档头 `eb972903a0b959f09a647a1727a6ed66f2d098f7`。
- 全新 Reviewer 13 对该精确候选给出 P0-P3 全空与 TECH `GO`。
- 产品所有者已明确对同一产品 SHA 给出 PRODUCT PASS，并授权把当前
  `workstream/v2-2-agent-authoring` 正常推送到同名远端分支。
- 推送前实时 `git ls-remote` 显示远端 `main=bf3f8b93`、V2-1 workstream=`eb972903`，
  且远端尚无 V2-2 workstream；因此授权操作只创建新分支，不覆盖或 force-push ref。
- TECH 与 PRODUCT 决定均绑定产品 SHA，不绑定 documentation seal、preview/report
  fingerprint 或未来 package/evidence identity。

### SECURITY PASS 边界

- SECURITY 验收须另行明确启动，并对精确产品候选执行；本次 workstream 推送不会自动
  授予 SECURITY PASS。
- 不访问私人小说、canon、派生内容、图片、存档或私人报告；只使用公开安全或合成材料。
- 不把未封存 preview、SimulationReport 或 fingerprint 作为可分发 package、release
  evidence 或安全证明。
- 保留主工作区未跟踪 `uv.lock` 的 14,471 字节和 SHA-256
  `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`。

### 停止规则

远端 workstream 推送完成后立即停止：不移动或合并 `main`，不 release，不开始 V2-3，
不发布 preview/report。若后续 SECURITY finding 要求改变产品字节，必须形成新候选并重新走
相应 TECH 与 PRODUCT 门禁；旧决定不转移。

## English

### Single Next Gate

**Independent SECURITY PASS for exact V2-2 product candidate
`ec60cb0169678ba8d7ef1256a2f2d7cad27d1b60`.**

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
- TECH and PRODUCT decisions bind to the product SHA, not the documentation seal,
  preview/report fingerprints, or a future package/evidence identity.

### SECURITY PASS Boundary

- SECURITY acceptance requires separate explicit initiation against the exact product
  candidate. Publishing the workstream does not grant SECURITY PASS automatically.
- Do not access private novels, canon, derived content, images, saves, or private
  reports. Review remains public-safe or synthetic.
- Do not present the unsealed preview, SimulationReport, or fingerprints as a
  distributable package, release evidence, or security proof.
- Preserve the primary checkout's untracked `uv.lock` at 14,471 bytes and SHA-256
  `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`.

### Stop Rule

Stop after the remote workstream push completes: do not move or merge `main`, release,
begin V2-3, or publish previews/reports. If a later SECURITY finding changes product
bytes, create a new candidate and repeat the applicable TECH and PRODUCT gates; the old
decisions do not transfer.
