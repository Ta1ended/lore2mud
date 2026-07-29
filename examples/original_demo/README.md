# 微光边站

这是 lore2mud 自带的完全原创演示内容包，只用于验证移动、拾取、背包、
确定性战斗、升级、消耗品、装备（hand/body）、任务闭环和对话系统。它不引用
任何第三方小说、角色或世界观。

## 推荐试玩

```text
look
take item_crystal_blade
take item_bronze_scale_mail
take item_linglu_pill 2
equip item_crystal_blade
equip item_bronze_scale_mail
status
quests
go east
talk character_elder_chen
1
3
go east
attack monster_ash_mite
attack monster_ash_mite
look
take item_ash_mite_gel
quests
quit
```

## 三类任务

演示内容包 0.4.0 在起始房间自动接取三条完全原创任务：

- `quest_collect_linglu_pills`：背包中收集 2 枚灵露丸（`collect_item`）。
- `quest_reach_silent_observatory`：抵达静默观测站（`reach_room`）。
- `quest_clear_ash_mite`：击败灰壳兽（`monster_defeated`，奖励 15 点经验）。

执行 `quests` 可查看收集进度。拾取、移动、击败怪物和成功发放对话物品奖励都会由
引擎统一检查已接取任务；已经完成的任务不会因丢弃或使用物品而撤销。

## 对话

琉草小径上有一位老陈（character_elder_chen），可以与他对话：

- `talk character_elder_chen` 开始对话
- 输入数字选择对话选项
- `bye` 或选择「告辞」选项结束对话
- 移动房间会自动结束对话

老陈会介绍微光边站的历史，并暗示观测站里有灰壳兽。

## 怪物战利品

灰壳兽首次被击败后会在当前房间掉落一份 `item_ash_mite_gel`。使用 `look` 查看掉落，
再用 `take item_ash_mite_gel` 拾取；它是一件可用的原创消耗品。

## 物品交互

- `drop <物品ID或名称>` 会将背包中的未装备物品放到当前房间。
- 已装备的 hand 或 body 物品必须先用 `unequip` 卸下，才能放下。
