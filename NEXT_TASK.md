# 下一任务 / Next Task

更新日期：2026-08-09

## 中文

### 唯一下一任务

**在新的独立公开 workstream 中实现 V2-4B / PLAT-1 通用玩家呈现修复：玩家日志不得直接暴露稳定 ID，
满足终局条件时 CLI/Web 必须给出明确的通关与结局提示。**

### 当前依据

- V2-4A 冻结产品候选为 `badc9a20816a9515b24c98199ca37323a02c1b00`，documentation seal 为
  `c7e3280083ebc77a2b453f9bc057df302b00202a`。产品所有者已于 2026-08-09 授权正常 push 与
  `main` 纯快进；发布完成时两个 live 远端 ref 均精确指向 `c7e3280`。
- V2-4A 的 TECH `GO`、PRODUCT `PRODUCT PASS` 与 SECURITY `GO` 继续绑定冻结产品字节；本后续
  documentation record 不改变源码、Schema 或测试。
- 私有 PLAT-1 试玩反馈暴露了两个通用表现缺口：事件/状态稳定 ID 可进入玩家日志，以及终局条件成立后
  缺少独立、醒目的通关/结局投影。私有故事内容、存档、日志和证据仍留在公共 Git 之外。

### 范围与门禁

- 只使用公开安全的合成 fixture 与现有 V2 application/Web 边界；不得把私有故事文本或专有 ID 写入仓库。
- 保持 `World` 权威、CLI/Web 等价、玩家安全投影、确定性与 V1 兼容；不得借机启动 V2-5、Workbench、
  动态插件、多人运行或运行时模型裁决。
- 新 workstream 必须有聚焦与全量验证、真实 CLI/Web 流程及新的独立 TECH 验收；push、`main` 更新、
  release 与分发仍是后续独立门禁。
- 主工作树未跟踪的 `uv.lock` 是用户保留文件，不得纳入新 workstream 或提交。

## English

### Single Next Task

**Implement a generic V2-4B / PLAT-1 player-presentation repair in a new isolated public workstream: player logs
must not expose stable IDs directly, and CLI/Web must show an explicit completion and ending result when terminal
conditions are satisfied.**

### Current Basis

- The frozen V2-4A product candidate is `badc9a20816a9515b24c98199ca37323a02c1b00`, with documentation seal
  `c7e3280083ebc77a2b453f9bc057df302b00202a`. On August 9, 2026, the product owner authorized a normal push and
  fast-forward `main` integration; both live remote refs pointed exactly to `c7e3280` when publication completed.
- V2-4A TECH `GO`, PRODUCT `PRODUCT PASS`, and SECURITY `GO` remain bound to the frozen product bytes; this follow-up
  documentation record changes no source, Schema, or test bytes.
- Private PLAT-1 playtest feedback exposed two generic presentation gaps: event/state stable IDs can reach player logs,
  and completed terminal conditions lack a separate, prominent completion/ending projection. Private story content,
  saves, logs, and evidence remain outside public Git.

### Scope And Gates

- Use only public-safe synthetic fixtures and the existing V2 application/Web boundaries; do not add private story
  text or proprietary IDs to the repository.
- Preserve authoritative `World`, CLI/Web equivalence, player-safe projection, determinism, and V1 compatibility. Do
  not start V2-5, Workbench, dynamic plugins, multiplayer runtime, or runtime model adjudication.
- The new workstream requires focused and full verification, real CLI/Web flows, and fresh independent TECH
  acceptance. Push, `main` updates, release, and distribution remain separate later gates.
- The main checkout's untracked `uv.lock` is user-owned and must not enter the new workstream or any commit.
