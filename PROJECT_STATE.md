# 项目状态 / Project State

_最后更新 / Last updated: 2026-08-03_

## 中文

### 目标

交付一个可由 Agent 调用的小说转文字游戏引擎：创作平面生成经过验证、可追溯的包，
确定性运行时平面负责执行，同时保持 V1 兼容性以及严格的公开/私有和权利边界。

### 当前状态

- V2-0 已接受并发布的基线是
  `077b8eb568f193b0b3ccab47410bec35dc4c2a9c`。开始任何新任务前都必须核对实时 Git，
  并确认在线 `main` 等于该基线，或是只包含后来已独立验收并发布的提交。
- V2 合同名称仍只是已接受的方向，尚未实现为已发布 API。

### 已完成
- V2-0 已完成：修复目标 `d13dd0590f47f6477b476cfbdab2715b8f4aba7a`
  获得独立 TECH GO，产品所有者明确给出 PRODUCT PASS；最终封印目标
  `077b8eb568f193b0b3ccab47410bec35dc4c2a9c` 又获得全新独立 GO，P0-P3 均无发现。

### 进行中
- 当前没有任何 V2 实现在进行；V2-1 已路由但尚未开始。

### 阻塞项
- V2-1 范围当前没有已知产品或架构阻塞；新任务仍须核对实时引用与已接受基线。

### 验证
- 最终封印分支的 quality `30829532319` 和 tests `30829532606` 成功；在线
  `main` 的 quality `30829717919` 和 tests `30829718590` 也于 2026-08-03 成功。

### 保持的边界

- 保持现有公开内容、权威 `World` 行为、save v9 写入以及受支持的 v7/v8 读取兼容性。
- 私有源文本、设定、改编内容、图像和报告不得进入公开 Git；没有新的私有访问授权。
- 所有实现、架构和验收任务或子 Agent 必须明确使用 `gpt-5.6-sol`，reasoning 为
  `xhigh` 或更高；不可静默降级，也不可自我批准。
- 主检出目录中有意未跟踪的 `uv.lock` 边界保持不变：14,471 字节，SHA-256
  `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`。
  主检出目录可保留这份未跟踪副本，但绝不能提交；隔离工作树不得创建或复制它。

### 关键路径

- `README.md`：中英双语的公开项目入口、产品边界与快速开始。
- `AGENTS.md`：任务、模型、门禁、架构与安全规则。
- `PRODUCT.md`、`CODE_MAP.md`：产品方向与当前 V1 数据流。
- `docs/v2/architecture.md`、`docs/v2/roadmap.md`：目标合同与已批准顺序。
- `NEXT_TASK.md`：唯一已路由的下一任务。

### 风险与未知项

- `World`、加载、存档、命令、Web 和战役模块仍然较大且耦合，边界必须渐进引入。
- `CampaignSpec v1` 仍是创作 IR，没有运行时物化器，也不是运行时输入。
- MCP、动态插件、生成代码及不受限的主机/网络访问均未获授权；SDK 和结构化 CLI
  仍应先于任何 MCP 适配器。

## English

### Objective

Deliver an Agent-callable novel-to-text-game engine whose Authoring Plane produces
validated, traceable packages for a deterministic Runtime Plane, while preserving V1
compatibility and strict public/private and rights boundaries.

### Current Status

- The accepted and published V2-0 baseline is
  `077b8eb568f193b0b3ccab47410bec35dc4c2a9c`. Before any new task, verify live Git
  and confirm live `main` is that baseline or contains only later independently
  accepted and published commits.
- V2 contract names remain accepted direction and are not implemented shipped APIs.

### Completed
- V2-0 is complete: repair target `d13dd0590f47f6477b476cfbdab2715b8f4aba7a`
  received independent TECH GO and the product owner's explicit PRODUCT PASS; final
  seal target `077b8eb568f193b0b3ccab47410bec35dc4c2a9c` then received a fresh
  independent GO with no P0-P3 findings.

### In Progress
- No V2 implementation is in progress; V2-1 is routed but not started.

### Blockers
- No product or architecture blocker is known for V2-1; a fresh task must still check
  live refs and the accepted baseline.

### Verification
- Final-seal branch quality run `30829532319` and tests run `30829532606` succeeded;
  live-`main` quality run `30829717919` and tests run `30829718590` also succeeded on
  2026-08-03.

### Preserved Boundaries

- Preserve existing public content, authoritative `World` behavior, save v9 writes,
  and supported v7/v8 read compatibility.
- Private source text, canon, adaptations, images, and reports stay out of public Git;
  no new private access is authorized.
- Every implementation, architecture, and acceptance task or subagent must explicitly
  use `gpt-5.6-sol` with reasoning `xhigh` or higher; never silently downgrade or
  self-approve.
- The intentionally untracked primary-checkout `uv.lock` boundary remains unchanged:
  14,471 bytes, SHA-256
  `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`.
  The primary checkout may retain that untracked copy, but it must never be committed;
  isolated worktrees must not create or copy it.

### Key Paths

- `README.md`: bilingual public project entry, product boundary, and quick start.
- `AGENTS.md`: task, model, gate, architecture, and safety rules.
- `PRODUCT.md`, `CODE_MAP.md`: product direction and current V1 data flows.
- `docs/v2/architecture.md`, `docs/v2/roadmap.md`: target contracts and approved order.
- `NEXT_TASK.md`: the single routed next task.

### Risks And Unknowns

- `World`, loader, save, command, Web, and campaign modules remain large and coupled;
  boundaries must be introduced incrementally.
- `CampaignSpec v1` remains authoring IR with no runtime materializer and is not a
  runtime input.
- MCP, dynamic plugins, generated code, and unrestricted host/network access are not
  authorized; SDK and structured CLI still precede any MCP adapter.
