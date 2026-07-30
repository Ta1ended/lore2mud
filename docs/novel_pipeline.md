# 大型小说资料管线

## 原则

目标不是让 Agent 在上下文中记住整部小说，而是建立可检索、可审查、可追溯
的本地资料层。原文与拆章结果始终是只读证据源，不进入公共仓库。

## 推荐目录

```text
novel/
├─ raw/                    # 原始 TXT，只读
├─ chapters/               # 拆章及 manifest
├─ summaries/
│  ├─ chapters/            # 逐章摘要
│  ├─ arcs/                # 10～30 章阶段摘要
│  └─ volumes/             # 分卷摘要
├─ extractions/
│  └─ chapters/            # 逐章结构化候选
└─ canon/                  # 审核后的事实注册表
```

这些目录已被 `.gitignore` 排除。若需要云端备份，应使用你有权控制且访问范围
明确的私人存储，并单独评估材料权利与服务条款。

## 第一步：拆章

```powershell
python pipeline/split_novel.py D:\PrivateNovel\book.txt novel\chapters --encoding gbk
```

### 支持的编码

| 参数值 | 说明 |
|--------|------|
| `utf-8-sig` | 默认，UTF-8 带 BOM |
| `utf-8` | UTF-8 无 BOM |
| `gbk` | 中文 GBK |
| `gb18030` | GB18030 超集 |

解码使用严格模式；遇到非法字节时立即报错，不会静默替换。

### 章节与卷的识别

- **"第X章"** 行作为章节分割点，每章生成一个 `chapter_NNNNNN.txt` 文件。
- **"第X卷"** 行不创建文件，仅更新后续章节的 `volume_label` 元数据。
- 文件名使用按出现顺序生成的稳定 ID，不使用原始章节号或标题。
- 原始章节号和标题允许重复（如不同卷中的重号章节）。

### 脚本行为

- 以指定编码（默认 `utf-8-sig`）读取源文件，不写回原文；
- 默认识别"第 N 章 标题"格式；
- 生成 `chapter_000001.txt` 等稳定文件名；
- 生成包含完整元数据的 `manifest.json`。

不同来源的标题格式可能是"卷一""Chapter 1"或不含空格。不要为了提高命中
率直接使用过宽正则；应先复制少量样本调整规则，再验证：

- 拆分章节数与目录一致；
- 全部章节按顺序拼接后与解码后的原文一致；
- 没有把正文句子误判为标题；
- 没有重复或空章节。

## manifest 格式 (v2)

```json
{
  "format_version": 2,
  "source_encoding": "gbk",
  "chapter_count": 3,
  "chapters": [
    {
      "chapter_id": "chapter_000001",
      "title": "第一章 雾岭小村",
      "source_chapter_label": "第一章",
      "source_title": "雾岭小村",
      "volume_label": "第一卷 雾岭边站",
      "source_offset": 42,
      "source_line": 12,
      "path": "chapter_000001.txt",
      "character_count": 12345,
      "sha256": "...",
      "previous_id": null,
      "next_id": "chapter_000002"
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `chapter_id` | str | 按出现顺序的稳定 ID，如 `chapter_000001` |
| `title` | str | 完整标题行，如 `"第一章 雾岭小村"` |
| `source_chapter_label` | str | 仅章节号，如 `"第一章"` |
| `source_title` | str | 仅标题文字，如 `"雾岭小村"`（可能为空） |
| `volume_label` \| null | str | 最近的卷标题，如 `"第一卷 雾岭边站"` |
| `source_offset` | int | 解码后文本中的字符偏移（标题行起始位置） |
| `source_line` | int | 解码后文本中的行号（从 1 开始） |
| `path` | str | 输出文件名 |
| `character_count` | int | 章节字符数 |
| `sha256` | str | 章节文本 SHA-256 |
| `previous_id` \| null | str | 前一章 ID |
| `next_id` \| null | str | 后一章 ID |

## 第二步：逐章提取

每章建议同时输出：

- 人类可读摘要；
- 人物、地点、组织、技能、物品和事件候选；
- 人物状态和关系变化；
- 未解决伏笔；
- `source_chapters`；
- `uncertain` 或 `inference` 标记。

模型不得自行补全原文没有的事实。提取结果仍是候选，不直接成为 canon。

逐章提取的候选格式规范见 [fact_candidate_format.md](fact_candidate_format.md)。
manifest v2 校验规范见 [chapter_manifest_format.md](chapter_manifest_format.md)。
审核决定格式规范见 [fact_review_format.md](fact_review_format.md)。

### 审核后提升为单章 canon 草稿

通过审核的 accepted claims 可经人工 PromotionPlan 确定性生成为 canon 草稿。
格式规范见 [canon_draft_format.md](canon_draft_format.md)。

### L2W-2：改编为 micro vignette

CanonDraft 可通过显式 AdaptationPlan 编译为可玩的微型内容包（一房间、一角色、
一物品、一叙事对话、一自动接取任务）。格式规范见
[adaptation_plan_format.md](adaptation_plan_format.md)。

## 第三步：实体归并

中央注册表负责稳定 ID。子 Agent 可以并行提取候选，但不能各自永久决定实体
ID。别名、称号和省略主语可能产生重复实体，必须通过来源章节审核。

遇到冲突时保留：

- 每个候选说法；
- 对应来源章节；
- 冲突类型；
- 建议解释；
- 审核状态。

禁止静默覆盖较早事实。

## 第四步：分层汇总

```text
原文章节
  → 逐章摘要
  → 10～30 章阶段摘要
  → 分卷摘要
  → 全书世界资料
```

每级摘要都保留来源范围、状态变化和未解决冲突。需要精确设定时，检索摘要后
回到原文章节核实。

## 第五步：生成游戏草稿

只选择一个封闭篇章生成首个区域。所有房间、怪物、物品和任务先写入私人
内容包，经过格式与引用校验后才试玩。原作事实与游戏数值分别保存：

```text
novel/canon/skills.json        # 原作实际说明
private_content/skills.json    # 冷却、消耗、伤害等游戏设计
```

游戏实体通过 `canon_ref` 指向事实实体。数值平衡、关卡入口和掉落率不得写回
canon。

## 安全检查

提交前运行：

```powershell
python scripts/check_repo_safety.py
```

发布、历史重写或 CI 使用：

```powershell
python scripts/check_repo_safety.py --history
```

脚本检查 Git 已跟踪文件（包括以 `git add -f` 强制加入的忽略文件）和未忽略的
候选文件；`--history` 还检查所有可达 Git 历史树和 blob。它仅检测有限的常见私钥、
GitHub/AWS/Slack 凭据模式，不能替代密钥管理、权利审核或提交前人工查看
`git status`。`.gitignore` 是第一道边界，安全脚本是第二道边界。
