# Lore2MUD

**把叙事世界观变成可运行的文字游戏引擎**

Lore2MUD 是一个本地优先、内容包驱动的 Python 文字 MUD（文字冒险）引擎。  
它把「通用游戏规则」和「具体故事内容」彻底分离，让你可以用结构化 JSON 内容包，快速构建包含房间、物品、装备、战斗、任务、对话、商店的单人文字世界。

当前版本已经自带一个完全原创的八房间演示世界（「微光边站」），支持完整的冒险闭环。运行时**零第三方依赖**，只用 Python 标准库。

> 本仓库只包含通用引擎、工具与原创示例。  
> **不包含**任何第三方小说、角色、世界观、图片或音频。  
> MIT 许可证仅覆盖仓库自有代码与原创演示内容。你自行导入或生成的材料，权利需自行确认。

---

## 它适合做什么？

- 想快速做一个可玩的文字冒险 / 轻量 MUD 原型
- 想把自己的原创故事（或有授权的小说）变成可交互的游戏
- 需要一个**确定性、可测试、可验证**的文字游戏运行时（方便 AI Agent 或工具链调用）
- 希望内容与引擎解耦，方便换皮、扩展、做多个独立故事包

它**不是**：
- 自动创作小说的 AI
- 多人在线 MUD 服务器
- 可以直接塞进任意小说就自动出完整游戏的黑盒

---

## 当前能力（V1）

| 系统           | 说明 |
|----------------|------|
| 房间与探索     | 多房间地图、出口、物品门禁 |
| 物品与背包     | 强类型物品堆、数量限制、拾取/丢弃 |
| 装备           | 手部 / 身体装备槽，提供攻击/防御加成 |
| 消耗品         | 可使用恢复道具 |
| 战斗           | 确定性回合制战斗 + 战败恢复 |
| 任务           | 收集、到达、击败等多种任务类型，支持分段接取 |
| 对话           | 强类型对话树 + 原子效果（给物品、设标记、接任务等） |
| 商店与金币     | 固定商店买卖 |
| 存档           | 版本化存档（当前写 v9，兼容读取旧版） |
| 内容校验       | `validate` 命令可在不启动游戏的情况下检查内容包 |
| 本地 Web 客户端| 浏览器也能玩 |
| 创作流水线     | 小说拆分、事实候选、设定注册表、叙事模型编译等工具（`pipeline/`） |

所有游戏规则都由 `World` 作为唯一权威状态持有，命令层只负责解析与展示，保证行为可测试、可复现。

---

## 快速开始

**要求**：Python 3.11 或更高版本。

```bash
# 1. 克隆并进入项目
git clone https://github.com/Ta1ended/lore2mud.git
cd lore2mud

# 2. 创建虚拟环境并安装（可编辑模式）
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

python -m pip install -e .
```

### 立刻开玩原创演示世界「微光边站」

```bash
python -m lore2mud play --content examples/original_demo
```

进入游戏后输入 `help` 查看所有可用命令。  
推荐按 [examples/original_demo/README.md](examples/original_demo/README.md) 里的试玩流程走一遍，大约 15–25 分钟能完整体验移动、装备、战斗、任务、对话和商店。

其他常用命令：

```bash
# 只校验内容包（不启动游戏）
python -m lore2mud validate --content examples/original_demo

# 启动本地 Web 玩家端
python -m lore2mud web --content examples/original_demo

# 旧版启动方式（仍然支持）
python -m lore2mud --content examples/original_demo
```

---

## 项目结构

```text
src/lore2mud/          # 核心运行时（World、命令处理、战斗、存档、CLI、Web）
pipeline/              # 确定性创作工具（拆分、事实、注册表、编译器、Forge）
schemas/               # 公开 JSON Schema 合同
examples/              # 公开原创内容包（目前主要是 original_demo）
tests/                 # 单元测试、场景测试、CLI/Web/打包证据
docs/                  # 格式说明、工作流、V2 架构文档
scripts/               # 仓库安全检查与辅助脚本
```

**数据流（当前 V1）**：

```text
JSON 内容包  →  load_content_pack()  →  ContentPack  →  World
玩家命令      →  CommandProcessor / PlayerSession  →  World  →  结果
World        ↔  SaveLoadService  →  版本化本地存档
```

未来 V2 会更清晰地拆成「创作平面」和「运行时平面」，并引入更正式的 `GameBlueprint` → `GamePackage` 流程，同时保持对现有内容包与存档的兼容。

---

## 自己做内容包

内容以**多文件 JSON 内容包**的形式组织，引擎会严格校验引用关系与数据结构。

你可以参考 `examples/original_demo/` 的目录结构和字段定义，或者查看 `docs/` 与 `schemas/` 下的格式合同。

创作相关工具集中在 `pipeline/`，包括：
- 小说章节拆分
- 事实候选提取与审查
- 设定草稿 / 注册表
- NarrativeModel 与 CampaignSpec 编译器

这些工具目前以「确定性 + 可验证」为设计目标，方便后续接入 Agent 工作流，同时保持人类可审查。

---

## 开发与测试

```bash
# 安装开发依赖
python -m pip install -e ".[test,quality]"

# 运行测试
python -m unittest discover -s tests -v
python -m pytest -q

# 代码质量
python -m ruff check .
python -m pyright
python -m compileall -q src pipeline scripts tests

# 内容与安全检查
python -m lore2mud validate --content examples/original_demo
python scripts/check_repo_safety.py --history
```

更详细的开发约定、任务边界与架构说明见：
- [PRODUCT.md](PRODUCT.md) — 产品定义与边界
- [CODE_MAP.md](CODE_MAP.md) — 当前代码地图
- [docs/v2/](docs/v2/) — V2 目标架构与路线图
- [AGENTS.md](AGENTS.md) — 给开发 Agent 的指引（如果你也在用 Agent 协作）

---

## 公开与私有边界（重要）

| 公共仓库包含                     | 不包含（应放在所有者控制的外部工作区）     |
|----------------------------------|--------------------------------------------|
| 通用引擎与工具代码               | 第三方小说原文、拆分章节                   |
| 公开 Schema 与测试               | 私人摘要、设定、来源追踪                   |
| 原创示例内容包                   | 专有改编、图片、音频、资产                 |
| 产品 / 架构 / 格式文档           | 本地存档、日志、报告、索引数据库           |

私人材料永远是只读输入，绝不应提交到本仓库。模型输出和导入内容在使用前必须经过校验，并保留来源追溯。

---

## 许可证

MIT License。详见 [LICENSE](LICENSE)。

MIT 仅覆盖本仓库中的自有代码与原创演示内容。  
你导入、生成或改编的外部材料不在本许可证授权范围内。

---

## 状态

当前处于积极开发中（Alpha）。  
V1 运行时已可用，并持续完善内容工具与 V2 架构准备。欢迎试用、反馈、提 Issue 或贡献原创内容包。

---

**玩得开心。如果「微光边站」让你感觉还行，那就对了——这正是这个引擎想要交付的东西。**
