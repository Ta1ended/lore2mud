# 项目状态 / Project State

更新日期：2026-08-05

## 中文

### 目标

在隔离分支上完成 Lore2MUD V2-2 Agent Authoring Interface：把公开安全输入与已批准
`GameBlueprint v1` 规范化为 `GameProject v1`，构造固定 V1 兼容 profile 的未封存预览，
通过隔离 `GameSession` 生成可重放模拟证据与只读 proofing，并让 Python SDK 与结构化
CLI 共用一个实现。

### 当前状态

- 工作分支：`workstream/v2-2-agent-authoring`；隔离 worktree：
  `D:\MUD game kaifa\.codex-worktrees\v2-2-agent-authoring-20260805`。
- 起始文档头：`eb972903a0b959f09a647a1727a6ed66f2d098f7`；其已验收 V2-1 产品祖先是
  `c8ee518ef39f938ece374cbd3f7c9bca06de2408`；规划祖先是
  `1d4b26d9127d4229893911cf260cf3c2f4b0ce3a`。
- 2026-08-05 开始时实时 GitHub `main` 是
  `564530d87aea17da26544b7793701e0dca0fe57d`，未包含 `eb972903`；因此未移动本地
  `main`，而是从精确绿色 `eb972903` 建立候选。
- 修复期间实时 GitHub `main` 前进到 README-only 的
  `bf3f8b93d40a04b21107bc9b7c9f828a7f000539`，其父仍是 `564530d`，与
  `eb972903` 分叉且不包含该 V2-1 文档头；新 main tests `30990599624` 与 quality
  `30990599399` 均成功，因此重新计算后仍以精确 `eb972903` 为 V2-2 起点，不合并或
  重基平行 README 提交。
- 第八轮验收因平台中断没有产生 verdict，不计作产品决定。第九轮对精确候选
  `1ea39acc195581461c56ad56ee98dcaa1ab0ce77` 独立关闭此前 typed-input 与循环 document
  P2，但发现 typed request 资源 P2；DEC-0105 修复后的
  `e7054d7c14a6e77f92874becdad6a9e451b72705` 第十轮又发现资源拒绝晚于 preview 构造/加载
  的 P2，并给出 `REVISE`。第十一轮对精确候选
  `cb974cb9ae2f4736e52f1f519e4aa8947c54be07` 独立关闭 DEC-0106 P2，但发现 typed
  blueprint/project/report 与 CLI bounded canonical round-trip 不一致的 P2，并指出 CHANGELOG
  决策范围遗漏 DEC-0106 的 P3，最终给出 `REVISE`。第十二轮对精确候选
  `e1f3a806b987209f7ed9435384739c9e6865d513` 关闭 DEC-0107 findings，但发现 typed
  project/report 中的 `bytes` 等非 JSON 标量会从 SDK 泄漏原始 `TypeError` 的 P2，并给出
  `REVISE`。DEC-0108 修复与完整本地门禁已通过；本文件无法自引用 amend 后 SHA，
  Controller 会在提交后把精确 SHA 交给全新 Reviewer 13。
- 当前没有 TECH `GO`、PRODUCT PASS、SECURITY PASS、push、merge、release、`main`
  移动或 V2-3 授权。

### 已实现

- `src/lore2mud/authoring/`：冻结的 blueprint/project/diagnostic/preview/simulation/
  proofing/result 合同、规范 JSON、稳定排序与 SHA-256、共享 `AuthoringService`、
  `AgentAuthoringSDK` 和结构化 CLI 适配器。
- `GameBlueprint v1` 与 `GameProject v1`：已批准蓝图、公开输入、决策/trace、固定 V1
  内容快照、build lock 与不参与语义身份的 workspace metadata。
- 公共内容先使用共享有界 UTF-8 JSON 规则捕获并规范化，V1 `ContentPack` loader 只读取
  隔离的不可变临时快照；项目不会保存源目录或绝对路径。
- typed SDK 的 blueprint/project/report 与嵌套 canonical content bytes 先通过共享有界
  JSON 和对应 loader 归一化。解码、递归、shape 或嵌套类型错误均转换为稳定
  `AuthoringResult` 拒绝；project validation 先于 capability diagnostics，结果诊断不超过
  Schema 的 4,096 项上限。
- typed blueprint/project/report 还会先流式生成规范 JSON 并通过同一 bounded reader；
  资源失败分别使用公开 artifact ID `blueprint`、`project`、`report`。Blueprint 默认
  seed/clock 在 Schema 与 loader 中均为 signed-64。模拟仍先做 request resource preflight，
  再验证 typed project，二者都发生在 preview 构造前。
- 共享 bounded canonical round-trip 将 JSON encoder 的 `TypeError` 归一化为
  `authoring_input_invalid_json`；typed project/report 中的 `bytes` 等非 JSON 标量不会再从
  SDK 泄漏原始异常，且仍在 preview/session 工作前拒绝。
- typed `SimulationRequest` 先迭代预检循环/depth/node，再在共享 8 MiB 上限内流式生成规范
  JSON，并由同一 bounded reader 统一 string/integer/UTF-8 规则。byte/string/depth/node/
  integer 超限在任何 preview/session 工作前返回与 CLI 等价的单一稳定
  `authoring_input_*` 拒绝。
- 资源预检同时发生在 `simulate_project()` 构造 preview 前和 `simulate_preview()` 加载
  preview 前；资源拒绝优先于 capability diagnostics，且不调用 preview materializer 或
  `GameSession`。语义 shape/domain 校验仍沿用原有路径。
- direct Python blueprint/project documents 使用同一 depth/node/string 上限做迭代预检；
  活动路径上的循环 dict/list/tuple 在 domain loader 前稳定拒绝，共享但非循环的值不误判。
- 固定 `lore2mud.v1.compatibility.fixed` preview：`sealed=false`、
  `distributable=false`、`release_evidence=false`，并绑定当前 engine version。非空 V2
  capability requirement 在构造预览或模拟前以稳定诊断拒绝。
- `SimulationReport v1`：记录 blueprint/project/request/preview hashes、engine version、
  seed/clock、初始/最终状态与 view hashes、每步 Intent/status/event types、胜负条件、
  witness replay 和 save/load checkpoint 等价性。
- 模拟只从 preview bytes 创建新的 `ContentPack`、`SaveLoadService`、`World` 与
  `GameSession`，所有动作都通过 typed `GameIntent`；项目、源输入、preview、活动 session、
  RNG、clock、事件序列和既有存档不被污染。
- proofing 只读取分离的玩家安全 `GameView`，输出有界 nodes/edges 与 view 中已经存在的
  concrete admissible intents；未知 trace endpoints、隐藏动作/ID/条件、内部诊断、绝对路径、
  私人 source hash 和 presentation metadata 均不输出。
- `python -m lore2mud author create-project|validate|preview|simulate|replay|proof` 与 SDK
  调用同一服务；stdout 是规范 `AuthoringResult v1`，成功 artifact 可原子写出，退出码
  `0/1/2` 分别表示成功、结构化拒绝和 argparse/transport misuse。
- 新增 10 个 Schema、公开合成 fixtures、聚焦/端到端/打包测试和
  `docs/v2/authoring_interface.md`；未扩张 `pipeline/forge.py`。

### 验证状态

- V2-2 contracts/privacy/preview/simulation/proofing/SDK/CLI/Windows packaging 聚焦矩阵：
  `81 passed, 61 subtests passed`；其中真实 PyInstaller author workflow 为
  `1 passed, 3 subtests passed`，覆盖 create-project、simulate 和 proof。
- 真实 SDK/subprocess CLI 字节等价、重复 preview、确定性 simulation/replay、超限 request，
  以及 65 位 typed blueprint/project/report 拒绝等价 smoke：`9 passed`。
- 资源拒绝顺序 spy 覆盖 SDK 与 direct `simulate_preview()`：五个边界案例中
  `build_preview`、preview load/materializer、`GameSession` 均为 `0` 次调用；capability-
  blocked project 也返回 `authoring_input_too_complex`。
- 完整 `python -m unittest discover`：`1483` tests，`OK (skipped=11)`。
- 完整 serial pytest：`1472 passed, 11 skipped, 619 subtests passed`；完整
  `pytest -n auto`：同为 `1472 passed, 11 skipped, 619 subtests passed`。
- `ruff check .`、标准 `pyright`（`0 errors, 0 warnings`）、compileall、公开
  `original_demo` validate、`pip check`、history safety、fsck 和工作树/baseline whitespace
  检查均已在 DEC-0108 工作树字节上通过；精确提交后的 baseline range diff 将在 amend 后重跑。
- 11 个 skip 全是此 Windows 主机缺少 symlink privilege/POSIX symlink 的条件性覆盖；没有
  将其写成通过。
- 非产品 harness 记录：一次聚焦命令引用不存在的 `tests/test_cli.py`；一次显式把测试文件
  传给 `pyright` 而绕过仓库配置；两次 Controller tool timeout 过短中止命令；一次把
  `%TEMP%` 放在 worktree 内而被 cold-start 隔离检查正确拒绝。所有正式命令均绑定外部
  TEMP/TMP 与 worktree `PYTHONPATH` 后成功重跑。第六轮验收的前两次 xdist 也分别因宿主
  `%TEMP%` 权限残留和错误的 `New-Item` 参数在执行 0 tests 前退出；外部 temp 正式重跑
  完整通过。第七轮修复后一次聚焦启动因递归清理临时目录被主机安全策略在 0 tests 前
  拦截，改用全新仓库外 temp 后完整通过。DEC-0106 的首次 unittest 外层工具在 121 秒
  超时，尽管 runner 已输出 `1477 tests OK`；300 秒超时的全新外部 TEMP 正式重跑以 exit 0
  完整通过。DEC-0107 首个聚焦命令引用了不存在的 `tests/test_authoring_privacy.py`，在收集
  0 tests 前退出；首个 xdist 运行又因新 subtest metadata 直接携带 signed-64 边界整数，
  触发 execnet 的 32 位控制协议限制。改为字符串标签后，单测与完整 xdist 均通过。这些记录
  是已闭环 harness 事实，不构成产品逻辑失败或通过。
- GitHub REST 复核 live `main=bf3f8b93`、V2-1 workstream=`eb972903`；GitHub Actions
  tests `30967832753` 与 quality `30967832780` 仍为 exact `eb972903` 的
  `completed/success`。
- 第五轮只读验收的唯一 P3 是 `CODE_MAP.md` 两处行数，已在 `b33c088` 关闭。第六轮对
  `b33c088` 返回 typed-SDK 结构化拒绝/诊断上限 P2；第七轮对 `845c04c` 独立关闭该 P2，
  但对循环内存 document 返回一个新 P2；第八轮平台中断且没有 verdict。第九轮对
  `1ea39ac` 独立关闭旧 P2，但发现 typed request 资源 P2；第十轮对 `e7054d7` 独立关闭
  该 P2 的诊断等价性，却发现资源拒绝顺序 P2。第十一轮对 `cb974cb` 关闭 DEC-0106 P2，
  但发现 typed blueprint/project/report bounded parity P2 与 CHANGELOG P3。第十二轮对
  `e1f3a806` 关闭 DEC-0107 findings，但发现 unsupported typed scalar 泄漏 `TypeError` 的
  P2。DEC-0108 已修复并通过完整本地门禁；amend 后候选仍需全新 Reviewer 13 验收，
  Controller 不能授予 TECH `GO`。

### 角色与模型

- Product/Specification：只读提炼字段语义、验收场景、兼容边界与非目标；未授予
  PRODUCT PASS。
- Architect/Engine Lead：只读检查 V2-1 application、loader/save、CLI、Forge、Schema、
  测试和 Windows packaging，确认 `src/lore2mud/authoring/` 的最小归属。
- Contracts/Project Implementation：原隔离任务中止且没有可集成产出；Controller 接管
  合同、project、serialization、Schema 和隐私加固。
- Preview/Simulation/Proofing Implementation：`preview_simulation_impl` 完成交付并由
  Controller 路径集成、复核和返工；使用继承模型，工具未暴露精确模型 ID。
- SDK/CLI Implementation：`sdk_cli_impl` 完成交付并由 Controller 路径集成、静态导入
  加固及真实 subprocess/Windows smoke 复核；使用继承模型，工具未暴露精确模型 ID。
- Controller：维护隔离 worktree、冻结接口、集成、修复、全量门禁、单一候选提交和交接；
  模型输出只作为实现输入，不作为正确性证据。
- Independent TECH Acceptance：第五轮发现文档行数 P3，第六轮发现 typed-SDK P2，
  第七轮关闭旧 P2 后发现循环 document P2，第八轮平台中断无 verdict，第九轮关闭旧 P2
  后发现 typed request 资源 P2，第十轮关闭旧 P2 后发现资源拒绝顺序 P2，第十一轮关闭
  DEC-0106 P2 后发现 typed artifact bounded parity P2 与 CHANGELOG P3，第十二轮关闭
  DEC-0107 findings 后发现 unsupported typed scalar `TypeError` P2；有 verdict 的
  轮次均为全新、未参与实现、严格只读任务并按 findings-first 输出。它们使用继承模型，
  工具未暴露可审计精确模型 ID；DEC-0108 amend 后候选必须交给全新 Reviewer 13 决定。

### 保持的边界

- 未访问私人小说、canon、派生内容、图片、存档或私人报告；测试仅使用公开 Demo 和公开
  合成材料。
- 不新增依赖，不改变 save v9 写入、v7/v8 读取、内容包版本、runtime campaign、既有
  Schema 版本或 `World` 架构。
- preview/report fingerprint 只证明复现性，不是 `GamePackage v2`、package/evidence
  identity、seal、release evidence 或分发授权。
- 不实现 capability catalog、semver、namespace、依赖/冲突、安全级别、migration、
  workbench、编辑 UI、第二套 compiler/runtime、MCP、V2-3、V2-4 或 V2-5。
- 主工作区未跟踪 `uv.lock` 必须保持 14,471 字节、SHA-256
  `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`。

### 剩余风险与唯一下一门禁

- 当前修复的提交后精确 range check 和全新独立 TECH 决定仍待完成；Windows PyInstaller
  smoke 已通过，但仍依赖主项目已安装的固定构建工具链。
- 即使 TECH `GO`，仍没有 PRODUCT PASS、SECURITY PASS、publication、push、merge、
  release、`main` 移动或 V2-3 授权。
- 唯一下一门禁：把 DEC-0108 修复 amend 为一个干净、连贯的精确 V2-2 产品候选，并交给
  全新 Reviewer 13 严格只读验收；最终只能输出 `GO` 或 `REVISE`。

## English

### Objective

Complete the Lore2MUD V2-2 Agent Authoring Interface on an isolated branch: normalize
public-safe inputs and an approved `GameBlueprint v1` into `GameProject v1`, build an
unsealed preview for the fixed V1 compatibility profile, generate replayable isolated
`GameSession` evidence and read-only proofing, and expose one implementation through
the Python SDK and structured CLI.

### Current Status

- Work branch: `workstream/v2-2-agent-authoring`; isolated worktree:
  `D:\MUD game kaifa\.codex-worktrees\v2-2-agent-authoring-20260805`.
- Starting documentation head: `eb972903a0b959f09a647a1727a6ed66f2d098f7`;
  its accepted V2-1 product ancestor is
  `c8ee518ef39f938ece374cbd3f7c9bca06de2408`; the planning ancestor is
  `1d4b26d9127d4229893911cf260cf3c2f4b0ce3a`.
- At the 2026-08-05 start check, live GitHub `main` was
  `564530d87aea17da26544b7793701e0dca0fe57d` and did not contain `eb972903`.
  Local `main` was therefore left untouched and the candidate started from exact green
  head `eb972903`.
- During repair, live GitHub `main` advanced to README-only commit
  `bf3f8b93d40a04b21107bc9b7c9f828a7f000539`, whose parent remains `564530d`.
  It diverges from and does not contain the `eb972903` V2-1 documentation head. The new
  main tests `30990599624` and quality `30990599399` succeeded, so scope recalculation
  still selects exact `eb972903` as the V2-2 base without merging or rebasing the
  parallel README commit.
- The eighth review was interrupted by the platform and produced no verdict, so it is
  not a product decision. The ninth review of `1ea39acc` closed the earlier typed-input/
  cyclic-document P2s but found the typed-request resource P2. Reviewer 10 on exact
  candidate `e7054d7c14a6e77f92874becdad6a9e451b72705` independently verified the corrected
  diagnostic and CLI equivalence but found a new P2 because resource rejection happened
  after preview construction/loading. Reviewer 11 on exact candidate
  `cb974cb9ae2f4736e52f1f519e4aa8947c54be07` closed the DEC-0106 P2 but found a new P2
  because typed blueprint/project/report values did not share the CLI bounded canonical
  round trip, plus a P3 because CHANGELOG omitted DEC-0106. It issued `REVISE`.
  Reviewer 12 on exact candidate `e1f3a806b987209f7ed9435384739c9e6865d513`
  closed the DEC-0107 findings but found a P2 because non-JSON scalars such as `bytes`
  in typed projects/reports escaped raw `TypeError` from SDK operations. It issued
  `REVISE`. DEC-0108 is repaired and full local gates pass; this file cannot self-
  reference the amended SHA. The Controller will give that exact candidate to fresh
  Reviewer 13.
- There is currently no TECH `GO`, PRODUCT PASS, SECURITY PASS, push, merge, release,
  `main` movement, or V2-3 authorization.

### Implemented

- `src/lore2mud/authoring/`: frozen blueprint/project/diagnostic/preview/simulation/
  proofing/result contracts, canonical JSON, stable ordering and SHA-256, shared
  `AuthoringService`, `AgentAuthoringSDK`, and structured CLI adapter.
- `GameBlueprint v1` and `GameProject v1`: approved blueprint, public inputs,
  decisions/traces, fixed V1 content snapshot, build lock, and workspace metadata that
  is outside semantic identity.
- Public content is captured and normalized through the shared bounded UTF-8 JSON
  rules before the V1 `ContentPack` loader receives only an isolated immutable
  temporary snapshot. Projects retain no source directory or absolute path.
- Typed SDK blueprint/project/report values and nested canonical content bytes are
  normalized through the shared bounded JSON rules and corresponding loaders first.
  Decode, recursion, shape, or nested-type failures become stable `AuthoringResult`
  rejections; project validation precedes capability diagnostics, and result diagnostics
  cannot exceed the Schema limit of 4,096 entries.
- Typed blueprint/project/report values also stream canonical JSON through the same
  bounded reader, with public resource artifact IDs `blueprint`, `project`, and `report`.
  Blueprint default seed/clock values are signed-64 in Schema and loader. Simulation
  still preflights request resources before validating the typed project, and both occur
  before preview construction.
- The shared bounded canonical round trip maps JSON encoder `TypeError` to
  `authoring_input_invalid_json`. Non-JSON scalars such as `bytes` in typed projects or
  reports no longer escape SDK operations and still reject before preview/session work.
- A typed `SimulationRequest` receives iterative cycle/depth/node preflight, canonical
  JSON streaming under the shared 8-MiB cap, and the same bounded reader for string,
  integer, and UTF-8 rules. Byte/string/depth/node/integer failures return one stable
  SDK/CLI-equivalent `authoring_input_*` rejection before any preview or session work.
- Resource preflight runs before `simulate_project()` builds a preview and before
  `simulate_preview()` loads one. Resource diagnostics also precede capability
  diagnostics, while semantic shape/domain validation retains its existing path.
- Direct Python blueprint/project documents receive iterative preflight under the same
  depth, node, and string limits. A dict/list/tuple cycle on the active path rejects
  before domain loading, while a shared acyclic value is not treated as a cycle.
- Fixed `lore2mud.v1.compatibility.fixed` preview with `sealed=false`,
  `distributable=false`, `release_evidence=false`, and current-engine binding. Any
  non-empty V2 capability requirement is rejected with stable diagnostics before
  preview construction or simulation.
- `SimulationReport v1`: blueprint/project/request/preview hashes, engine version,
  seed/clock, initial/final state and view hashes, per-step Intent/status/event types,
  win/loss conditions, witness replay, and save/load checkpoint equivalence.
- Simulation creates fresh `ContentPack`, `SaveLoadService`, `World`, and `GameSession`
  values from preview bytes and submits only typed `GameIntent` values. It does not
  contaminate projects, source inputs, previews, active sessions, RNG, clock, event
  sequence, or existing saves.
- Proofing reads only a detached player-safe `GameView` and emits bounded nodes/edges
  plus concrete admissible intents already present in that view. Unknown trace
  endpoints, hidden actions/IDs/conditions, internal diagnostics, absolute paths,
  private source hashes, and presentation metadata are absent.
- `python -m lore2mud author create-project|validate|preview|simulate|replay|proof` and
  the SDK call the same service. Stdout is canonical `AuthoringResult v1`; successful
  artifacts may be written atomically; exit codes `0/1/2` mean success, structured
  rejection, and argparse/transport misuse.
- Ten Schemas, public synthetic fixtures, focused/end-to-end/packaging tests, and
  `docs/v2/authoring_interface.md` were added. `pipeline/forge.py` was not expanded.

### Verification Status

- The V2-2 contracts/privacy/preview/simulation/proofing/SDK/CLI/Windows packaging
  focused matrix passed `81 tests` and `61 subtests`. The real PyInstaller author
  workflow passed `1 test` and `3 subtests`, covering create-project, simulate, and
  proof.
- The real SDK/subprocess CLI byte-equivalence, repeated-preview, deterministic
  simulation/replay, over-limit-request, and 65-digit typed blueprint/project/report
  rejection-equivalence smoke passed `9 tests`.
- Resource-order spies across SDK and direct `simulate_preview()` passed, with zero
  preview-build/load/materializer/session calls for all five resource cases; a
  capability-blocked project still returns `authoring_input_too_complex` first.
- Full `python -m unittest discover`: `1483` tests, `OK (skipped=11)`.
- Full serial pytest: `1472 passed, 11 skipped, 619 subtests passed`; full
  `pytest -n auto`: the same `1472 passed, 11 skipped, 619 subtests passed`.
- `ruff check .`, standard `pyright` (`0 errors, 0 warnings`), compileall, public
  `original_demo` validation, `pip check`, history safety, fsck, and working-tree/baseline
  whitespace checks pass on the DEC-0108 worktree bytes. The exact post-commit baseline
  range diff will be rerun after amending the candidate.
- All 11 skips are conditional coverage for unavailable Windows symlink privilege or
  POSIX symlinks; they are not reported as passes.
- Non-product harness record: one focused command referenced nonexistent
  `tests/test_cli.py`; one invocation explicitly passed test files to `pyright` and
  bypassed repository configuration; two Controller tool timeouts were too short and
  terminated commands; one run placed `%TEMP%` inside the worktree and was correctly
  rejected by cold-start isolation. Every formal command was rerun successfully with
  external TEMP/TMP and worktree-bound `PYTHONPATH`. The first two xdist attempts in
  sixth acceptance also exited before 0 tests because of stale host `%TEMP%` permissions
  and an incorrect `New-Item` parameter; the formal external-temp rerun passed in full.
  One post-seventh-review focused launch was blocked before 0 tests because recursive
  temp cleanup violated the host safety policy; the fresh external-temp rerun passed in
  full. The first DEC-0106 unittest wrapper timed out at 121 seconds after the runner had
  printed `1477 tests OK`; a fresh external-temp rerun with a 300-second wrapper completed
  with exit 0. The first DEC-0107 focused command named nonexistent
  `tests/test_authoring_privacy.py` and exited before collection. The first xdist run then
  exposed an execnet control-protocol limitation because a new subtest metadata field
  carried a signed-64 boundary integer directly. Converting only the test label to text
  made the focused and full xdist reruns pass. These are closed harness facts, not product
  logic failures or passes.
- GitHub REST reconfirmed live `main=bf3f8b93` and V2-1 workstream=`eb972903`.
  GitHub Actions tests `30967832753` and quality `30967832780` remain
  `completed/success` for exact `eb972903`.
- The fifth read-only review's only P3 was two `CODE_MAP.md` line counts and was closed
  in `b33c088`. The sixth review returned the typed-SDK rejection/diagnostic-bound P2;
  the seventh closed it before finding the cyclic-document P2. The eighth was interrupted
  without a verdict. The ninth closed the old P2 before finding the typed-request resource
  P2; Reviewer 10 closed that one before finding the preview-order P2. Reviewer 11 closed
  DEC-0106 but found the typed-artifact bounded-parity P2 and CHANGELOG P3 in `cb974cb`.
  Reviewer 12 closed those findings on `e1f3a806` but found the unsupported typed-scalar
  `TypeError` P2. DEC-0108 is repaired and full local gates pass. The amended candidate
  still requires fresh Reviewer 13; Controller verification cannot grant TECH `GO`.

### Roles And Models

- Product/Specification: read-only extraction of field semantics, acceptance
  scenarios, compatibility limits, and non-goals; no PRODUCT PASS was granted.
- Architect/Engine Lead: read-only review of the V2-1 application layer, loader/save,
  CLI, Forge, Schemas, tests, and Windows packaging; confirmed the minimal
  `src/lore2mud/authoring/` ownership boundary.
- Contracts/Project Implementation: the original isolated task was interrupted with
  no integrable output; the Controller took over contracts, project, serialization,
  Schemas, and privacy hardening.
- Preview/Simulation/Proofing Implementation: `preview_simulation_impl` delivered the
  domain and the Controller integrated, reviewed, and reworked it by path. It used the
  inherited model; the tool did not expose an auditable exact model ID.
- SDK/CLI Implementation: `sdk_cli_impl` delivered the domain and the Controller
  integrated it by path, hardened static imports, and added real subprocess/Windows
  smoke review. It used the inherited model; the tool did not expose an auditable
  exact model ID.
- Controller: owns the isolated worktree, interface freeze, integration, repairs, full
  gates, single candidate commit, and handoff. Model output is implementation input,
  not correctness evidence.
- Independent TECH Acceptance: the fifth review found the documentation line-count P3,
  the sixth found the typed-SDK P2, the seventh closed it before finding the cyclic-
  document P2, the eighth was interrupted without a verdict, the ninth found the typed-
  request resource P2, Reviewer 10 found the preview-order P2 after closing that one, and
  Reviewer 11 closed DEC-0106 before finding the typed-artifact parity P2 and CHANGELOG
  P3; Reviewer 12 closed DEC-0107 before finding the unsupported typed-scalar P2.
  Every verdict-bearing review was fresh, non-implementing, strictly read-only, and
  findings-first. The tasks used inherited models whose auditable exact IDs were not
  exposed. Fresh Reviewer 13 must decide the amended DEC-0108 candidate.

### Preserved Boundaries

- No private novel, canon, derived content, image, save, or private report was accessed.
  Tests use only the public Demo and public synthetic material.
- No dependency, save v9 write, v7/v8 read, content-pack version, runtime campaign,
  existing Schema version, or `World` architecture changed.
- Preview/report fingerprints prove reproducibility only. They are not
  `GamePackage v2`, package/evidence identity, a seal, release evidence, or distribution
  authorization.
- No capability catalog, semver, namespace, dependency/conflict resolver, safety
  level, migration, workbench, editor UI, alternate compiler/runtime, MCP, V2-3, V2-4,
  or V2-5 was implemented.
- The primary checkout's untracked `uv.lock` must remain 14,471 bytes with SHA-256
  `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`.

### Residual Risks And Single Next Gate

- The post-commit exact-range check and a fresh independent TECH decision remain
  pending. Windows PyInstaller smoke passed but still depends on the pinned build
  toolchain installed in the primary project environment.
- Even TECH `GO` would not grant PRODUCT PASS, SECURITY PASS, publication, push,
  merge, release, `main` movement, or V2-3 authorization.
- The sole next gate is to amend the DEC-0108 repair into one clean coherent exact V2-2
  product candidate and submit it to fresh Reviewer 13 for strict read-only acceptance
  ending only in `GO` or `REVISE`.
