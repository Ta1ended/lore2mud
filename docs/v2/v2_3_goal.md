# Goal: 实现 Lore2MUD V2-3 Capability Module Architecture

_状态：产品负责人已于 2026-08-06 明确授权开始 V2-3；本文件是供全新 Codex 会话执行的自包含 Goal。它不授权 push、移动或合并 `main`、release、V2-4、V2-5 或私人材料访问。_

## Controller 指令

你是本阶段 Controller。收到本 Goal 后立即创建并持续执行一个 Goal，完成实时基线核对、设计、接口冻结、实现、验证、独立 TECH 验收和交接。不得只停留在分析或计划，也不得把模型输出当作正确性证据。

本里程碑的唯一目标是：

```text
GameProject v1 capability_requirement_ids
  -> engine-shipped static CapabilityCatalog
  -> deterministic dependency/version/safety/namespace resolution
  -> ResolvedCapabilityPlan v1
  -> capability-enabled unsealed preview
  -> isolated GameSession + namespaced capability state
  -> typed capability intents/effects/events/player-safe views
  -> replay/checkpoint evidence
  -> shared Python SDK and structured CLI
```

V2-3 必须让一个引擎内置 reference capability 在不修改 `World`、`src/lore2mud/engine/save.py` 或 capability-specific CLI/Web routing 的情况下完成解析、运行、事件、投影和 checkpoint round trip。通用 capability host 可以修改 application/authoring 适配层，但新增具体 capability 只能注册到静态 catalog 与 engine-owned implementation registry。

## 授权与实时基线

规划时已确认：

- 远端 `main`：`ba729be8d80dbcbefe90a1dc801003deec7c4c95`。
- V2-2 workstream：`bfec33a538d184c36822efeb11eff3dd6d8e7fc5`。
- V2-2 integration merge candidate：`c37969f6b6958e66474738f88a53b9d5c2f50d99`。
- `c37969f` 的第一父提交是 `ba729be`，第二父提交是 `bfec33a`。
- integration tree 与 V2-2 tree 均为 `d7ea31bd3cda9c84cdf5e1e47b2ddedb46771753`，`git diff c37969f^2 c37969f` 为空。
- GitHub PR #1 是 `main <- integration/v2-2-to-main` 的 clean Draft PR；exact-head tests 和 quality 已成功。
- 主工作区未跟踪 `uv.lock` 必须保持 14,471 字节，SHA-256 为 `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`。

开始前必须重新查询 live GitHub/remote refs、PR #1、Actions、祖先和 worktree：

1. 如果实时绿色 `main` 已包含 `c37969f` 的完整 integration history，从该 live `main` 创建 `workstream/v2-3-capability-modules`。
2. 如果 PR #1 仍未合并，但 exact `c37969f` 仍是绿色、clean、byte-identical integration candidate，则可以从精确 `c37969f` 创建 stacked V2-3 workstream，不得借此移动 `main`。
3. 如果 `main`、PR head、V2-2 head、tree identity 或 Actions 与上述证据不一致，立即停止并重新计算范围。尚未验收的后续产品提交不得静默进入 V2-3。
4. 远端查询失败时不得把本地 `origin/*` 当成实时 GitHub 证据。

## 隐私与信任边界

- 禁止访问私人小说、canon、派生内容、图片、索引、数据库、存档和私人报告。
- 测试只使用公开 `examples/original_demo`、现有公开 fixtures 和全新合成 capability fixtures。
- package/project 不得提供 Python、import path、handler 名称、脚本语言、native module、submodule、shell、process 或网络权限。
- capability descriptor 是公开数据合同；可执行实现只能来自 source-controlled、engine-shipped registry。
- public diagnostics、views、reports 和 proofing 不得包含隐藏 ID、隐藏条件、私人路径、私人 source hash 或可识别私人内容的标识符。
- 不新增依赖。SemVer、解析、catalog、runtime 和 checkpoint 必须使用标准库与仓库现有依赖完成。

## 必读材料

按顺序读取：

1. `AGENTS.md`
2. `PRODUCT.md`
3. `PROJECT_STATE.md`
4. `NEXT_TASK.md`
5. `CODE_MAP.md`
6. `docs/v2/architecture.md`
7. `docs/v2/roadmap.md`
8. `docs/v2/reference_patterns.md`
9. `docs/v2/development_model.md`
10. `docs/v2/authoring_interface.md`

同时查看 `DEC-0091`、`DEC-0101`、`DEC-0102`、`DEC-0109` 至当前最新决策、`CHANGELOG.md` 的 Unreleased 部分，并只读检查：

- `src/lore2mud/application/`
- `src/lore2mud/authoring/`
- `src/lore2mud/content/`
- `src/lore2mud/engine/save.py`
- `src/lore2mud/engine/world.py`
- `src/lore2mud/cli.py`
- `src/lore2mud/web/`
- `pipeline/forge.py`
- 相关 Schemas、测试、Windows packaging 和公开 fixtures

## 编辑前一次性报告

编辑前报告以下内容，然后直接继续，不等待重复确认：

1. 当前 V2-2 authoring/runtime 数据流和目标 V2-3 capability 数据流。
2. 冻结的公共接口、内部接口、计划模块和精确路径。
3. 各 Agent 的角色、责任域、模型选择和文件所有权。
4. SemVer、解析顺序、namespace、事务、checkpoint、安全、兼容和客户端风险。
5. 非目标与完整验证矩阵。
6. 如何保证解析、preview、simulation、replay 和 checkpoint 失败不会污染项目、调用者输入、活动 session、`World`、capability state、RNG、clock、event sequence、save 或输出文件。

## 冻结合同

### 保持不变的 V2-2 合同

- `GameBlueprint v1` 和 `GameProject v1` 的现有 JSON shape、格式版本与 canonical bytes 不变。
- 现有 V2-1/V2-2 Schema 版本和 artifact shape 不变；V2-3 通过新增 Schema、包装类型和通用 runtime 扩展交付。
- 根 requirement 继续使用 `capability_requirement_ids: tuple[str, ...]`。每个 ID 表示对 engine catalog 中该 capability 的无版本上界根要求。
- requirement 为空时，现有 `PreviewBuild v1`、`SimulationReport v1`、proofing、SDK/CLI 输出、fingerprint 和 legacy runtime 行为必须保持 byte-for-byte 兼容。
- `PreviewBuild v1` 与 `SimulationReport v1` 仍是 V2-2 reproducibility evidence，不得被改写成 package、seal 或 release identity。

### 新增公共合同

实现 typed、frozen、canonical、bounded 的：

- `SemanticVersion v1`：严格 SemVer 2.0.0 解析、比较与 canonical serialization；拒绝前导零、溢出、非法 prerelease/build 和非 ASCII token。
- `VersionRequirement v1`：支持精确版本和有界 comparator conjunction；禁止不确定、环境相关或非 canonical 语法。
- `CapabilityDescriptor v1`：stable ID、exact version、safety level、owned state namespace、initial state/schema、accepted action schemas、dependencies、conflicts、predicates、effects、events、player-safe view schema 和 migration declarations。
- `CapabilityCatalog v1`：只读、engine-shipped、稳定排序；拒绝重复 `(capability_id, version)`、非法 descriptor 或 implementation 缺失。
- `ResolvedCapability v1` 与 `ResolvedCapabilityPlan v1`：exact selected versions、dependency edges、migration plan、state namespaces、catalog fingerprint 与确定性顺序。
- `CapabilityIntent`：`capability_id`、`action_id` 和 bounded canonical JSON object parameters；不得携带直接 state patch、代码或实现选择。
- `CapabilityEventData` 和 capability player-safe view entry：只输出 descriptor 允许的公开 payload 与当前 admissible actions。
- `CapabilityPreview v1`：仅在 requirement 非空且成功解析时使用，包装不变的 `PreviewBuild v1`，并绑定 exact plan、initial namespaced state、engine version 和独立 reproducibility fingerprint；仍是 unsealed、non-distributable、not release evidence。
- `CapabilityCheckpoint v1`：仅用于隔离 simulation/replay/save-load checkpoint evidence，组合已有 save v9 document、resolved plan identity、namespaced capability state、determinism context 和 event sequence；不是新的 V1 save format、package 或可分发 artifact。
- `CapabilitySimulationReport v1`：包装不变的 `SimulationReport v1`，增加 plan hash、初始/最终 capability-state hash、capability event/view hashes、witness replay 和 capability checkpoint equivalence。

所有新文档必须有 Schema、typed loader、canonical serialization、稳定排序、严格 bounds、fingerprint 和 SDK/structured-CLI 等价性。

## Catalog 与解析规则

- Catalog 可以包含同一 capability ID 的多个 exact versions，但同一 ID/version 只能有一项。
- 根 `capability_requirement_ids` 默认不接受 prerelease；只有 engine-shipped dependency 明确引用 compatible prerelease 时才可选择 prerelease。
- 对所有 requirement、dependency 和 conflict 做全局约束求交，选择满足全部约束的最高 canonical SemVer；结果不得受输入、dict、文件或注册顺序影响。
- 解析结果按 dependency topological order，再按 capability ID 和 SemVer 做稳定 tie-break。
- 必须在 preview materialization、state creation、`GameSession` construction 或任何输出写入前拒绝：
  - unknown requirement；
  - no satisfying version；
  - duplicate catalog entry；
  - dependency cycle；
  - declared conflict；
  - namespace overlap 或 prefix capture；
  - descriptor/implementation mismatch；
  - invalid initial state/schema；
  - unavailable migration；
  - safety policy denial。
- 初始安全策略固定为：L0、L1 可用；L2 denied by default；L3 forbidden。项目和 package 不得提升安全级别。
- 任何解析错误必须使用现有 `AuthoringDiagnostic v1` envelope；project/catalog errors 使用 `project` stage，preview binding errors 使用 `preview` stage，runtime/checkpoint errors 使用 `simulation` stage。
- 最少提供稳定 code：`capability_not_found`、`capability_version_unsatisfied`、`capability_catalog_duplicate`、`capability_dependency_cycle`、`capability_conflict`、`capability_namespace_overlap`、`capability_safety_denied`、`capability_state_invalid`、`capability_implementation_missing`、`capability_migration_unavailable`、`capability_intent_invalid` 和 `capability_intent_inadmissible`。

## Runtime 与事务边界

- `World` 继续是 V1 gameplay authority。不得向 `World` 添加 reference-capability 分支或 state。
- `GameSession` 是唯一 turn coordinator。Capability host 必须组合进同一 lock、snapshot、rejection 和 event-sequence transaction，不能成为第二套 runtime。
- namespaced state 只能由 owning engine-shipped capability implementation 通过 validated deterministic effects 修改。
- capability implementation 可以读取明确的 immutable context 和 player-safe projection；不得获得任意 `World` 引用、save path、filesystem、process、network 或 importer。
- 对普通 V1 intent，capability observer 失败必须同时恢复 `World`、capability state、RNG、clock、event sequence 和 save-visible state。
- 对 `CapabilityIntent`，malformed/inadmissible rejection 必须产生零 transition events 且完全不变；accepted in-world failure 与 contract rejection 继续区分。
- public `GameView`/Web/CLI 仅在存在 capability data 时增加通用 capability section；空 requirement 的 legacy bytes、view hashes 和 compatibility fields 不变。
- Save v9 写入、v7/v8 读取和 `src/lore2mud/engine/save.py` 不变。Capability checkpoint 通过隔离临时根复用 `SaveLoadService` 生成/读取嵌套的 V1 save document，禁止把 capability state 写进 V1 save。

## Reference Capability

提供一个公开合成、engine-shipped 的 `reference_counter` v1.0.0：

- safety：L1 deterministic；
- namespace：`reference_counter`；
- initial state：`{"count": 0}`，范围 `0..1000`；
- actions：`increment`，参数 `amount` 为 `1..10`；`reset` 仅在 count 非零时 admissible；
- events：公开 `counter_changed` old/new/reason；
- view：仅公开 count 和当前 admissible actions；
- 不读取或修改 `World`，不访问 host I/O，不包含私人数据。

新增该 capability 时只允许注册 descriptor 与 engine-owned implementation。不得为它修改 `World`、save core、CLI/Web capability-specific route 或 hard-code 分支。测试可以使用额外的 synthetic descriptors 验证版本冲突、cycle、namespace、safety 和 migration，但它们不得进入默认 catalog。

## 模块归属

优先新增：

- `src/lore2mud/capabilities/__init__.py`
- `src/lore2mud/capabilities/contracts.py`
- `src/lore2mud/capabilities/semver.py`
- `src/lore2mud/capabilities/catalog.py`
- `src/lore2mud/capabilities/resolution.py`
- `src/lore2mud/capabilities/runtime.py`
- `src/lore2mud/capabilities/persistence.py`
- `src/lore2mud/capabilities/reference.py`
- `src/lore2mud/capabilities/serialization.py`

窄适配允许修改：

- `src/lore2mud/application/contracts.py`
- `src/lore2mud/application/session.py`
- `src/lore2mud/application/projection.py`
- `src/lore2mud/authoring/contracts.py`
- `src/lore2mud/authoring/preview.py`
- `src/lore2mud/authoring/simulation.py`
- `src/lore2mud/authoring/proofing.py`
- `src/lore2mud/authoring/serialization.py`
- `src/lore2mud/authoring/service.py`
- `src/lore2mud/authoring/sdk.py`
- `src/lore2mud/authoring/structured_cli.py`
- `src/lore2mud/cli.py` 仅做通用命令解析与结果呈现
- `src/lore2mud/web/` 仅做通用 capability intent/view transport

不得扩张 `pipeline/forge.py`。除非只读架构审查证明需要一个窄 adapter，并在编辑前报告中单独说明，否则不得修改 pipeline。

同步新增或更新 `schemas/`、`docs/v2/capability_modules.md`、公开合成 fixtures、聚焦测试、`CODE_MAP.md`、`CHANGELOG.md`、`PROJECT_STATE.md` 和 `NEXT_TASK.md`。`README.md`、`PROJECT_STATE.md`、`NEXT_TASK.md` 如更新，必须中文在前、英文在后且语义同步。

## 协作与模型分工

- Product/Specification：只读提炼字段语义、验收场景、兼容边界和非目标，不授予 PRODUCT PASS。
- Architect/Engine Lead：冻结 SemVer、resolver、runtime transaction、checkpoint 和 public contract；使用可用的高可靠推理。
- Implementation A：capability contracts、SemVer、catalog、resolver、serialization、Schemas；拥有对应文件。
- Implementation B：runtime transaction、reference capability、checkpoint、application integration；拥有对应文件。
- Implementation C：authoring preview/simulation、SDK/CLI/Web parity、fixtures、docs/tests；只有在前两域接口冻结后才能开始。低成本模型可承担 Schema/fixture/重复测试与证据整理，但不得独立决定共享合同或安全边界。
- Controller：维护 worktree、接口冻结、文件 ownership、集成、返工、验证、候选提交和交接。
- Independent Acceptance：未参与实现的全新只读任务；优先采用与主要实现不同的可靠模型，按 P0-P3 先列 findings，最终只能输出 `GO` 或 `REVISE`。

最多同时运行两个实现 Agent。同一文件只能有一个 owner。跨域修改必须先报告给 Controller；共享接口冻结前不得并行写依赖实现。

## 可恢复检查点

1. **Contracts checkpoint**：SemVer、descriptor、catalog、resolver、diagnostics、Schemas 和排列无关 resolution tests。
2. **Runtime checkpoint**：namespaced state、transaction rollback、reference capability、generic event/view、checkpoint round trip。
3. **Authoring checkpoint**：capability preview/report、simulation/replay/proofing、SDK/CLI/Web parity、empty-requirement byte compatibility。
4. **Candidate checkpoint**：Windows packaging、完整门禁、单一 coherent product commit、独立验收和交接。

每个 checkpoint 先跑 focused tests，可创建本地 checkpoint commit，并记录精确 WIP。只在 coherent operation 之间暂停。最终重型矩阵只在产品候选阶段完整运行一次。

## 必须证明

- 相同 catalog、project、seed、clock 和 intent sequence 产生相同 plan、canonical bytes、diagnostics、events、views、state hashes、reports 和 fingerprints。
- catalog/requirement/dependency 输入顺序变化不改变解析结果。
- 空 requirement 的 V2-2 blueprint/project/preview/report/SDK/CLI bytes 与 baseline fixtures 完全一致。
- 支持的 capability requirement 不再返回 `capability_requirement_unsupported_v2_2`，而是解析为 exact plan；不支持或非法集合返回新的稳定诊断。
- SDK 与 structured CLI 的 artifacts、diagnostics、exit semantics 和 capability evidence 等价。
- 所有解析拒绝发生在 preview/session/state/output 之前；runtime rejection 同时保持 `World`、capability state、RNG、clock、event sequence、save/checkpoint 不变。
- reference capability 可通过 catalog 注册加入，而无需修改 `World`、save core 或 capability-specific client routing。
- checkpoint restore 与 uninterrupted execution 的 World save hash、capability-state hash、view hash、event sequence 和 final report 等价。
- descriptor、events、views、proofing 和 reports 不泄露 hidden/private/implementation data。
- presentation/workspace metadata 不影响 capability preview/report fingerprints。
- V2-1、V2-2 fixed-profile path、CLI、Web、public content、save v9、v7/v8 reads、runtime campaign 和 Windows packaging 不退化。

## 验证矩阵

使用主项目 `.venv\Scripts` 工具，并把 `PYTHONPATH` 绑定到隔离 worktree 的 `src`。正式命令前先运行：

```powershell
python -c "import lore2mud; print(lore2mud.__file__)"
```

确认 import 来自 V2-3 worktree。将 `TEMP`、`TMP`、`TMPDIR` 和 pytest `--basetemp` 放在仓库外。

运行：

- focused capability contracts/semver/resolution/runtime/persistence/authoring/SDK/CLI/Web/security tests；
- 真实 SDK/subprocess structured CLI 等价 smoke；
- catalog permutation、repeat build/report bytes、replay/checkpoint equivalence；
- empty-requirement V2-2 golden byte comparison；
- reference capability registration without `World`/save-core/client-specific changes audit；
- Windows zipapp/PyInstaller capability workflow；
- `python -m unittest discover`
- `python -m pytest -q`
- `python -m pytest -q -n auto --basetemp=<repo-external>`
- `ruff check .`
- `pyright`
- `python -m compileall -q src pipeline scripts tests`
- `python -m lore2mud validate --content examples/original_demo`
- `python -m pip check`
- `python scripts/check_repo_safety.py --history`
- `git fsck --full --no-dangling`
- `git diff --check`
- `git diff <baseline>..HEAD --check`

缺失工具、权限性 skip、环境污染或未执行项必须准确报告，不得写成通过。

## 提交、验收与停止规则

完成本地验证后创建一个 coherent V2-3 产品候选提交，工作树必须干净。由未参与实现的全新任务在精确 SHA 上严格只读验收。

- `REVISE`：只修复 findings，创建新候选，并交给另一个全新验收任务。
- `GO`：冻结产品字节，创建 documentation-only handoff seal，然后立即停止。
- documentation-only seal 不得冒充新产品候选；产品字节未变化时不得重复声称新的全量 TECH 验收。
- 不得 push、移动或合并 `main`、release、开始 V2-4/V2-5、发布 preview/checkpoint/report，或把 TECH GO 当作 PRODUCT PASS。
- 唯一下一门禁是产品负责人对精确 V2-3 产品候选给出 PRODUCT PASS；publication、SECURITY PASS、main integration 和 release 仍需独立授权。

最终报告必须包含：实时 baseline/target SHA、角色与模型记录、改动路径、公共合同、diagnostic codes、实际命令及结果、独立验收 verdict、剩余风险、Git 状态、产品候选与文档封存 SHA，以及唯一下一门禁。
