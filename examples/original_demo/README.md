# 微光边站

这是 lore2mud 自带的完全原创演示内容包，只用于验证移动、拾取、背包、
确定性战斗、升级、消耗品、装备（hand/body）、任务闭环、强类型对话效果、金币和固定商店。它不引用
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
1
2
shop
buy item_linglu_pill 2
sell item_linglu_pill
go east
attack monster_ash_mite
attack monster_ash_mite
look
take item_ash_mite_gel
quests
go east
attack monster_spark_hound
attack monster_spark_hound
attack monster_spark_hound
quests
quit
```

## 三类任务与分段接取任务

演示内容包 0.7.0 在起始房间自动接取三条完全原创任务：

- `quest_collect_linglu_pills`：背包中收集 2 枚灵露丸（`collect_item`）。
- `quest_reach_silent_observatory`：抵达静默观测站（`reach_room`）。
- `quest_clear_ash_mite`：击败灰壳兽（`monster_defeated`，奖励 15 点经验）。
- `quest_collect_ash_mite_gel`：收集一份灰壳凝胶（`collect_item`，奖励 5 点经验）。它可由
  老陈的对话提前接取；跳过对话时，进入静默观测站仍会按既有 M3 规则自动接取。
- `quest_clear_spark_hound`：进入静默观测站后接取，前往其东侧的碎讯支线击败火花巡兽
  （`monster_defeated`，奖励 18 点经验）。

执行 `quests` 可查看收集进度。拾取、移动、击败怪物、成功对话 `grant_item` 效果和商店买入都会由
引擎统一检查已接取任务；已经完成的任务不会因丢弃或使用物品而撤销。

## 对话

琉草小径上有一位老陈（character_elder_chen），可以与他对话：

- `talk character_elder_chen` 开始对话
- 输入数字选择对话选项
- `bye` 或选择「告辞」选项结束对话
- 移动房间会自动结束对话

老陈会介绍微光边站的历史，并暗示观测站里有灰壳兽。观测站节点的奖励选项按固定顺序执行：
写入 `flag_chen_warned_ash_mite=true`、接取 `quest_collect_ash_mite_gel`、获得 3 点经验、
获得 `item_chen_token`。重复选择会因任务已经接取而整体拒绝，不重复发放经验、物品或标记。

## 金币与商店

玩家初始有 20 金币。琉草小径的 `shop_chen_travel_goods`（陈伯的行囊）固定出售并收购
`item_linglu_pill`：买入 4 金币，卖出 2 金币。使用 `shop` 查看目录，使用
`buy <物品ID或名称> [数量]` 和 `sell <物品ID或名称> [数量]` 交易。目录无限供应且不保存库存；
`status` 会显示金币和 flags。

## 怪物战利品

灰壳兽首次被击败后会在当前房间掉落一份 `item_ash_mite_gel`。使用 `look` 查看掉落，
再用 `take item_ash_mite_gel` 拾取；它是一件可用的原创消耗品。

## 第二个遭遇

从静默观测站向东可抵达碎讯支线。这里的火花巡兽没有引入新机制：它使用现有确定性战斗、
怪物经验和 `monster_defeated` 任务结算。击败灰壳兽后继续向东，再攻击
`monster_spark_hound` 三次即可完成该任务。

## 物品交互

- `drop <物品ID或名称>` 会将背包中的未装备物品放到当前房间。
- 已装备的 hand 或 body 物品必须先用 `unequip` 卸下，才能放下。
