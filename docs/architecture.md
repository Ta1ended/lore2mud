# 架构说明

## 目标

lore2mud 首版是本地单人、命令行、内存运行的最小 MUD。架构首先保证游戏
规则可测试、内容可替换、引用可验证；多人网络、数据库和 LLM 不是首版前提。

## 模块职责

### `engine`

`CommandProcessor` 把文本转换为有限的玩家意图，并将动作交给 `World`。
`World` 持有当前房间、玩家、物品和怪物，是运行时状态的唯一权威。命令层
不直接更改生命、经验或背包。

### `combat`

处理单回合确定性战斗。伤害公式为 `max(1, attack - defense)`，玩家先攻击，
存活的怪物才反击。这里不读取内容文件，也不生成叙事文本。

### `progression`

处理经验和升级。升级阈值为 `当前等级 × 10`，支持一次奖励连续升级。具体
成长数值是首版游戏规则，未来应通过版本化规则调整。

### `inventory`

保存稳定物品 ID，不复制物品显示名称。背包容量由内容包的玩家默认值定义。

### `content`

把 JSON 文件转换为不可变内容定义，并检查：

- 必填字段与基本类型；
- 稳定 ID 格式和重复 ID；
- 起始房间、出口目标、出口门禁物品、物品、怪物、角色和对话引用；
- `pack.json`、`rooms.json`、`items.json`、`monsters.json`、`characters.json`、
  `quests.json` 和 `dialogues.json` 七个必需内容文件；
- 同一实体的重复放置；
- 怪物 `room_id` 与房间 `monster_ids` 一致性；
- 对话节点/选项的交叉引用与唯一性；
- 可选 `canon_ref` 的来源章节。

仓库中的 JSON Schema 是格式契约和编辑器提示；运行时使用标准库实现等价的
关键校验，因此不依赖第三方 Schema 库。

## 状态生命周期

```text
内容文件（不可变）
  → 加载与校验
  → ContentPack（不可变定义）
  → World.from_content_pack
  → World（本次运行的可变状态）
```

玩家发出的只是意图。以拾取为例：

```text
take item_spark_lantern
  → 解析指令
  → 确认物品在当前房间
  → 确认背包有容量
  → 从房间移除稳定 ID
  → 向背包加入同一稳定 ID
  → 渲染结果
```

任何失败都发生在修改之前，避免半完成状态。

### 门禁出口

`ExitDefinition` 是不可变的内容契约：每个出口都有 `target_room_id`，并可带有
`required_item_id`。加载器把旧的字符串出口和对象出口统一规范化；`World.move()`
在修改房间、触发任务或清理活动对话前检查背包。缺少所需物品时，错误同时显示物品名
和稳定 ID，且不改变任何运行时状态；通过时物品不会被消耗。出口定义属于内容包，
不写入 save v5 的可变状态。

`CommandProcessor.look()` 只读取当前房间的出口定义、物品定义和背包 ID，并显示门禁
出口所需物品及“未持有”或“已持有”状态；它不复刻、放宽或执行门禁规则。门禁的唯一
规则权威仍是 `World.move()`，因此这只是展示行为，不是内容或存档契约变更。

### 可见物品查看

`World.inspect_item()` 只从当前房间物品和玩家背包的并集解析稳定 ID 或唯一显示名称，
并返回带稳定 ID、名称和描述的 `InspectItemOutcome`。其他房间的物品和尚未获得的对话
奖励不在可见范围；同名可见物品要求使用稳定 ID。`CommandProcessor.inspect` 只渲染该
结果，不直接读取或修改状态。查看不会改变房间、背包、装备、任务、活动对话或怪物，且
不新增内容包或 save v5 契约。

## 原作事实与游戏规则

两层数据不得合并：

```text
私有 canon 层
  角色、地点、事件、关系、来源章节

游戏内容层
  房间出口、生命、攻击、防御、经验奖励、任务条件
```

游戏实体可通过 `canon_ref.entity_id` 引用私有事实实体，并用
`source_chapters` 提供追溯证据。`adaptation_notes` 解释游戏化选择。运行引擎
只依赖游戏内容层，因此公共仓库和原创内容包不需要任何小说资料。

## 对话系统

对话由内容定义和运行时状态两层构成：

```text
内容定义（不可变）
  DialogueDefinition（对话树）
  → DialogueNode（节点 + 台词）
  → DialogueOption（选项 + next_node_id + 可选 grant_item_id）

运行时状态（World 持有）
  characters: dict[str, Character]          # 角色位置由 room_id 决定
  dialogue_defs: dict[str, DialogueDefinition]  # 对话树
  active_dialogue: DialogueState | None     # 当前对话位置
```

对话状态所有权在 `World`。`CommandProcessor` 只负责解析裸整数 / bye / talk
指令，将意图转给 World，再将 `TalkOutcome` 渲染为文本。

### 终端节点

终端节点（`options` 为空元组的节点）在到达时自动结束对话，无需玩家输入
bye。结束选项（`next_node_id=null`）则立即结束对话。

### 状态不变性

对话操作不修改玩家 HP、经验、装备、任务状态或房间布局。带 `grant_item_id` 的
选项是唯一例外：`World.select_option()` 在变更对话状态前检查背包容量和重复拥有，
然后原子加入一个经内容校验的普通物品；失败时背包与 `active_dialogue` 均不变。

### 存档

`active_dialogue` 是 save v5 的必填字段。加载时严格验证：
- 顶层、`content_pack`、`player`、每个房间和每个怪物对象的键集合必须精确匹配；
- 对话 ID 和节点 ID 必须存在
- 指向的节点不能是终端节点
- 角色的 `room_id` 必须与玩家房间一致

任何不一致都以 `SaveLoadError` 拒绝，不静默清除。

`SaveLoadService.save()` 与 `.load()` 不带参数时仍使用兼容的 `default.json`。可选槽位名
由 `save <槽位>` / `load <槽位>` 传入，并只映射到保存目录内的 `<槽位>.json`：名称必须是
1–32 位小写 ASCII 字母、数字、`-` 或 `_`，以字母或数字开头，且拒绝路径片段、扩展名和
Windows 保留设备名。路径验证发生在序列化、读取或替换世界之前；槽位只选择文件，不改变
save v5 的 JSON 契约。

`SaveLoadService.save()` 在服务边界把文件系统 `OSError` 转换为带原始异常链的
`SaveLoadError`，因此 `CommandProcessor` 能将写入失败渲染为正常的“存档失败”文本，
而不会让 I/O 异常逃出游戏循环。`_atomic_write()` 的原子写入和临时文件清理职责不变；
非 I/O 编程错误不会被重新标记为存档 I/O 错误。

## 扩展原则

- 存档应序列化运行时状态，而不是覆盖内容包。
- 数据库访问应集中到 repository 接口，不进入命令处理器。
- 随机、时间和外部模型都应通过可替换接口注入。
- LLM 只能提出候选指令或候选内容，不能直接修改 `World`。
- 内容格式变更必须带版本、迁移说明、Schema 和引用测试。
