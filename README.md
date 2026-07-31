# lore2mud

`lore2mud` 是一个面向本地单人文字 MUD 的现代 Python 项目基底。它把
通用游戏引擎、小说资料处理工具、原作事实和具体游戏数值分成不同层。Codex 全程使用
GPT-5.6-sol 完成方案、实现、测试、交接和本地提交；需要独立验收时，由新的 Codex 任务
或干净上下文只读复核真实提交。Hermes 仅保留历史贡献归属，不再承担新任务。

当前版本提供一个完全原创的八房间演示世界，包含移动、拾取、背包、确定性
战斗、装备、消耗品、任务和对话系统。运行时只使用 Python 标准库。

> 本仓库不附带任何第三方小说、角色、世界观、图片、音频或改编内容。
> MIT 许可证仅覆盖仓库中的自有代码与原创演示内容。用户自行导入的材料及
> 其生成内容不属于本项目的授权范围，使用者应自行确认相应权利。

## 快速开始

需要 Python 3.11 或更高版本。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

### 启动游戏

旧版命令（仍受支持）：

```powershell
lore2mud --content examples/original_demo
python -m lore2mud --content examples/original_demo
```

显式 `play` 子命令（推荐）：

```powershell
lore2mud play --content examples/original_demo
python -m lore2mud play --content examples/original_demo
```

### 校验内容包

不启动游戏，只检查内容包结构和引用：

```powershell
lore2mud validate --content examples/original_demo
python -m lore2mud validate --content examples/original_demo
```

成功输出 `[OK] 内容包校验通过` 并退出 0；校验失败输出所有问题并退出 1。

进入游戏后可执行：

```text
look
examine
examine item item_spark_lantern
inspect item_spark_lantern
take item_spark_lantern
take item_linglu_pill 2
inventory
save lantern_run
use item_linglu_pill
equip item_crystal_blade
unequip hand
quests
go east
go east
attack monster_ash_mite
attack monster_ash_mite
quests
status
load lantern_run
help
help examine
quit
```

## 当前能力

- `look`：查看当前房间、出口、物品、怪物和角色；门禁出口会显示所需物品的名称、稳定 ID 与当前是否持有，普通出口保持只显示方向。
- `examine` / `examine room|here`：只读查看当前房间摘要；`examine <ID或名称>` 可在当前
  房间物品、背包物品、当前房间怪物和角色之间解析目标。跨类型同名或重复稳定 ID 时，使用
  `examine item|monster|character <ID或名称>` 显式限定；同一类型内重名时使用稳定 ID。
  其他房间及尚未取得的奖励不可见。
- `inspect <ID或名称>`：保留兼容的物品专用查看，只解析当前房间或背包物品，并保持原有
  `InspectItemOutcome` 与输出格式。
- `go <方向>`：沿内容包声明的出口移动；门禁出口要求背包持有指定物品，不消耗该物品。
- `take <ID或名称> [数量]`：拾取房间内物品（数量可选，默认 1）。
- `drop <ID或名称> [数量]`：将背包中未装备的物品放入当前房间（数量可选，默认 1）。
- `inventory`：查看背包。
- `use <ID或名称> [数量]`：使用背包内的消耗品（数量可选，默认 1）。
- typed stacks：不可变内容 `ItemStackDefinition` 与运行时 `ItemStack` 统一房间、背包、
  战利品和对话奖励；容量按栈位计算，`stack_limit` 限制每栈数量。
- 当前原创内容包为 0.8.0；本地存档为 v7，使用 `inventory_stacks`、`item_stacks`、
  `player.coins` 与顶层 `flags`，明确拒绝 v6 存档；旧 0.7.0 内容包存档也会按内容包版本拒绝。
- `equip <ID或名称>`：装备 hand 或 body 槽物品。
- `unequip [hand|body]`：卸下指定槽位；省略时默认为 hand。
- `save [槽位]` / `load [槽位]`：保存或读取默认 `default` 槽位，或使用一个安全的命名槽位。
  槽位名为 1–32 位小写字母、数字、`-` 或 `_`，必须以小写字母或数字开头，且不接受路径、
  扩展名或 Windows 保留设备名。
- `attack <ID或名称>`：进行一个确定性战斗回合。
- `talk <ID或名称>`：与角色对话，显示台词和编号选项。
- `<数字>`：选择对话选项（对话中可用）。
- `bye`：结束当前对话（对话中可用）。
- `help [command]`：无参数列出所有真实路由；指定命令或别名时显示语法、参数、上下文限制
  和死亡限制。帮助、路由和死亡允许信息来自同一个命令注册表。
- 对话选项必须声明有序 `effects`；首批强类型效果是 `grant_item`、`grant_experience`、
  `accept_quest` 与 `set_flag`。World 预检整组效果后原子执行，并按效果顺序渲染结果。
- `shop`：只读查看当前房间的固定无限目录；`buy <ID或名称> [数量]` 与
  `sell <ID或名称> [数量]` 按内容包的固定价格交易，不维护可变库存。
- `status`：查看生命、等级、经验、攻击、防御、金币和按稳定 ID 排序的 flags。
- `quests`：查看已接取任务及进度。任务定义是 `monster_defeated`、`reach_room`、
  `collect_item` 三分支强类型契约；收集任务以背包数量达到 `required_quantity` 为条件。
- JSON 内容包结构、类型、稳定 ID 与跨文件引用校验。
- `validate` 子命令：不启动游戏即可校验内容包，报告所有问题。
- 原创确定性任务闭环：自动接取、三类条件推进、按任务 ID 稳定结算、一次性经验奖励和
  存档持久化；移动 API 保持兼容，CLI 通过加性结果显示任务完成。
- 保守的中文小说拆章与 manifest 生成工具。
- Git 候选与可达历史安全检查，阻止私有资料、电子书、常见凭据、数据库、索引、
  存档、日志和异常大文件进入仓库。

## 项目结构

```text
lore2mud/
├─ src/lore2mud/
│  ├─ engine/          # 命令编排、世界状态、玩家、房间
│  ├─ combat/          # 确定性战斗规则
│  ├─ progression/     # 经验与升级
│  ├─ inventory/       # 物品与背包
│  └─ content/         # JSON 内容包模型、加载与引用校验
├─ pipeline/           # 本地小说拆章与 manifest 工具
├─ schemas/            # 内容格式的 JSON Schema 文档
├─ examples/
│  └─ original_demo/   # 完全原创的可玩演示内容
├─ scripts/            # 仓库安全检查
├─ tests/              # 单元测试与场景测试
├─ docs/               # 架构、管线、格式和 Agent 工作流
└─ .github/            # CI、Issue 与 PR 基础配置
```

核心数据流：

```text
玩家指令
  → CommandProcessor
  → World 权威状态
  → combat / progression / inventory 领域规则
  → 结果文本

JSON 内容包
  → Schema/类型校验
  → 跨文件引用校验
  → 不可变定义
  → 可变运行时世界
```

更完整的设计见 [架构说明](docs/architecture.md)。

## 公开内容与私有内容边界

建议把公共仓库与私人小说资料严格分开：

| 可以公开提交 | 必须留在本地 |
|---|---|
| 通用引擎与工具 | 小说原文与电子书 |
| JSON Schema | 拆分后的章节 |
| 原创演示内容 | 章节摘要与事实提取 |
| 不含专有名称的测试 | 使用原作名称的改编内容包 |
| Agent 工作规范 | 本地索引、数据库、模型和存档 |

推荐的本地目录会被 `.gitignore` 忽略：

```text
novel/
├─ raw/          # 只读原文
├─ chapters/     # 拆章结果
├─ summaries/    # 分层摘要
├─ extractions/  # 逐章实体候选
└─ canon/        # 经审核的原作事实

private_content/ # 私人游戏改编内容
```

游戏内容中的 `canon_ref` 只是指向私有事实层的可选引用：

```json
{
  "id": "item_example",
  "name": "显示名称",
  "description": "游戏内描述",
  "canon_ref": {
    "entity_id": "canon_item_example",
    "source_chapters": ["chapter_000123"]
  },
  "adaptation_notes": "伤害和稀有度属于游戏改编，不是原作事实。"
}
```

引擎不需要读取小说原文；没有 `canon_ref` 的原创内容包同样可以运行。

## 本地小说处理入口

默认拆章器针对“第一章 标题”或“第一章”这类保守格式：

```powershell
python pipeline/split_novel.py `
  D:\PrivateNovel\book.txt `
  novel\chapters
```

它不会修改源文件，并会生成 `manifest.json`。不同小说的标题格式差异很大，
首次运行后必须检查章节数、异常标题和前后边界。详细流程见
[小说资料管线](docs/novel_pipeline.md)。

审核后的单章 canon 草稿可通过显式 RegistryPlan 组装为多章 CanonRegistry；该步骤
保留每条 claim 的复合来源，不自动识别同名实体或裁决冲突。格式见
[Canon Registry Format v1](docs/canon_registry_format.md)。

经过验证的 CanonRegistry 可通过显式 RegistryAdaptationPlan 编译为一个公开安全的
单房间 micro content pack；游戏文本和数值只来自人工计划，registry claims 仅用于
来源追溯。该流程不裁决冲突或读取私有资料：

```powershell
python -m pipeline.registry_adaptation `
  --canon-registry tests/fixtures/registry_adaptation/canon_registry.json `
  --adaptation-plan tests/fixtures/registry_adaptation/valid_plan.json `
  --output-dir C:\Temp\registry_micro_demo
```

格式与完整验证规则见
[Registry Adaptation Format v1](docs/registry_adaptation_format.md)。

## 生产工作流

Codex 全程使用 GPT-5.6-sol 完成方案、实现、测试、交接和本地提交；项目负责人
批准切片范围和 push，不再在不同 Agent 之间人工转交 prompt：

1. Codex 先阅读 `AGENTS.md`、交接文件、相关代码和测试，并报告数据流、范围、
   风险和验证方案。
2. 项目负责人明确授权后，Codex 只实现当前纵向切片。
3. Codex 运行完整测试、`python scripts/check_repo_safety.py --history` 和对应 CLI
   冒烟，再同步格式文档与交接文件并创建本地提交。
4. 需要独立验收时，由新的 Codex 任务或干净上下文使用 GPT-5.6-sol 只读核对真实
   提交并给出 GO/REVISE。
5. 本地提交不会自动 push；发布前重新核实 HEAD、`origin/main` 和 ahead/behind，
   并取得项目负责人明确授权。

可直接复制的任务模板与检查点见
[生产工作流](docs/production_workflow.md)。

## 开发与验证

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
python scripts/check_repo_safety.py --history
```

任何内容格式变更都应同时更新：

- `src/lore2mud/content/`
- `schemas/`
- `examples/original_demo/`
- `tests/`
- `docs/content_pack_format.md`

## 路线图

1. 存档与读取：加入版本化存档格式和原子写入。 ✅
2. 物品使用与装备：继续保持确定性规则和场景测试。
3. 内容包命令：提供独立的 `validate` 子命令和更清晰的错误定位。 ✅
4. 小说事实层：定义候选提取、别名归并和冲突审核格式。
5. 任务系统：先实现一个原创的确定性任务闭环。 ✅
6. 可选检索：在核心流程稳定后，再接入本地全文或语义检索。

## 许可证

项目中的自有代码和原创演示内容使用 [MIT License](LICENSE)。许可证不扩展到
用户自行导入的小说、第三方资料、私人内容包或其衍生内容。
