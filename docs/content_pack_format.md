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
└─ quests.json
```

首版要求六个实体文件都存在；没有角色或任务时使用空数组。所有文本为 UTF-8
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
    "north": "room_north"
  },
  "item_ids": ["item_lantern"],
  "monster_ids": []
}
```

出口目标、物品和怪物必须存在。物品和怪物首版不能同时放在多个房间。

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
  "experience_reward": 12
}
```

`room_id` 必须与对应房间的 `monster_ids` 一致。所有数值必须是非负整数，
`max_hp` 与 `attack` 至少为 1。

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
