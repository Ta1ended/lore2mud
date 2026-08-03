# 内容包格式

## 必需文件

每个内容包是一个独立目录：

```text
content_pack/
├─ pack.json
├─ rooms.json
├─ items.json
├─ monsters.json
├─ characters.json
├─ quests.json
├─ dialogues.json
├─ shops.json
├─ narrative_state.json  # 可选
└─ campaign.json         # 可选
```

前八个文件必须存在；没有角色、任务、对话或商店时使用空数组。`narrative_state.json`
和 `campaign.json` 是可选的：缺失前者时内容包没有类型化叙事状态，缺失后者时保持既有
房间/任务/对话运行方式。所有文本为 UTF-8 JSON。
稳定 ID 必须匹配：

```text
^[a-z][a-z0-9_]*$
```

名称可以修改，引用只能使用稳定 ID。

## `pack.json`

```json
{
  "id": "original_demo",
  "name": "内容包名称",
  "version": "0.1.0",
  "start_room_id": "room_start",
  "player": {
    "max_hp": 20,
    "attack": 5,
    "defense": 1,
    "inventory_capacity": 10,
    "coins": 0
  },
  "extensions": {}
}
```

`extensions` 为未来的私有 canon provider 或工具元数据预留；引擎首版不解释
其中内容。

`player.coins` 必填，必须是非负整数；bool、负数、字符串和缺失字段均被拒绝。

## `narrative_state.json`

该可选文件的格式版本固定为 1，用于声明通用叙事状态，而不是存放玩家运行时数据：

```json
{
  "format_version": 1,
  "states": [
    {"id": "state_gate_open", "kind": "bool", "initial": false},
    {"id": "state_signal", "kind": "int", "initial": 1, "minimum": 0, "maximum": 3},
    {"id": "state_mode", "kind": "enum", "initial": "idle", "values": ["idle", "ready"]}
  ]
}
```

- 每个 `id` 是内容包内唯一的稳定 ID，且不得与对话 `set_flag.flag_id` 重名。
- `bool.initial` 必须是真正的 bool。
- `int.initial`、可选 `minimum` 和可选 `maximum` 都是 bool 以外的整数；同时给出范围时
  `minimum <= maximum`，`initial` 必须在范围内。
- `enum.values` 是至少一个、不重复的稳定 ID 字符串；`initial` 必须属于该集合。
- 运行时 `World` 以这些定义初始化 `narrative_state`。新存档统一写 v9 并精确保存该映射；
  没有 campaign 的内容包可只读加载 v8。只有同时没有本文件和 campaign 的内容包才可只读
  加载 v7。

## `campaign.json`

该可选文件的格式版本固定为 1。它描述题材中立的运行时 campaign，而不是小说事实或任意
脚本；完整结构由 `schemas/campaign.schema.json` 约束。顶层必须精确包含：

```json
{
  "format_version": 1,
  "location_views": [],
  "actor_views": [],
  "dialogue_views": [],
  "scenes": [],
  "interactables": [],
  "actions": [],
  "objectives": [],
  "knowledge": [],
  "log_entries": []
}
```

### 动态投影

- `location_views` 可为已有房间声明条件描述和条件出口。条件出口必须引用该房间真实存在的
  方向；`World.available_exits()` 同时控制显示与移动，客户端不能直接提交隐藏方向。
- `actor_views` 可为已有角色声明条件描述和可见条件。角色位置、`present/absent`、`enabled`
  与 `incapacitated` 是运行时状态，Web、CLI、查看和对话都读取 World 的当前投影。
- `dialogue_views` 只替换已有对话节点的显示文本；选项、跳转和强类型 effects 仍来自
  `dialogues.json`，可用选项仍以 `World.available_dialogue_options()` 为唯一权威。
- 每个文本投影是 `{ "text": "...", "condition": {...} }`；一个非空投影列表必须恰有一个
  省略 `condition` 的回退文本。按文件顺序采用第一个满足条件的文本，否则采用该回退。
- 所有条件复用对话条件的受限 AST、深度/节点上限和引用校验，不支持 `eval`、Python、插件
  或客户端自定义表达式。

### 场景、交互对象与动作

`scenes` 声明稳定 ID、显示名、房间、初始 `inactive|active` 状态和至少一个有序阶段。活动
场景只有一个 `stage_index`；阶段列出当前可用的 `interactable_ids`。场景可激活、推进或完成，
完成后不再投影交互对象。

`interactables` 使用统一形状表示 `actor`、`location`、`object`、`ritual` 或 `inner`：

- `actor` / `location` 使用 `target_id` 引用已有角色或房间；
- `object` 可选引用已有物品，也可仅作为场景对象；
- `object`、`ritual` 和 `inner` 必须以 `location_id` 或 `scene_id` 确定唯一上下文；
- `scene_id` 与阶段引用必须一致；条件、actor 状态、当前位置和活动阶段共同决定可见性；
- 每个 `action_id` 必须存在，且一个动作必须恰属于一个交互对象。

`actions` 声明稳定 ID、按钮/命令标签、成功文本、可选条件和有序 `effects`。`World` 先在
完整 World 副本上预检全部效果，再在扩展事务中执行；任何后续异常都会回滚房间、怪物、玩家、
背包、装备、任务、flags、叙事状态、角色、场景、目标、知识和活动对话。支持的效果为：

- 既有 `grant_item`、`grant_experience`、`accept_quest`、`set_flag`；
- `set_narrative_state`、`adjust_narrative_state`；
- `remove_item`；
- `move_actor`，可原子修改位置、`presence`、`enabled` 和 `incapacitated` 中至少一项；
- `advance_scene` 的 `activate|advance|complete`；
- `advance_objective` 的 `activate|start|complete|fail`；
- `reveal_knowledge` 到 `heard|suspected|confirmed`，以及 `retract_knowledge`、
  `correct_knowledge`。

动作只按稳定 ID 执行，但稳定 ID 本身不构成授权。`World.execute_campaign_action()` 会再次从
当前交互对象、场景阶段和条件投影动作；隐藏动作通过 CLI、旧索引或 Web JSON 直接提交都会失败，
且不改变状态。活动对话期间不执行 campaign 动作。

### 目标、知识与日志

- `objectives` 初始为 `inactive` 或 `active`，运行时状态为 `inactive`、`active`、
  `in_progress`、`completed` 或 `failed`。激活前所有依赖必须完成；依赖图必须无环。
  `exclusive_with` 必须对称，激活一端会把尚未选择的另一端锁定为 `failed`。
- `knowledge` 初始可为 `unknown`、`heard`、`suspected`、`confirmed`、`retracted` 或
  `corrected`，并为每个可见状态提供玩家文本。`unknown` 永不进入玩家日志；揭示只可向前，
  撤回和修正必须从允许的既有状态发生。
- `log_entries` 是条件故事/目标/知识文本。`World.available_log_entries()` 还合并当前可见目标
  与知识，Web 和 CLI 不从客观 canon 或隐藏定义自行推导日志。

带 campaign 的内容包必须使用 save v9；v8 缺少角色、场景、目标和知识运行态，因此明确拒绝。
读取存档只恢复已验证状态，不重放 action effects，不推进阶段，也不再次揭示知识。

## 房间

`rooms.json` 是房间数组，对应 `schemas/location.schema.json`：

```json
{
  "id": "room_start",
  "name": "起点",
  "description": "原创描述。",
  "exits": {
    "north": "room_north",
    "west": {
      "target_room_id": "room_west",
      "required_item_id": "item_gate_token"
    }
  },
  "item_stacks": [{"item_id": "item_lantern", "quantity": 1}],
  "monster_ids": []
}
```

出口可保留兼容格式 `"方向": "目标房间ID"`，也可使用对象格式：

- `target_room_id`：必填、非空稳定 ID，必须引用现有房间。
- `required_item_id`：可省略的非空稳定 ID，必须引用现有物品；`null`、空字符串和
  其他类型均非法。
- 出口对象严格拒绝未知字段；同一房间中方向按 `casefold()` 不能重复。
- 移动经过带 `required_item_id` 的出口时，玩家必须在背包中持有该物品。物品不被
  消耗；类型和初始摆放不受额外限制。
- `look` 会只读显示门禁出口的方向、所需物品名称、稳定 ID，以及“未持有”或“已持有”；
  普通出口只显示方向。这不改变内容包格式或移动规则。

出口目标、门禁物品、房间内物品和怪物必须存在。物品和怪物首版不能同时放在多个房间。

## 物品

```json
{
  "id": "item_lantern",
  "name": "提灯",
  "description": "原创描述。"
}
```

物品只有身份和描述时不可使用。字段缺省表示不可使用；显式 `heal_amount:
null` 属于非法内容，加载器拒绝内容包。

### 丢弃保护

物品可声明可选布尔字段 `droppable`，默认值为 `true`。设为 `false` 时，
`World.drop()` 会在改变背包或房间状态前拒绝丢弃；适合仍需由玩家持有的门禁钥匙等
关键物品。该定义随内容包加载，不写入存档，因此不需要提升 save 格式版本。

### 消耗品

物品可以带有可选的 `heal_amount` 字段（正整数），表示使用后恢复的生命数值：

```json
{
  "id": "item_linglu_pill",
  "name": "灵露丸",
  "description": "一枚晶莹的小药丸。",
  "heal_amount": 10
}
```

- `heal_amount` 为正整数时，玩家可以用 `use <物品ID或名称>` 使用该物品。
- 使用后恢复 `min(heal_amount, max_hp - hp)` 点生命，物品从背包移除。
- 满血时拒绝使用（不消耗物品）；HP 为 0 时拒绝使用。

### 装备

物品可以带有 `slot` 和对应的 bonus 字段，表示可装备到指定槽位并提供属性加成：

```json
{
  "id": "item_crystal_blade",
  "name": "晶刃",
  "description": "一片薄而透明的晶体。",
  "slot": "hand",
  "attack_bonus": 3
}
```

- `slot` 为 `"hand"` 时需要 `attack_bonus` ≥ 1；为 `"body"` 时需要 `defense_bonus` ≥ 1。
- hand 装备增加有效攻击力；body 装备增加有效防御力。
- 装备物品仍留在背包中；卸下后仍在背包。
- hand 和 body 可同时装备；同一槽位已占用时必须先 `unequip`。
- 装备中的物品不可被 `use` 命令使用。
- `slot` 与 `heal_amount` 不可同时指定；`attack_bonus` 与 `defense_bonus` 不可同时指定。
- hand 槽不可指定 `defense_bonus`；body 槽不可指定 `attack_bonus`。
- 所有字段（`slot`、`attack_bonus`、`defense_bonus`、`heal_amount`）显式 `null` 均被拒绝；不可用字段应省略。

## 怪物

```json
{
  "id": "monster_example",
  "name": "训练假人",
  "description": "原创描述。",
  "room_id": "room_north",
  "max_hp": 8,
  "attack": 3,
  "defense": 1,
  "experience_reward": 12,
  "loot_item": {"item_id": "item_training_core", "quantity": 1}
}
```

`room_id` 必须与对应房间的 `monster_ids` 一致。所有数值必须是非负整数，
`max_hp` 与 `attack` 至少为 1。

`loot_item` 是可选的 typed stack 对象（`{item_id, quantity}`）。指定时必须引用存在、初始未放置在房间中的物品，且该物品
不能同时作为对话奖励或另一个怪物的战利品。怪物首次被击败时，战利品会放入当前房间；
它可以是消耗品，玩家仍通过现有 `take` / `use` 指令处理。

## 角色与任务

角色首版只校验身份和位置：

```json
{
  "id": "character_guide",
  "name": "向导",
  "description": "原创描述。",
  "room_id": "room_start"
}
```

角色位置由 `CharacterDefinition.room_id` 唯一决定。`look` 命令自动显示当前
房间的角色列表。

任务定义是一个 frozen tagged union。每个对象都必须有共同字段 `id`、`name`、
`description`、`kind`、`trigger_room_id` 和 `reward_experience`，并且只能带与
`kind` 对应的那一组目标字段；不能把其他分支的目标字段混入同一对象。

`monster_defeated` 使用 `target_monster_id`：

```json
{
  "id": "quest_clear_mite",
  "name": "清除灰壳兽",
  "description": "前往静默观测站，击败那只灰壳兽。",
  "kind": "monster_defeated",
  "trigger_room_id": "room_ember_wharf",
  "target_monster_id": "monster_ash_mite",
  "reward_experience": 15
}
```

`reach_room` 使用 `target_room_id`：

```json
{
  "id": "quest_reach_observatory",
  "name": "抵达观测站",
  "description": "进入静默观测站。",
  "kind": "reach_room",
  "trigger_room_id": "room_ember_wharf",
  "target_room_id": "room_silent_observatory",
  "reward_experience": 0
}
```

`collect_item` 使用 `target_item_id` 和 `required_quantity`：

```json
{
  "id": "quest_collect_pills",
  "name": "收集灵露丸",
  "description": "在背包中保留两枚灵露丸。",
  "kind": "collect_item",
  "trigger_room_id": "room_ember_wharf",
  "target_item_id": "item_linglu_pill",
  "required_quantity": 2,
  "reward_experience": 5
}
```

- `trigger_room_id` 引用现有房间。玩家进入该房间或在该房间开始游戏时自动
  接取任务；接取后立即进行一次幂等条件检查。
- 三个 `kind` 的目标必须分别引用已存在的怪物、房间或物品。相同 `(kind, target)`
  条件只能属于一个任务；不同 kind 不共享字段。
- `required_quantity` 必须是整数，满足
  `1 <= required_quantity <= items[target_item_id].stack_limit`。完成条件是背包中
  该物品的数量大于或等于这个值。
- `reward_experience` 是非负整数。
- `World` 在移动、拾取、击败怪物、成功执行对话 `grant_item` 效果和商店买入后检查已接取任务；同一次
  动作完成多个任务时，按任务 ID 字典序结算并输出结果。`completed` 表示奖励已成功
  发放，之后 `drop`、`use` 或读档都不会撤销或补发。
- 玩家使用 `quests` 指令查看已接取任务及收集任务的当前数量。

## 对话

`dialogues.json` 是对话树数组。每个对话引用一个角色，包含节点和选项：

```json
[
  {
    "id": "dialogue_guide",
    "character_id": "character_guide",
    "start_node_id": "node_greeting",
    "nodes": [
      {
        "id": "node_greeting",
        "text": "你好，旅人。",
        "options": [
          {"id": "opt_who", "text": "你是谁？", "next_node_id": "node_intro", "effects": []},
          {"id": "opt_bye", "text": "告辞。", "next_node_id": null, "effects": []}
        ]
      },
      {
        "id": "node_intro",
        "text": "我是这里的向导。",
        "options": [
          {"id": "opt_back", "text": "（换个话题）", "next_node_id": "node_greeting", "effects": []},
          {"id": "opt_bye2", "text": "告辞。", "next_node_id": null, "effects": []}
        ]
      }
    ]
  }
]
```

### 对话字段

- `id`：稳定 ID，全局唯一。
- `character_id`：引用 `characters.json` 中的角色。每个角色最多一个对话。
- `start_node_id`：起始节点 ID，必须存在于 `nodes` 中。
- `nodes`：节点数组，至少一个。

### 节点字段

- `id`：稳定 ID，对话内唯一。
- `text`：NPC 台词，非空字符串。
- `options`：选项数组。**必须存在**（省略 `options` 键会被拒绝）。
  - 空数组 `[]` = 终端节点：显示台词后对话自动结束。
  - 非空数组 = 显示台词和选项，等待玩家选择。

### 选项字段

- `id`：稳定 ID，节点内唯一。
- `text`：选项显示文本，非空字符串。
- `next_node_id`：目标节点 ID，或 `null`（结束对话）。
  - 省略 `next_node_id` 等价于 `null`。
  - 非 null 时必须引用同对话内的节点。
- `effects`：**必填**数组；空数组合法。旧 `grant_item` 字段是未知字段，直接拒绝。
  每个对象都必须有 `kind`，且只允许所属分支的精确字段：
  - `{"kind": "grant_item", "item_id": "...", "quantity": 1}`：稳定 ID、正整数数量；
    物品必须存在、不是消耗品、不超过 `stack_limit`，且非堆叠物品遵守跨来源唯一性。
  - `{"kind": "grant_experience", "amount": 1}`：`amount` 是 bool 以外的正整数。
  - `{"kind": "accept_quest", "quest_id": "..."}`：引用存在的稳定任务 ID。
  - `{"kind": "set_flag", "flag_id": "...", "value": true}`：稳定 flag ID 和真正 bool 值。
  同一选项不得重复 `grant_item.item_id`、`accept_quest.quest_id`、`set_flag.flag_id`，且最多一个
  `grant_experience`；不同 kind 和不同目标可按原数组顺序组合。
- `condition`：可选的受限对象。它只能使用 `state_equals`、`state_compare`、`has_item`、
  `at_location`、`quest_status`、`all`、`any` 或 `not`，严格拒绝未知字段和任意脚本。
  - `state_equals` 的值必须符合被引用状态的精确类型和值域；`state_compare` 只引用 int 状态，
    使用 `lt`、`lte`、`gt` 或 `gte`。
  - `has_item`、`at_location` 和 `quest_status` 分别引用已有物品、房间和任务；任务状态只能是
    `not_accepted`、`active` 或 `completed`。
  - `all` 和 `any` 至少有一个子条件，`not` 恰有一个子条件。单个条件树最大深度为 16、最大
    节点数为 256。
  - 每个非终端节点至少保留一个没有 `condition` 的选项。运行时只显示
    `World.available_dialogue_options()` 返回的顺序，并以该投影重新编号。

### 对话交互

- `talk <角色>`：开始对话（已在对话中则重显当前节点）。
- `<正整数>`：选择第 N 个选项（仅对话中有效，匹配 `^[1-9][0-9]{0,4}$`，最大99999）。
- `bye`：主动结束对话（仅对话中有效）。
- 移动房间自动结束对话。
- `select_option` 先预检完整 effects 列表，后在一个 World 事务中按数组顺序执行；容量、栈上限、
  非堆叠唯一性、任务状态和后续异常均不能留下半完成状态，对话位置仅在全部成功后推进。
- `grant_item` 会结算已接取的 `collect_item` 任务；`grant_experience` 复用 progression 服务；
  `accept_quest` 可绕过 `trigger_room_id` 提前接取并立即结算，已接取/完成时整个选项失败；
  `set_flag` 是 World-owned upsert，缺失与显式 `false` 不同，重复设置同值是成功 no-op。
- `TalkOutcome.effect_outcomes` 是按 effects 原顺序排列的 frozen typed outcomes；CLI 同序渲染，
  不重复渲染任务完成或升级文本。

## 商店

`shops.json` 是必需数组；没有商店时写 `[]`。每个商店的精确形状为：

```json
[
  {
    "id": "shop_chen_travel_goods",
    "name": "陈伯的行囊",
    "room_id": "room_glassgrass_path",
    "catalog": [
      {
        "item_id": "item_linglu_pill",
        "buy_price": 4,
        "sell_price": 2
      }
    ],
    "adaptation_notes": "本仓库原创演示商店。"
  }
]
```

- `id`、`room_id` 和每个 `item_id` 都是稳定 ID；房间和物品引用必须存在。
- `catalog` 必须是非空有序数组，同一商店内不得重复 `item_id`，每个房间至多一个商店。
- `buy_price` 和 `sell_price` 都是 bool 以外的正整数，且 `sell_price <= buy_price`。
- `stack_limit=1` 的目录物品参与既有跨来源唯一性检查。
- 商店定义是冻结、无限供应的内容目录；没有 stock、补货、折扣或动态价格字段，也不会写入存档。

运行时命令是 `shop`、`buy <物品ID或名称> [数量]` 和 `sell <物品ID或名称> [数量]`。`shop`
只读且倒下时可用；买卖预检金币、目录、数量、容量、栈上限、非堆叠唯一性和装备状态，在
事务中完成金币与背包变更。买入会结算 collect_item 任务，卖出不会撤销已完成任务。

## 原作来源扩展

任何实体都可以附加：

```json
{
  "canon_ref": {
    "entity_id": "canon_entity_id",
    "source_chapters": [
      "chapter_000123"
    ]
  },
  "adaptation_notes": "哪些字段属于游戏化设计。"
}
```

一旦存在 `canon_ref`，`source_chapters` 至少包含一个非空来源。canon 实体及
事实保存在私有资料层；内容包只保留引用和游戏规则。

## 校验

加载内容包会验证结构与跨文件引用：

```python
from lore2mud.content import validate_content_pack

validate_content_pack("examples/original_demo")
```

格式变更必须同步 Python 加载器、JSON Schema、原创示例、测试和本文档。
