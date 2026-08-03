# 微光边站

这是 lore2mud 自带的完全原创冒险内容包，用一段完整旅程验证移动、拾取、背包、
确定性战斗、升级、消耗品、装备（hand/body）、任务闭环、强类型对话效果、金币和固定商店。
它不引用任何第三方小说、角色或世界观。

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
4
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
quests
go east
go north
attack monster_mist_crawler
attack monster_mist_crawler
look
take item_condensed_mist
go south
go east
go east
attack monster_prism_sentinel
attack monster_prism_sentinel
look
take item_beacon_core
go east
quests
talk character_beacon_echo
1
status
save ending
quit
```

## 三类任务与分段接取任务

演示内容包 0.10.0 在起始房间自动接取三条完全原创任务：

- `quest_collect_linglu_pills`：背包中收集 2 枚灵露丸（`collect_item`）。
- `quest_reach_silent_observatory`：抵达静默观测站（`reach_room`）。
- `quest_clear_ash_mite`：击败灰壳兽（`monster_defeated`，奖励 15 点经验）。
- `quest_collect_ash_mite_gel`：收集一份灰壳凝胶（`collect_item`，奖励 5 点经验）。它可由
  老陈的对话提前接取；跳过对话时，进入静默观测站仍会按既有 M3 规则自动接取。
- `quest_clear_spark_hound`：进入静默观测站后接取，前往其东侧的碎讯支线击败火花巡兽
  （`monster_defeated`，奖励 18 点经验）。
- `quest_clear_mist_crawler`：进入断轨岔口后接取，前往北侧雾凝机井击败雾核潜行者
  （`monster_defeated`，奖励 20 点经验）。
- `quest_clear_prism_sentinel`：同样在断轨岔口接取，前往东侧的余辉信标台击败棱镜哨卫
  （`monster_defeated`，奖励 22 点经验）。
- `quest_restore_beacon`：抵达余辉信标台后接取；只有击败棱镜哨卫、拾取它掉落的
  `item_beacon_core`，才能进入信标心室并完成任务（`reach_room`，奖励 25 点经验）。

执行 `quests` 可查看收集进度。拾取、移动、击败怪物、成功对话 `grant_item` 效果和商店买入都会由
引擎统一检查已接取任务；已经完成的任务不会因丢弃或使用物品而撤销。

## 对话

琉草小径的房间描述会提示一位愿意交谈的老人；老陈（character_elder_chen）可以与玩家对话：

- `talk character_elder_chen` 开始对话
- 输入数字选择对话选项
- `bye` 或选择「告辞」选项结束对话
- 移动房间会自动结束对话

开场直接询问「这附近有什么需要留意的吗？」即可听到观测站警告；原有的「你是谁？」→
「你知道观测站那边的情况吗？」路线仍然有效。观测站节点的奖励选项按固定顺序执行：
写入 `flag_chen_warned_ash_mite=true`、接取 `quest_collect_ash_mite_gel`、获得 3 点经验、
获得 `item_chen_token`。重复选择会因任务已经接取而整体拒绝，不重复发放经验、物品或标记。

信标心室的「让信标重新点亮」选项使用内容包声明的无脚本条件：它要求 bool、范围受限 int 和
enum 叙事状态仍分别为 `true`、至少 `1` 和 `standby`，同时要求持有核心、位于心室且最终任务
已经完成。不满足时该选项不会投影给 CLI 或 Web；这些状态由 `narrative_state.json` 定义并随存档保存。

## 金币与商店

玩家初始有 20 金币。琉草小径的 `shop_chen_travel_goods`（陈伯的行囊）固定出售并收购
`item_linglu_pill`：买入 4 金币，卖出 2 金币。使用 `shop` 查看目录，使用
`buy <物品ID或名称> [数量]` 和 `sell <物品ID或名称> [数量]` 交易。目录无限供应且不保存库存；
`status` 会显示金币和 flags。

## 战利品与路线选择

灰壳兽首次被击败后会在当前房间掉落一份 `item_ash_mite_gel`。使用 `look` 查看掉落，
再用 `take item_ash_mite_gel` 拾取；它是一件可用的原创消耗品。

断轨岔口提供明确的路线选择：直接向东可以更快抵达最终信标，向北则要承担雾核潜行者造成的
伤害，但胜利后会得到可恢复 12 点生命的 `item_condensed_mist`。北支线任务不是进入结局的门槛，
玩家可以用时间和风险换取决战补给，也可以依靠已有装备与药物直接推进。

## M7 内容扩容

从静默观测站向东依次经过碎讯支线和断轨岔口后，可选择北侧的雾凝机井或东侧的折光档案室。
折光档案室继续向东通往余辉信标台。雾核潜行者与棱镜哨卫都复用现有确定性战斗、怪物经验、
战利品和 `monster_defeated` 任务结算。按上方推荐流程装备晶刃和铜鳞甲后，每只新增怪物都可在
三次攻击内击败。

## 可确认结局

棱镜哨卫是冒险高潮。它掉落的 `item_beacon_core` 是余辉信标台东侧出口的唯一门禁物品；
该物品声明 `droppable=false`，尝试 `drop item_beacon_core` 会在状态不变的情况下被拒绝。
未持有时移动会失败且 World 状态保持不变。进入信标心室会完成 `quest_restore_beacon`，与
`character_beacon_echo` 对话并选择点亮信标后，World 写入 `flag_beacon_restored=true`。
`quests`、`status` 和 save/load 可以分别确认最终任务、结局 flag 和完整终局状态。

## 存档兼容性

本演示内容包 0.10.0 声明了 `narrative_state.json`，但不包含 `campaign.json`。所有新存档都写为
v9，精确保存当前任务、房间、战利品、flags、叙事状态和角色运行态。由于本内容包没有 campaign，
严格 loader 仍可只读加载由本内容包创建的 v8 存档；再次保存时会写为 v9。v7 缺少叙事状态，
因此不能用于本演示内容包。loader 不会猜测旧档状态，也不会隐式迁移内容包版本；需要继续旧进度时
请使用创建该存档的原内容包，进入本演示时请在 0.10.0 新开游戏。

## 物品交互

- `drop <物品ID或名称>` 会将背包中的未装备物品放到当前房间。
- 已装备的 hand 或 body 物品必须先用 `unequip` 卸下，才能放下。
