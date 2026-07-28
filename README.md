# lore2mud

`lore2mud` 是一个面向本地单人文字 MUD 的现代 Python 项目基底。它把
通用游戏引擎、小说资料处理工具、原作事实和具体游戏数值分成不同层，让 GPT
可以让 GPT-5.6-sol 担任设计与审查顾问，并由 Codex（GPT-5.6-terra）每次实现
一个可测试的纵向功能。

当前版本提供一个完全原创的三房间演示世界，包含移动、拾取、背包、确定性
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
inspect item_spark_lantern
take item_spark_lantern
inventory
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
help
quit
```

## 当前能力

- `look`：查看当前房间、出口、物品、怪物和角色；门禁出口会显示所需物品的名称、稳定 ID 与当前是否持有，普通出口保持只显示方向。
- `inspect <ID或名称>`：只读查看当前房间或背包中物品的稳定 ID 与描述；不能查看其他房间或尚未获得的奖励物品。
- `go <方向>`：沿内容包声明的出口移动；门禁出口要求背包持有指定物品，不消耗该物品。
- `take <ID或名称>`：拾取房间内物品。
- `inventory`：查看背包。
- `use <ID或名称>`：使用背包内的消耗品。
- `equip <ID或名称>`：装备 hand 或 body 槽物品。
- `unequip [hand|body]`：卸下指定槽位；省略时默认为 hand。
- `attack <ID或名称>`：进行一个确定性战斗回合。
- `talk <ID或名称>`：与角色对话，显示台词和编号选项。
- `<数字>`：选择对话选项（对话中可用）。
- `bye`：结束当前对话（对话中可用）。
- 对话选项可一次性奖励一个未放置的原创普通物品，并在文本中明确显示。
- `status`：查看生命、等级、经验、攻击和防御。
- `quests`：查看已接取任务及进度。
- JSON 内容包结构、类型、稳定 ID 与跨文件引用校验。
- `validate` 子命令：不启动游戏即可校验内容包，报告所有问题。
- 原创确定性任务闭环：自动接取、条件推进、经验奖励、存档持久化。
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

## 生产工作流

2026-07-28 的最新已验证同步远端检查点为 `6c13fca`，当时 `main` 与 `origin/main`
同步；公共历史清理祖先为 `96de7b2`。后续本地提交不会自动推送，执行任何发布或
历史操作前必须重新检查实时远端状态。建议让 GPT-5.6-sol 负责范围、
架构与验收，让 Codex（GPT-5.6-terra）在仓库中执行单个纵向任务：

1. 顾问根据当前状态定义一个可验证目标、数据契约和限制。
2. 执行者先阅读 `AGENTS.md`、交接文件、相关代码和测试，并报告数据流、范围、
   风险和测试方案。
3. 执行者只实现当前纵向切片，同步内容格式、文档和四个交接文件。
4. 执行者运行完整测试与 `python scripts/check_repo_safety.py --history`。
5. 顾问按测试、差异和试玩证据验收，再决定下一项任务。

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
