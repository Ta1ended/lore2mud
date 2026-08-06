# 项目状态 / Project State

更新日期：2026-08-06

## 中文

### 目标

在保持 V1/V2-1/V2-2 兼容与确定性的前提下，完成 Lore2MUD V2-3 Capability Module Architecture：使用引擎内置静态 catalog 确定性解析 capability requirements，并通过同一 `GameSession` 事务边界运行 namespaced state、typed intents/events/player-safe views 和隔离 checkpoint。

### 当前状态

- V2-2 精确产品候选是 `ec60cb0169678ba8d7ef1256a2f2d7cad27d1b60`，已获得独立 TECH `GO`、人类 PRODUCT PASS 和 SECURITY PASS。
- V2-2 远端文档头是 `bfec33a538d184c36822efeb11eff3dd6d8e7fc5`。
- V2-2 integration candidate 是 `c37969f6b6958e66474738f88a53b9d5c2f50d99`：`HEAD^1=ba729be`、`HEAD^2=bfec33a`，tree 与 V2-2 tree 均为 `d7ea31bd3cda9c84cdf5e1e47b2ddedb46771753`，相对第二父提交零字节差异。
- GitHub PR #1 是 `main <- integration/v2-2-to-main` 的 open Draft PR，实时检查显示 clean/mergeable，exact-head tests 与 quality 成功；尚未获得单独 merge 授权。
- 产品负责人已于 2026-08-06 明确授权开始 V2-3 开发。本 planning workstream 从精确 `c37969f` 创建，只整理授权、范围和新会话 Goal；V2-3 产品代码尚未开始。
- 当前本地主 checkout 仍是 `main@564530d`，实时远端 `main=ba729be`。主 checkout 未跟踪 `uv.lock` 保持 14,471 字节和既定 SHA-256。

### 已完成

- V2-1 transport-neutral `GameSession` application boundary 已验收并发布到 workstream。
- V2-2 `GameBlueprint v1`、`GameProject v1`、diagnostics、fixed-profile preview、isolated simulation/report、proofing、Python SDK 与 structured CLI 已完成并通过三类门禁。
- V2-2 integration merge candidate 已通过完整本地矩阵、GitHub Actions 与只读 integration audit，且不改变 V2-2 tree。
- `docs/v2/v2_3_goal.md` 已定义 V2-3 baseline、合同、模块归属、reference capability、协作、验证、验收和停止规则。

### 进行中

- `planning/v2-3-capability-system` 正在形成一个只含规划与交接文档的 stacked Draft PR，供产品负责人审核后交给新的 Codex 会话。

### 阻塞项

- V2-3 产品实现无技术阻塞，但新会话必须先实时复核 PR #1 与 `main`。如果 PR #1 尚未合并，可从 exact green `c37969f` 开始 stacked workstream；不得自行移动 `main`。

### 验证

- 2026-08-06 live remote：`main=ba729be8d80dbcbefe90a1dc801003deec7c4c95`，integration head=`c37969f6b6958e66474738f88a53b9d5c2f50d99`。
- integration identity：第一父/第二父/tree 精确匹配，`git diff HEAD^2 HEAD` 为空。
- PR #1 exact head GitHub Actions：tests 和 quality 成功。
- V2-2 integration matrix：unittest 1483 OK（11 skip）；serial/xdist pytest 1472 passed、11 skipped、619 subtests；Ruff、Pyright、compileall、Demo validate、pip check、safety、fsck、diff checks 通过。
- 本 planning PR 只运行文档、UTF-8、链接、隐私、Git 和 repository safety 门禁，不声称重新执行产品测试。

### 关键路径

- `docs/v2/v2_3_goal.md`：新 Codex 会话的自包含执行 Goal。
- `docs/v2/architecture.md`、`docs/v2/roadmap.md`：V2-3 产品与里程碑边界。
- `src/lore2mud/application/`：现有 V2-1 runtime transaction 与 player-safe projection。
- `src/lore2mud/authoring/`：现有 V2-2 project/preview/simulation/SDK/CLI 服务。
- `src/lore2mud/capabilities/`：V2-3 计划新增的 capability 合同、catalog、resolver、runtime 与 checkpoint 归属。

### 风险与唯一下一门禁

- PR #1 仍是 Draft；规划 PR 必须保持 stacked dependency 清晰，不能被误解为已合并 `main`。
- SemVer、全局依赖解析、namespace ownership、runtime rollback 与 checkpoint 是 V2-3 高风险域，必须使用高可靠推理和独立验收。
- 低成本模型仅承担接口冻结后的重复、机械和证据整理工作；模型输出不是通过证据。
- 唯一下一门禁：产品负责人审核 V2-3 planning PR 和 `docs/v2/v2_3_goal.md`。审核通过后，把 Goal 交给新的 Codex 会话执行；当前会话不实现 V2-3 产品代码。

## English

### Objective

Complete the Lore2MUD V2-3 Capability Module Architecture without regressing V1, V2-1, or V2-2: deterministically resolve capability requirements from an engine-shipped static catalog, then run namespaced state, typed intents/events/player-safe views, and isolated checkpoints inside the same `GameSession` transaction boundary.

### Current Status

- Exact V2-2 product candidate `ec60cb0169678ba8d7ef1256a2f2d7cad27d1b60` has independent TECH `GO`, human PRODUCT PASS, and SECURITY PASS.
- The remote V2-2 documentation head is `bfec33a538d184c36822efeb11eff3dd6d8e7fc5`.
- Integration candidate `c37969f6b6958e66474738f88a53b9d5c2f50d99` has `HEAD^1=ba729be`, `HEAD^2=bfec33a`, and tree `d7ea31bd3cda9c84cdf5e1e47b2ddedb46771753`, identical to the V2-2 tree with zero byte difference from its second parent.
- GitHub PR #1 is an open Draft for `main <- integration/v2-2-to-main`; live checks show it clean and mergeable with successful exact-head tests and quality. Separate merge authorization has not been given.
- On 2026-08-06 the product owner explicitly authorized V2-3 development. This planning workstream starts from exact `c37969f` and contains only authorization, scope, and a new-session Goal; no V2-3 product code has started.
- The primary local checkout remains `main@564530d`, while live remote `main=ba729be`. Its untracked `uv.lock` retains the authorized 14,471-byte size and SHA-256.

### Completed

- The V2-1 transport-neutral `GameSession` application boundary is accepted and published to its workstream.
- V2-2 blueprint/project contracts, diagnostics, fixed-profile preview, isolated simulation/report, proofing, Python SDK, and structured CLI are complete across TECH, PRODUCT, and SECURITY gates.
- The V2-2 integration merge candidate passed the full local matrix, GitHub Actions, and a read-only integration audit without changing the V2-2 tree.
- `docs/v2/v2_3_goal.md` defines the V2-3 baseline, contracts, ownership, reference capability, collaboration, validation, acceptance, and stop rules.

### In Progress

- `planning/v2-3-capability-system` is preparing a documentation-only stacked Draft PR for product-owner review and transfer to a fresh Codex session.

### Blockers

- There is no technical implementation blocker, but the fresh session must recheck PR #1 and live `main`. If PR #1 remains unmerged, it may start a stacked workstream from exact green `c37969f`; it must not move `main` itself.

### Verification

- 2026-08-06 live remote: `main=ba729be8d80dbcbefe90a1dc801003deec7c4c95`; integration head=`c37969f6b6958e66474738f88a53b9d5c2f50d99`.
- Integration identity: exact first parent, second parent, and tree; `git diff HEAD^2 HEAD` is empty.
- PR #1 exact-head GitHub Actions tests and quality succeeded.
- V2-2 integration matrix: unittest 1483 OK with 11 skips; serial/xdist pytest 1472 passed, 11 skipped, 619 subtests; Ruff, Pyright, compileall, Demo validation, pip check, safety, fsck, and diff checks passed.
- This planning PR runs documentation, UTF-8, link, privacy, Git, and repository-safety checks only. It does not claim a fresh product test run.

### Key Paths

- `docs/v2/v2_3_goal.md`: self-contained execution Goal for the fresh Codex session.
- `docs/v2/architecture.md`, `docs/v2/roadmap.md`: V2-3 product and milestone boundaries.
- `src/lore2mud/application/`: existing V2-1 runtime transaction and player-safe projection.
- `src/lore2mud/authoring/`: existing V2-2 project/preview/simulation/SDK/CLI services.
- `src/lore2mud/capabilities/`: planned V2-3 ownership for contracts, catalog, resolver, runtime, and checkpoints.

### Risks And Single Next Gate

- PR #1 remains Draft. The planning PR must retain a clear stacked dependency and cannot imply that `main` already contains V2-2.
- SemVer, global dependency resolution, namespace ownership, runtime rollback, and checkpoints are high-risk V2-3 domains requiring reliable reasoning and independent acceptance.
- Lower-cost models are limited to repetitive, mechanical, and evidence-collection work after interfaces freeze; model output is not pass evidence.
- The single next gate is product-owner review of the V2-3 planning PR and `docs/v2/v2_3_goal.md`. After approval, transfer the Goal to a fresh Codex session. This session does not implement V2-3 product code.
