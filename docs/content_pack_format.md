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
└─ dialogues.json
```

首版要求七个文件都存在；没有角色、任务或对话时使用空数组。所有文本为 UTF-8
JSON。稳定 ID 必须匹配：

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
    "inventory_capacity": 10
  },
  "extensions": {}
}
```

`extensions` 为未来的私有 canon provider 或工具元数据预留；引擎首版不解释
其中内容。

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

任务定义触发房间、目标怪物和经验奖励：

```json
{
  "id": "quest_clear_mite",
  "name": "清除灰壳兽",
  "description": "前往静默观测站，击败那只灰壳兽。",
  "trigger_room_id": "room_ember_wharf",
  "target_monster_id": "monster_ash_mite",
  "reward_experience": 15
}
```

- `trigger_room_id` 引用现有房间。玩家进入该房间或在该房间开始游戏时自动
  接取任务。
- `target_monster_id` 引用现有怪物。击败该怪物时任务完成，奖励经验即时发放。
  当前每个目标怪物最多对应一个任务；内容加载器会拒绝重复的目标怪物引用。
- `reward_experience` 是非负整数。
- 玩家使用 `quests` 指令查看已接取任务及进度。

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
          {"id": "opt_who", "text": "你是谁？", "next_node_id": "node_intro"},
          {"id": "opt_bye", "text": "告辞。", "next_node_id": null}
        ]
      },
      {
        "id": "node_intro",
        "text": "我是这里的向导。",
        "options": [
          {"id": "opt_back", "text": "（换个话题）", "next_node_id": "node_greeting"},
          {"id": "opt_bye2", "text": "告辞。", "next_node_id": null}
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
- `grant_item`：可省略的奖励物品 typed stack 对象（`{item_id, quantity}`）。省略表示不奖励；若出现，必须是
  非空稳定 ID，`null` 和其他类型均非法。
  - 必须引用 `items.json` 中存在的非消耗品，且该物品不能放置在任何房间。
  - 同一物品最多只能被一个对话选项奖励。

### 对话交互

- `talk <角色>`：开始对话（已在对话中则重显当前节点）。
- `<正整数>`：选择第 N 个选项（仅对话中有效，匹配 `^[1-9][0-9]{0,4}$`，最大99999）。
- `bye`：主动结束对话（仅对话中有效）。
- 移动房间自动结束对话。
- 对话不改变 HP、经验、装备、任务或房间布局；带 `grant_item` 的选项会在
  背包有空位且尚未拥有该物品时，原子性地加入一个奖励物品。失败时对话状态和
  其他游戏状态均不变。

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
