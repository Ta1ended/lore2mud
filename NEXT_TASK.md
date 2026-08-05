# 下一任务 / Next Task

更新日期：2026-08-05

## 中文

### 唯一下一门禁

**把干净、连贯、精确的 V2-2 产品候选交给一个未参与实现的全新任务，严格只读执行
Independent TECH Acceptance。**

Controller 必须先完成全部本地门禁并把所有产品改动收敛为一个提交。候选从精确绿色
V2-1 文档头 `eb972903a0b959f09a647a1727a6ed66f2d098f7` 开始；不得把本地
`origin/main` 当作实时 GitHub 证据，也不得移动 `main`。第八轮验收因平台中断没有
verdict。第九轮修复了 `1ea39ac` 的 typed-input/cyclic-document findings；第十轮在
精确候选 `e7054d7` 上确认诊断等价性后发现资源拒绝晚于 preview 构造/加载的 P2，并给
出 `REVISE`。第十一轮在精确候选 `cb974cb` 上关闭 DEC-0106 P2，但发现 typed
blueprint/project/report 未共享 CLI bounded canonical round-trip 的 P2，以及 CHANGELOG
遗漏 DEC-0106 的 P3，并给出 `REVISE`。Reviewer 12 在精确候选 `e1f3a806` 上关闭
DEC-0107 findings，但发现 typed project/report 中的 `bytes` 等非 JSON 标量会从 SDK
泄漏原始 `TypeError` 的 P2，并给出 `REVISE`。DEC-0108 amend 后的新 SHA 必须由全新
Reviewer 13 决定，旧 verdict 不得转移。

### 验收合同

- 在验收提示中写明精确候选 SHA、基线 `eb972903` 和允许范围；任务必须
  `fork_turns="none"`，未参与任何实现，并保持严格只读。
- 先按 P0、P1、P2、P3 列 findings；没有问题时各严重度明确为空；最后只能输出一个
  `GO` 或 `REVISE`。
- 检查合同/Schema/loader/runtime/save/CLI/SDK/Windows packaging 同步、规范字节与 hashes、
  capability 拒绝、隔离模拟、witness replay、checkpoint 等价、玩家安全 descriptors、
  proofing 隐私、SDK/CLI 等价和 V1 回归。
- 直接构造损坏 canonical content、错误 nested blueprint/request/report 及 4,097 capability
  IDs；所有 SDK 操作必须返回可序列化、有界、稳定的 `AuthoringResult` 拒绝，project
  validation 必须发生在 capability diagnostics 和任何 runtime materialization 之前。
- 直接构造自引用 dict 与 list，并调用 blueprint/project document SDK 入口；两者都必须
  在有界时间内返回单一、稳定、Schema-valid 的 rejection，且共享非循环值不得误判为环。
- 直接构造 typed request：1,000,001 字符、超过 8 MiB 的规范 JSON、depth/node 上限加一、
  65 位整数；每项 SDK rejection 必须是单一 Schema-valid `authoring_input_*` 诊断，且
  超过 8 MiB 的案例必须与 structured CLI 的 bytes/diagnostic/exit 等价。
- 直接构造 65 位 seed/clock 的 typed blueprint、包含该 blueprint 的 typed project，及
  65 位 seed 的 typed report；验证 create-project、validate、preview、simulate、replay、
  proof 与真实 structured CLI 的 canonical bytes、diagnostic、artifact ID 和 exit 等价。
  同时检查 Blueprint Schema/loader 接受 signed-64 边界并拒绝边界外整数。
- 直接在 typed project workspace metadata 与 typed report `player_name` 中注入 `bytes`
  等非 JSON 标量；validate、preview、simulate、replay、proof 必须全部返回单一、规范可
  序列化的 `authoring_input_invalid_json`，不得泄漏 Python 异常或开始 preview/session 工作。
- 用 spy 证明上述五种资源拒绝在 SDK `simulate()` 与 direct `simulate_preview()` 中均不
  调用 `build_preview`、preview load/materializer 或 `GameSession`，且 capability-blocked
  project 不得遮蔽 resource diagnostic；request resource preflight 还必须先于 typed project
  normalization，project resource rejection 必须先于 preview 构造。
- 不得编辑文件、移动 ref、push、merge、release、访问私人材料、查询新范围或自行授予
  PRODUCT/SECURITY/publication 通过。

### Verdict 后流程

- `REVISE`：只修 findings，生成新的单一产品候选，并交给另一个全新未参与实现的只读
  验收任务。旧 verdict 不得转移到新产品字节。
- `GO`：立即冻结产品字节；只创建 documentation-only seal，记录精确产品 SHA、空/非空
  P0-P3 与 TECH verdict。产品字节未变化时不得因文档封存重复全量 TECH 验收。
- TECH `GO` 后唯一下一门禁是产品所有者对精确 V2-2 产品候选给出人类
  `PRODUCT PASS`。TECH `GO` 不等于 PRODUCT PASS、SECURITY PASS、publication 或 release。

### 当前停止边界

- 不 push，不移动或合并 `main`，不创建 release，不开始 V2-3，不发布 preview/report，
  不把 fingerprint 表述为 package/evidence identity。
- 不访问私人小说、canon、派生内容、图片、存档或私人报告；验收材料只用公开安全或合成
  fixtures。
- 保留主工作区未跟踪 `uv.lock` 的 14,471 字节和 SHA-256
  `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`。

## English

### Single Next Gate

**Submit the clean, coherent, exact V2-2 product candidate to a fresh task that did
not participate in implementation for strict read-only Independent TECH Acceptance.**

The Controller must first complete every local gate and collapse all product changes
into one commit. The candidate starts from exact green V2-1 documentation head
`eb972903a0b959f09a647a1727a6ed66f2d098f7`. Local `origin/main` is not live GitHub
evidence, and `main` must not move. The eighth review was interrupted and produced no
verdict. The ninth review repaired the typed-input/cyclic-document findings; Reviewer 10
on exact candidate `e7054d7` confirmed diagnostic equivalence but found a P2 because
resource rejection happened after preview construction/loading. Reviewer 11 on exact
candidate `cb974cb` closed DEC-0106 but found a P2 because typed blueprint/project/report
values did not share the CLI bounded canonical round trip, plus a CHANGELOG P3.
Reviewer 12 on exact candidate `e1f3a806` closed the DEC-0107 findings but found a P2
because non-JSON scalars such as `bytes` in a typed project/report escaped raw
`TypeError` from SDK operations. It issued `REVISE`. Fresh Reviewer 13 must decide the
amended DEC-0108 SHA; no old verdict transfers.

### Acceptance Contract

- State the exact candidate SHA, `eb972903` baseline, and allowed scope in the review
  prompt. The task must use `fork_turns="none"`, have no implementation participation,
  and remain strictly read-only.
- List findings first under P0, P1, P2, and P3, explicitly empty when applicable, then
  end with exactly one `GO` or `REVISE`.
- Check contract/Schema/loader/runtime/save/CLI/SDK/Windows packaging alignment,
  canonical bytes and hashes, capability rejection, isolated simulation, witness
  replay, checkpoint equivalence, player-safe descriptors, proofing privacy, SDK/CLI
  equivalence, and V1 regressions.
- Directly construct malformed canonical content, nested blueprint/request/report
  values, and 4,097 capability IDs. Every SDK operation must return a serializable,
  bounded, stable `AuthoringResult` rejection, with project validation before capability
  diagnostics or any runtime materialization.
- Directly construct self-referential dict and list values for both blueprint/project
  document SDK entry points. Each must return one stable Schema-valid rejection in
  bounded time, while shared acyclic values must not be mistaken for cycles.
- Directly construct typed requests with a 1,000,001-character string, an encoded
  document over 8 MiB, depth and node limits plus one, and a 65-digit integer. Each SDK
  rejection must be a single Schema-valid `authoring_input_*` diagnostic, and the
  over-8-MiB case must be byte/diagnostic/exit equivalent to the structured CLI.
- Directly construct a typed blueprint with a 65-digit seed/clock, a typed project that
  embeds it, and a typed report with a 65-digit seed. Verify create-project, validate,
  preview, simulate, replay, and proof against the real structured CLI for canonical
  bytes, diagnostics, artifact IDs, and exit semantics. Also verify Blueprint Schema and
  loader accept signed-64 boundaries and reject values outside them.
- Inject non-JSON scalars such as `bytes` into typed-project workspace metadata and the
  typed-report `player_name`. Validate, preview, simulate, replay, and proof must all
  return one canonically serializable `authoring_input_invalid_json` result without a
  Python exception or any preview/session work.
- Use spies to prove those five resource rejections call neither preview construction,
  loading/materialization, nor `GameSession`, and that a capability-blocked project
  cannot mask the resource diagnostic. Request resource preflight must also precede
  typed project normalization, while a project resource rejection precedes preview work.
- Do not edit files, move refs, push, merge, release, access private material, query new
  scope, or grant PRODUCT/SECURITY/publication approval.

### Post-Verdict Flow

- `REVISE`: fix only the findings, create a new single product candidate, and submit it
  to another fresh non-implementing read-only acceptance task. The old verdict does
  not transfer to new product bytes.
- `GO`: freeze product bytes immediately and create only a documentation seal recording
  the exact product SHA, P0-P3 result, and TECH verdict. Do not rerun full TECH
  acceptance merely because documentation changed while product bytes did not.
- After TECH `GO`, the sole next gate is human `PRODUCT PASS` from the product owner for
  the exact V2-2 product candidate. TECH `GO` is not PRODUCT PASS, SECURITY PASS,
  publication, or release.

### Current Stop Boundary

- Do not push, move or merge `main`, create a release, begin V2-3, distribute previews
  or reports, or describe a fingerprint as package/evidence identity.
- Do not access private novels, canon, derived content, images, saves, or private
  reports. Acceptance material remains public-safe or synthetic.
- Preserve the primary checkout's untracked `uv.lock` at 14,471 bytes and SHA-256
  `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`.
