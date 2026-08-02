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

内容层用不可变 `ItemStackDefinition(item_id, quantity)` 描述物品数量；运行时房间和
背包用可变 `ItemStack(item_id, quantity)` 保存稳定 ID 与正整数数量，不复制显示名称。
`ItemDefinition.stack_limit` 限制每栈数量；背包容量按占用栈位而非物品单位数计算。

### `content`

把 JSON 文件转换为不可变内容定义，并检查：

- 必填字段与基本类型；
- 稳定 ID 格式和重复 ID；
- 物品 `stack_limit`、所有 `ItemStack` 的正整数数量、栈上限、装备单件约束与
  房间/背包/战利品/对话奖励之间的放置规则；
- 起始房间、出口目标、出口门禁物品、物品、怪物、角色和对话引用；
- `QuestDefinition` 的三分支 tagged union：`monster_defeated.target_monster_id`、
  `reach_room.target_room_id` 或 `collect_item.target_item_id` 与
  `required_quantity`；分支目标字段互斥，收集数量必须在 1 和物品 `stack_limit` 之间；
- `pack.json`、`rooms.json`、`items.json`、`monsters.json`、`characters.json`、
  `quests.json`、`dialogues.json` 和 `shops.json` 八个必需内容文件，以及可选的
  `narrative_state.json` 和 `campaign.json`；
- 同一实体的重复放置；
- 怪物 `room_id` 与房间 `monster_ids` 一致性；
- 对话节点/选项的交叉引用与唯一性；
- 可选 `canon_ref` 的来源章节。

仓库中的 JSON Schema 是格式契约和编辑器提示；运行时使用标准库实现等价的
关键校验，因此不依赖第三方 Schema 库。

### `narrative`

`narrative` 提供内容可声明、运行时可验证的通用叙事状态，而不执行用户提供的脚本。
可选 `narrative_state.json` 的 v1 定义支持 `bool`、范围受限 `int` 与枚举 `enum`；
`World.narrative_state` 保存与定义精确同键、同类型的可变值。没有该文件的内容包保持
空状态集合。

条件是冻结的受限 AST：`state_equals`、`state_compare`、`has_item`、`at_location`、
`quest_status`、`all`、`any` 和 `not`。加载器在引用解析后检查状态类型、物品/房间/任务
引用、最大深度与节点数；求值器只读取由 `World.condition_context()` 生成的只读快照。
不会使用 `eval`、任意脚本或外部模型。

可选 `campaign.json` v1 在同一条件 AST 上增加动态地点、出口、角色和对话文本投影，
以及场景、交互对象、动作、目标、玩家知识和日志定义。它不包含可执行脚本；加载器严格检查
稳定 ID、场景/阶段所有权、动作唯一所有者、目标依赖 DAG、对称互斥和所有效果引用。

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
take item_spark_lantern [数量]
  → 解析指令
  → 解析当前房间的 ItemStack 与正整数数量
  → 在写入前检查 stack_limit、可合并栈位或可用容量
  → 原子减少来源栈（清空时移除）
  → 原子合并到背包目标栈或创建新栈
  → 渲染结果
```

可预见的输入、容量和引用失败都发生在修改之前；动作后触发的任务结算若失败，则由
`World` 的局部事务回滚，避免半完成状态。

### Campaign 运行时

`World` 从不可变 `CampaignDefinition` 初始化四类可变状态：角色的位置/出现/启用/失能状态、
`SceneState`、`ObjectiveState` 和 `KnowledgeState`。动态描述、出口、角色、活动场景、交互对象、
动作和日志均由 World 读取同一个条件快照后投影；CLI 与 Web 只消费这些公开方法。

```text
campaign.json + narrative_state.json
  -> 严格加载与跨文件引用校验
  -> World.available_* 权威投影
  -> 玩家提交稳定 action_id
  -> 重新验证当前投影
  -> deepcopy(World) 完整效果预检
  -> 扩展事务内按序提交或整体回滚
```

交互对象统一表示 actor、location、object、ritual 和 inner 上下文；场景阶段决定场景型对象的
可用集合。对话不被转换成无类型 action：它继续使用既有 `DialogueState`、有序选项和强类型
effects，但角色可见性、动态节点文本与可用选项同样由 World 投影，因此客户端没有第二套规则。

目标状态为 `inactive|active|in_progress|completed|failed`。激活会检查已完成依赖和对称互斥，
并锁定尚未选择的互斥目标。知识状态为
`unknown|heard|suspected|confirmed|retracted|corrected`；玩家日志只包含非 unknown 的当前文本，
不会暴露客观 canon 定义。

### 任务系统

任务内容是不可变的三分支 `QuestDefinition` tagged union；运行时的
`World.quest_defs` 保存定义，`World.quest_states` 是唯一的可变状态权威。某个
`QuestState` 的存在表示已经接取，`completed=True` 是“奖励已经成功提交”的一次性事实，
而不是可由背包、房间或怪物状态反推的缓存。

```text
进入触发房间 / World.from_content_pack
  → 按任务 ID 接取尚未接取的定义
  → 对已接取且未完成的定义按任务 ID 检查条件
  → 发放经验、标记 completed、生成 QuestOutcome

move_with_outcome / take / attack / select_option(effects) / buy
  → 主动作的全部预检
  → 局部内存事务：主动作 + 任务结算
  → quest_outcomes + level_gains（任务 ID 字典序）
```

条件分别是目标怪物已被击败、玩家当前房间匹配目标房间，以及背包中的目标
`ItemStack.quantity >= required_quantity`。同一次动作可结算多个不同 kind 的任务，
结果、经验和升级信息都按 quest ID 字典序稳定排列。任何奖励或结算异常都会回滚该次
主动作的房间、怪物、玩家、背包、任务、装备和活动对话状态。

`World.move()` 保持历史返回类型 `Room`；需要任务结果的命令层调用加性的
`World.move_with_outcome()`。`TakeOutcome`、`AttackOutcome` 和带物品奖励的
`TalkOutcome` 同样携带 `quest_outcomes` 与对应 `level_gains`。`drop` 与 `use` 不会
重新检查或撤销已完成任务。

### 门禁出口

`ExitDefinition` 是不可变的内容契约：每个出口都有 `target_room_id`，并可带有
`required_item_id`。加载器把旧的字符串出口和对象出口统一规范化；`World.move()`
在修改房间、触发任务或清理活动对话前检查背包。缺少所需物品时，错误同时显示物品名
和稳定 ID，且不改变任何运行时状态；通过时物品不会被消耗。出口定义属于内容包，
不写入存档中的可变状态。

`CommandProcessor.look()` 只读取当前房间的出口定义、物品定义和背包 ID，并显示门禁
出口所需物品及“未持有”或“已持有”状态；它不复刻、放宽或执行门禁规则。门禁的唯一
规则权威仍是 `World.move()`，因此这只是展示行为，不是内容或存档契约变更。

### 可见目标查看与命令帮助

`World.examine(query, target_type=None)` 是可见实体解析权威。物品候选只来自当前房间 typed
stacks 与玩家背包 typed stacks；怪物候选只来自当前房间的 `monster_ids`；角色候选只来自
`room_id` 等于玩家当前房间的角色。无类型查询先匹配唯一稳定 ID，再匹配唯一显示名称；同一
查询跨可见类型匹配多个名称或重复稳定 ID 时，必须用 `item`、`monster` 或 `character`
限定；同一类型内多个名称匹配则必须使用稳定 ID。其他房间、未掉落战利品和未取得的
对话奖励不会成为候选。

三个 frozen tagged 结果为 `ExamineItemOutcome`、`ExamineMonsterOutcome` 和
`ExamineCharacterOutcome`。命令层只解析 `examine` 语法并渲染结果；无参数、`room`、`here`
复用现有 `look` 房间摘要。`World.inspect_item()` 仍是物品专用兼容 API，返回原有
`InspectItemOutcome`；`inspect` 的成功输出和缺失错误保持兼容。所有查看分支在死亡和活动
对话中均可用且只读，不改变房间、玩家、金币、背包、装备、任务、flags、怪物或活动对话。

`CommandSpec` 注册表同时定义真实文字路由、别名、总帮助、`help [command]` 详细帮助和
死亡允许元数据。死亡门禁继续遵循 DEC-0020：先于对话数字选择和未知命令判断；允许集合从
注册表派生，避免帮助、路由和门禁分别维护。裸数字仍只在活动对话中选择选项，对话外保持
原有未知命令行为；`examine 1` 始终把 `1` 当作查看目标。M6 不改变内容定义、Schema、
original_demo 0.6.0 或 save v7。

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

### 公共 campaign IR

`pipeline.narrative_model` 生成的已验证 `NarrativeModel v1` 可与人工编写的
`RegistryCampaignPlan v1` 交给 `pipeline.campaign`，纯编译成自包含、确定性的
`CampaignSpec v1`。计划同时绑定模型稳定 ID 与规范 JSON 字节的 SHA-256；输出内嵌完整
NarrativeModel 快照，并对实体、视角、命题和 beat 做精确使用/遗漏核算。

CampaignSpec 描述有向地点、角色、场景 DAG、目标 DAG、严格 tagged completion 目标以及
知识披露/修正 IR。编译器检查地点可达性、物理场景间的有向通行、source beat 与 scene 的
阶段/前驱顺序、目标互斥与前驱可满足性，以及同一知识轨迹在 source/scene 两张 DAG 中的
全序关系。`corrected` 只存在于 adaptation-only 修正对象，不改写 NarrativeModel v1 的
披露枚举或内嵌快照。

该 artifact 尚不是运行时内容包。`src/`、World、存档、Web、玩家 CLI 和 Forge 不读取或
执行 CampaignSpec；任何后续 materialization 必须作为独立授权切片定义版本和验证边界。

## 对话系统

对话由内容定义和运行时状态两层构成：

```text
内容定义（不可变）
  DialogueDefinition（对话树）
  → DialogueNode（节点 + 台词）
  → DialogueOption（选项 + next_node_id + 必填有序 DialogueEffect 列表 + 可选条件）

运行时状态（World 持有）
  characters: dict[str, Character]          # 角色位置由 room_id 决定
  dialogue_defs: dict[str, DialogueDefinition]  # 对话树
  active_dialogue: DialogueState | None     # 当前对话位置
```

对话状态所有权在 `World`。`CommandProcessor` 只负责解析裸整数 / bye / talk
指令，将意图转给 World，再将 `TalkOutcome` 渲染为文本。

### 叙事条件投影

`World.available_dialogue_options(dialogue_id, node_id)` 对当前不可变对话定义和只读条件
上下文进行纯投影，是 CLI、Web 和选择索引的唯一可用选项来源。每个非终端节点必须至少有
一个无条件选项，保证状态变化不会留下无法结束的活动对话；条件不满足的选项不会显示，也
不能通过旧索引选择。`World.set_narrative_state()` 是唯一受类型和值域验证的状态写入入口。

### 终端节点

终端节点（`options` 为空元组的节点）在到达时自动结束对话，无需玩家输入
bye。结束选项（`next_node_id=null`）则立即结束对话。

### 状态不变性

`World.select_option()` 先在不修改真实 World 的前提下预检完整 effects 列表，再在一个
局部内存事务中按内容顺序执行。四个 frozen 分支为 `grant_item(item_id, quantity)`、
`grant_experience(amount)`、`accept_quest(quest_id)` 与 `set_flag(flag_id, value)`；它们分别
复用库存/任务结算、progression、唯一任务接取入口和 World-owned flags。预检或后续结算失败时，
房间、怪物、玩家、金币、背包、装备、任务、flags 和 `active_dialogue` 全部回滚，且对话位置
只会在所有效果成功后推进。`accept_quest` 可以绕过触发房间提前接取，但已接取或已完成时会使
整个选项失败；`set_flag` 保留缺失与显式 `false` 的差别，并报告旧值、新值和是否改变。

### 存档

`active_dialogue`、`quest_states`、顶层 `flags` 和 `narrative_state` 继续是必填字段；
`player` 还必须保存非负整数 `coins`。新存档统一写 save v9，并使用 `inventory_stacks` 和每个房间的
`item_stacks` 数组保存 `{item_id, quantity}`，而 `flags` 是稳定 ID 到真正 bool 的映射；
`narrative_state` 的键集合必须与内容包声明完全一致，且每个值都满足对应的 bool、int 范围或
enum 定义。每个任务状态仍只有 `completed`。v9 还要求所有内容角色的精确运行态，以及与当前
campaign 定义同键的 scene/objective/knowledge 状态；无 campaign 时这三组映射必须为空。

v8 只对没有 campaign 的内容包保持只读兼容；v7 只在内容包同时没有
`narrative_state.json` 和 campaign 时可读。读取兼容存档后再次保存会写 v9。带 campaign 的
内容包拒绝 v8/v7，以免默默补造角色、场景、目标或知识状态。v6 按格式版本明确拒绝，不做
隐式迁移；original_demo 内容包为 0.10.0，其他内容包版本创建的存档会由内容包版本检查拒绝。

加载时只校验并恢复已保存的 `quest_states`、`coins`、`flags`、角色和 campaign 状态；不执行
对话或 campaign effects，不调用任务接取、条件检查、奖励发放、阶段推进、知识揭示或商店交易。
商店和 campaign 定义从当前 ContentPack 重建，不会序列化可执行定义。其余严格验证包括：
- 顶层、`content_pack`、`player`、每个房间和每个怪物对象的键集合必须精确匹配；
- `inventory_stacks` 与 `item_stacks` 中的物品 ID、正整数数量、栈上限、重复栈、
  容量和装备数量必须与当前内容定义一致；
- 对话 ID 和节点 ID 必须存在，指向的节点不能是终端节点，且对话角色必须仍可交互；
- actor 键集合必须与内容角色完全一致；房间、presence、enabled 和 incapacitated 必须满足
  精确类型和值域；
- scene 的状态与 stage index、objective/knowledge 的状态必须与当前 campaign 定义一致。

任何不一致都以 `SaveLoadError` 拒绝，不静默清除。

`SaveLoadService.save()` 与 `.load()` 不带参数时仍使用兼容的 `default.json`。可选槽位名
由 `save <槽位>` / `load <槽位>` 传入，并只映射到保存目录内的 `<槽位>.json`：名称必须是
1–32 位小写 ASCII 字母、数字、`-` 或 `_`，以字母或数字开头，且拒绝路径片段、扩展名和
Windows 保留设备名。路径验证发生在序列化、读取或替换世界之前；槽位只选择文件，不改变
save v9 的 JSON 契约。

`SaveLoadService.save()` 在服务边界把文件系统 `OSError` 转换为带原始异常链的
`SaveLoadError`，因此 `CommandProcessor` 能将写入失败渲染为正常的“存档失败”文本，
而不会让 I/O 异常逃出游戏循环。`_atomic_write()` 的原子写入和临时文件清理职责不变；
非 I/O 编程错误不会被重新标记为存档 I/O 错误。

### 固定金币商店

`ShopDefinition` 与其有序 `ShopListingDefinition` 目录是冻结内容定义；每个房间至多有一个
商店。`World.shop()` 只读返回目录和当前金币，`buy()` 与 `sell()` 返回各自的 typed outcome。
目录是无限供应且不保存库存：买入只在所有价格、金币、容量、合并后的 `stack_limit` 和
非堆叠物品唯一性检查通过后扣金币、加入物品并结算 `collect_item` 任务；奖励失败会连同
金币和物品回滚。卖出只移除未装备的背包物品并增加固定售价，已完成任务不会撤销。

`shop` 是倒下时仍可用的只读命令；`buy`/`sell` 受死亡门禁。三者都不结束活动对话，也不
改变商店目录。`look` 只展示当前房间商店的名称与稳定 ID；`status` 展示金币和按 flag ID
字典序排列的 flags。动态价格、折扣、货币物品和可变库存不属于本切片。

## 扩展原则

- 存档应序列化运行时状态，而不是覆盖内容包。
- 数据库访问应集中到 repository 接口，不进入命令处理器。
- 随机、时间和外部模型都应通过可替换接口注入。
- LLM 只能提出候选指令或候选内容，不能直接修改 `World`。
- 内容格式变更必须带版本、迁移说明、Schema 和引用测试。
