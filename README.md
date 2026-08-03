# Lore2MUD

## 中文

Lore2MUD 是一个**供 Agent 调用的小说转文字游戏引擎**。开发 Agent 是直接工具用户；
产品所有者/创作者负责产品决策、创意方向和权利授权；玩家是最终用户。Lore2MUD 本身
不是 Agent。

本仓库是公开仓库，只包含通用引擎、工具代码和原创示例，不包含第三方小说、专有角色、
私人改编、图片、音频或由所有者控制的派生材料。MIT 许可证只覆盖仓库自有内容，不覆盖
导入或生成的外部内容。

### 产品与架构

- [产品定义](PRODUCT.md)：用户、制作模式、输入输出、PLAT-1、成功指标、非目标和权利边界。
- [当前代码地图](CODE_MAP.md)：真实 V1 符号、数据流、模块规模、风险和未来修改入口。
- [V2 目标架构](docs/v2/architecture.md)：创作平面、确定性运行时平面、合同、兼容性和能力安全。
- [V2 开发模式](docs/v2/development_model.md)：产品权责、Codex 角色、模型下限、
  TECH/PRODUCT/SECURITY 门禁和 Git 门禁。
- [V2 路线图](docs/v2/roadmap.md)：V2-0 至 V2-5 以及 PLAT-1。

### 当前已有能力：V1

当前公开运行时是一个本地单人 Python 文字 MUD。它把严格的多文件 JSON 内容加载为
`ContentPack`，构建权威 `World`，并通过文字 CLI 和本地 Web 客户端提供游玩体验。
当前能力包括：

- 房间、出口和物品门禁；强类型物品堆、背包、装备、消耗品、战利品、固定商店、
  金币、确定性战斗和失败恢复；
- 强类型任务、对话和原子效果，叙事状态/条件，以及可选运行时 `campaign.json` 的场景、
  动作、目标、知识和日志；
- save v9 写入、受约束的命名存档槽，以及受保护的 v7/v8 读取兼容；
- 内容校验、公开原创示例、确定性创作编译器、仓库安全检查、Windows 打包和本地 Web 玩家端。

`World`、`CommandProcessor` 和 Web `PlayerSession` 是当前 V1 类型。
`GameBlueprint`、`GameProject`、`GamePackage v2`、`CapabilityDescriptor`、
`GameSession`、`GameIntent`、`GameEvent`、`GameView` 和 `TurnResult` 是 V2 目标，
尚未由 V2-0 文档重置实现。

流水线中的 `CampaignSpec v1` 是确定性的创作中间表示，不是运行时输入，也不能与内容包的
运行时 `campaign.json` 互换。

### 快速开始

需要 Python 3.11 或更高版本。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

游玩公开原创 Demo：

```powershell
python -m lore2mud play --content examples/original_demo
```

旧版形式仍受支持：

```powershell
python -m lore2mud --content examples/original_demo
```

只校验内容，不启动游戏：

```powershell
python -m lore2mud validate --content examples/original_demo
```

启动本地 Web 玩家端：

```powershell
python -m lore2mud web --content examples/original_demo
```

在 CLI 中输入 `help` 查看实时命令注册表。原创 Demo 的流程和内容说明位于
[examples/original_demo/README.md](examples/original_demo/README.md)。

### 仓库结构

```text
src/lore2mud/          V1 运行时、内容加载、CLI 和 Web
pipeline/              确定性创作工具和 Forge 工具
schemas/               公开 JSON Schema 合同
examples/              公开原创内容
tests/                 单元、场景、CLI、Web 和打包证据
docs/                  V1 格式/工作流和 V2 架构文档
scripts/               仓库安全和交付辅助工具
```

当前运行时数据流：

```text
JSON 内容 -> load_content_pack() -> ContentPack -> World
玩家命令/动作 -> CommandProcessor 或 PlayerSession -> World -> 结果/视图
World <-> SaveLoadService -> 带版本的本地存档
```

目标 V2 数据流：

```text
创作平面：来源材料 + 决策 -> Blueprint -> Project -> Package
运行时平面：Package + Intent -> Session -> Events + View -> TurnResult
```

修改共享运行时或创作模块前，请先阅读 [CODE_MAP.md](CODE_MAP.md)。

### 公开与私有边界

| 公共仓库 | 所有者控制的外部工作区 |
|---|---|
| 通用引擎与工具、Schema 和测试 | 小说原文和拆分章节 |
| 原创示例和公开安全测试材料 | 私人摘要、设定和来源追踪 |
| 产品、架构和格式文档 | 专有改编和资产 |
| 通用来源追溯和权利合同 | 索引、数据库、存档、日志和报告 |

私人来源目录是只读输入。模型输出、导入包、资产和玩家输入均不受信任；使用前必须校验，
保留来源追溯，并且绝不能推断仓库许可证同时授予外部材料的使用权。

### 创作工具

当前流水线提供保守的小说拆分，以及经过确定性校验的事实候选/审查、设定草稿/注册表、
注册表检查/改编、`NarrativeModel v1` 和 `CampaignSpec v1` 编译器。它们的格式合同位于
`docs/` 和 `schemas/`。

Forge 目前只编排检查和注册表改编阶段。它是一个有用的 V1 工作台，但还不是 V2 创作平面
或游戏包构建器。

### 开发

先阅读 [AGENTS.md](AGENTS.md)，然后阅读 `PRODUCT.md`、`PROJECT_STATE.md`、
`NEXT_TASK.md`，以及当前任务真正相关的代码和文档。完整流程见
[docs/production_workflow.md](docs/production_workflow.md)。

核心验证包括：

```powershell
python -m unittest discover -s tests -v
python -m pytest -q
python -m ruff check .
python -m pyright
python -m compileall -q src pipeline scripts tests
python -m lore2mud validate --content examples/original_demo
python scripts/check_repo_safety.py --history
git fsck --full --no-dangling
git diff --check
```

本地提交并不授权 push、移动 `main` 或发布；实现者不能自行宣布通过独立验收。

## English

Lore2MUD is an **Agent-callable novel-to-text-game engine**. A developer Agent is
the direct tool user; the product owner/creator supplies product decisions, creative
direction, and rights authorization; the player is the final user. Lore2MUD is not
itself an Agent.

The repository is public and contains generic engine/tooling code plus original
examples only. It does not include third-party novels, proprietary characters,
private adaptations, images, audio, or owner-controlled derived artifacts. The MIT
license covers repository-owned material, not imported or generated content.

### Product And Architecture

- [Product definition](PRODUCT.md) - users, modes, inputs/outputs, PLAT-1, metrics,
  non-goals, and rights boundary.
- [Current code map](CODE_MAP.md) - real V1 symbols, flows, module sizes, risks, and
  ownership for future changes.
- [V2 target architecture](docs/v2/architecture.md) - Authoring Plane, deterministic
  Runtime Plane, contracts, compatibility, and capability safety.
- [V2 development model](docs/v2/development_model.md) - product authority, Codex
  roles, model floor, TECH/PRODUCT/SECURITY passes, and Git gates.
- [V2 roadmap](docs/v2/roadmap.md) - V2-0 through V2-5 and PLAT-1.

### What Exists Today: V1

The current public runtime is a local single-player Python text MUD. It loads strict
multi-file JSON content into `ContentPack`, constructs an authoritative `World`, and
exposes play through a text CLI and local Web client. Current capabilities include:

- rooms, exits and item gates; typed item stacks, inventory, equipment, consumables,
  loot, fixed shops, coins, deterministic combat and defeat recovery;
- typed quests, dialogue and atomic effects, narrative state/conditions, and optional
  runtime `campaign.json` scenes, actions, objectives, knowledge, and journal entries;
- save v9 writes with constrained named slots and guarded v7/v8 read compatibility;
- content validation, public original examples, deterministic authoring compilers,
  repository safety checks, Windows packaging, and a local Web player.

`World`, `CommandProcessor`, and Web `PlayerSession` are current V1 types.
`GameBlueprint`, `GameProject`, `GamePackage v2`, `CapabilityDescriptor`,
`GameSession`, `GameIntent`, `GameEvent`, `GameView`, and `TurnResult` are V2 targets
and are not implemented by the V2-0 documentation reset.

The pipeline `CampaignSpec v1` is a deterministic authoring IR. It is **not** a
runtime input and is not interchangeable with a content pack's runtime
`campaign.json`.

### Quick Start

Python 3.11 or newer is required.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Play the original public demo:

```powershell
python -m lore2mud play --content examples/original_demo
```

The legacy form remains supported:

```powershell
python -m lore2mud --content examples/original_demo
```

Validate without starting a game:

```powershell
python -m lore2mud validate --content examples/original_demo
```

Run the local Web player:

```powershell
python -m lore2mud web --content examples/original_demo
```

Use `help` in the CLI for the live command registry. The original demo walkthrough
and content notes are in [examples/original_demo/README.md](examples/original_demo/README.md).

### Repository Layout

```text
src/lore2mud/          V1 runtime, content loading, CLI, and Web
pipeline/              deterministic authoring and Forge tools
schemas/               public JSON Schema contracts
examples/              original public content
tests/                 unit, scenario, CLI, Web, and packaging evidence
docs/                  V1 formats/workflows and V2 architecture documents
scripts/               repository safety and delivery helpers
```

The current runtime flow is:

```text
JSON content -> load_content_pack() -> ContentPack -> World
player command/action -> CommandProcessor or PlayerSession -> World -> result/view
World <-> SaveLoadService -> versioned local save
```

The target V2 flow is:

```text
Authoring Plane: source + decisions -> Blueprint -> Project -> Package
Runtime Plane: Package + Intent -> Session -> Events + View -> TurnResult
```

See [CODE_MAP.md](CODE_MAP.md) before changing shared runtime or authoring modules.

### Public And Private Boundary

| Public repository | Owner-controlled external workspace |
|---|---|
| Generic engine and tooling, schemas and tests | Novel text and split chapters |
| Original examples and public-safe fixtures | Private summaries, canon and traces |
| Product/architecture/format documentation | Proprietary adaptations and assets |
| Generic provenance and rights contracts | Indexes, databases, saves, logs and reports |

Private source directories are read-only inputs. Model output, imported packages,
assets, and player input are untrusted. Validate them before use, preserve provenance,
and never infer that a repository license grants rights to external material.

### Authoring Tools

The current pipeline provides conservative novel splitting and deterministic,
validated compilers for fact candidates/reviews, canon drafts/registries,
registry inspection/adaptation, `NarrativeModel v1`, and `CampaignSpec v1`. Their
format contracts live under `docs/` and `schemas/`.

Forge currently orchestrates only inspection and registry-adaptation stages. It is a
useful V1 workbench, not yet the V2 Authoring Plane or package builder.

### Development

Start with [AGENTS.md](AGENTS.md), then read `PRODUCT.md`, `PROJECT_STATE.md`,
`NEXT_TASK.md`, and only the code/docs relevant to the active task. The exact workflow
is in [docs/production_workflow.md](docs/production_workflow.md).

Core verification includes:

```powershell
python -m unittest discover -s tests -v
python -m pytest -q
python -m ruff check .
python -m pyright
python -m compileall -q src pipeline scripts tests
python -m lore2mud validate --content examples/original_demo
python scripts/check_repo_safety.py --history
git fsck --full --no-dangling
git diff --check
```

Local commits do not authorize push, `main` movement, or release. Implementation
cannot self-declare independent acceptance.
