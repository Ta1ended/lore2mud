# Engine Completion Milestones

_Last updated: 2026-07-29（M6 已由 GPT-5.6-sol 独立验收 GO；M7 未授权）_

本文件定义公共引擎从当前状态到功能完备的里程碑路线。每个里程碑是一个可独立验证的
纵向切片，完成后更新本文件和相关交接记录。
本次 M2 文档封板前的同步基线为 `1ee0b30`：`HEAD`、`origin/main` 与远端 `main`
一致，工作树干净，ahead/behind 为 `0/0`。

---

## M1: 死亡 / 失败处理 ✅

- **状态**: GPT-5.6-sol 已于 2026-07-28 对 `c329546` 完成独立验收，结论 GO。
- **执行者**: Hermes agent。
- **验收者**: GPT-5.6-sol。
- **强制完成条件**:
  - HP=0 后只允许只读命令以及 save/load/recover/quit/exit。
  - 所有修改型 World 方法统一由 `_require_alive()` 拒绝（10 个方法）。
  - 命令层门禁位于裸数字和 `bye` 路由之前（DEC-0020）。
  - `recover` 回到起始房间、恢复满 HP、清除活动对话。
  - 保留等级、经验、任务、背包、装备、怪物 HP 和世界物品状态。
  - 不重置任务、不恢复怪物、不复制物品或战利品。
  - 在 `c329546` 的 M1 历史验收时，死亡状态可使用 save v5 往返。
- **验收证据**:
  - recover 专项测试：59 项通过。
  - 全量 unittest：474 项通过。
  - compileall：通过。
  - original_demo 内容校验：通过。
  - `check_repo_safety.py --history`：通过。
  - `git diff --check`：通过。
  - 真实 CLI：加载受伤状态 → 攻击倒下 → 移动拒绝 → 死亡存档 → recover → 20/20 → 可继续游戏。
  - 验收时 Git：`main`、ahead 2 / behind 0、工作树干净、未 push。

## M2: 全场 typed stacks 物品数量系统 ✅

- **状态**: GPT-5.6-sol 已完成独立验收，结论 GO。
- **历史执行者**: Hermes agent。
- **验收者**: GPT-5.6-sol。
- **日期**: 2026-07-29。
- **封板前 Git**: `main`、`1ee0b30`、工作树干净、ahead/behind `0/0`、已同步远端；
  后续文档提交不自动 push。
- **强制完成条件**: 全部满足（详见下方）。
- **验收证据**:
  - 全量 unittest：530 项通过。
  - `tests.test_item_stacks`：56 项通过。
  - compileall、original_demo 内容校验、`check_repo_safety.py --history` 和
    `git diff --check`：通过。
  - 真实 CLI：数量拾取、受伤后 `use` ×2 恢复至 20/20、战斗掉落、丢弃和
    save/load：通过。
  - 内容物品增加 `stack_limit`，默认 1。
  - 房间、背包、战利品、对话奖励统一使用带正整数数量的 `ItemStack`。
  - 容量按占用栈位计算，不按物品单位数计算。
  - `take`、`use`、`drop` 支持可选数量，省略时为 1。
  - 数量操作原子执行。
  - 拒绝 0、负数、超栈上限和超容量。
  - save 升级至 v6。
  - 严格校验数量、重复栈、未知物品和装备数量。
  - v5 按版本规则明确拒绝，不做隐式迁移。

## M3: 三类任务系统

- **状态**: GPT-5.6-sol 已完成独立验收，结论 GO。
- **执行者**: Codex。
- **验收者**: GPT-5.6-sol。
- **独立验收封板**: 2026-07-29；实现提交 `dca629b`，唯一 P2 交接修正提交
  `5527faa`。聚焦复验确认 P2 已关闭，结论为无 findings。
- **已实现的强制契约**:
  - frozen tagged union 固定为 `monster_defeated.target_monster_id`、
    `reach_room.target_room_id`、`collect_item.target_item_id + required_quantity`；
    Schema 与 loader 拒绝跨分支字段和未知 kind。
  - `collect_item` 要求 `1 <= required_quantity <= stack_limit`，完成条件为背包目标
    栈数量 `>= required_quantity`。
  - `World` 统一接取、条件判断、一次性奖励和 `QuestOutcome`；同一次动作的跨 kind
    结果、经验和升级信息按 quest ID 字典序结算。
  - 进入触发房间、移动、拾取、击败怪物和成功发放对话物品奖励均进行幂等检查；接取时
    已满足条件会立即完成。
  - 主动作与任务结算使用局部内存事务；奖励失败会整体回滚，不留下重复奖励、物品、战利品
    或对话状态的半完成变更。
  - `World.move()` 保持返回 `Room`；`move_with_outcome()` 是 CLI 的加性结果路径。
  - `completed` 是奖励已发放的事实；`drop`、`use` 和 load 不撤销或补发。
  - save format 保持 v6，`QuestState` 仍只有 `completed`；load 只恢复状态、不重新接取、
    检查或发奖。内容包升至 0.4.0，旧 0.3.0 内容包存档按版本拒绝。
- **Codex 本地验证证据**:
  - 全量 unittest：540 项通过。
  - `tests.test_quest`：31 项通过，覆盖三分支契约、幂等、排序、四条事务回滚、对话奖励、
    CLI、v6 形状和读档不重算。
  - `tests.test_item_stacks`：56 项通过（M2 回归）。compileall、original_demo 校验、
    `check_repo_safety.py --history` 和 `git diff --check`：通过。
  - 仓库外临时存档目录 CLI：完成 collect/reach/monster 三类任务、战利品拾取、save、
    读档和状态恢复。
- **GPT-5.6-sol 独立验收证据**:
  - 540 项全量 unittest、31 项 M3 专项和 56 项 M2 stack 回归通过；compileall、
    original_demo 校验、历史安全扫描与 `git diff --check` 通过。
  - 仓库外 CLI 覆盖三类任务、战利品、save/load；复验后无 findings。

## M4: 强类型对话效果

- **状态**: GPT-5.6-sol 已完成联合 M4+M5 独立验收，结论 GO。
- **执行者**: Codex。
- **验收者**: GPT-5.6-sol。
- **已实现的强制契约**:
  - `DialogueOption.effects` 为必填、有序、frozen tagged union：`grant_item`、
    `grant_experience`、`accept_quest`、`set_flag`；旧 `grant_item` 字段不兼容且被拒绝。
  - loader/Schema 严格拒绝缺失或未知 `kind`、跨分支字段、错误类型、bool-as-int、非法引用、
    重复目标和多个经验效果。
  - `World.select_option()` 先预检整组效果，再在同一事务中按内容顺序执行；失败会回滚
    房间、怪物、玩家、金币、背包、装备、任务、flags 和活动对话，成功后才推进对话。
  - 显式 `accept_quest` 可提前接取并立即结算，已接取/完成会使整项选择失败；自动触发接取
    仍保持 M3 幂等语义。`set_flag` 是 World-owned upsert，缺失和 `false` 不混同。
  - `TalkOutcome.effect_outcomes` 和每个分支 outcome 为 frozen typed 数据；CLI 按效果顺序
    渲染且不重复任务/升级文本。save v7 严格保存 flags，load 不执行效果或重算任务。
- **Codex 本地验证证据**:
  - `tests.test_dialogue_effects`：12 项通过。
  - M3/M2 对话、任务、堆叠与 save 回归均通过；全量、CLI、安全和编译证据在本切片交接中记录。
- **GPT-5.6-sol 独立验收证据**:
  - 联合 M4+M5 聚焦复验无 findings；M4 effects 顺序、整组预检、重复接取原子拒绝、typed
    outcomes、flags 和即时任务结算均通过。
  - 25 项 M4/M5 专项、569 项全量测试、compileall、original_demo 校验、历史安全扫描、
    diff 检查和真实 CLI 通过；effects 不重放，v6 与旧内容包存档继续拒绝。

## M5: 固定金币商店

- **状态**: GPT-5.6-sol 已完成联合 M4+M5 独立验收，结论 GO；首次空栈买入超
  `stack_limit` 的 P1 已关闭。
- **执行者**: Codex。
- **验收者**: GPT-5.6-sol。
- **已实现的强制契约**:
  - `PlayerDefaults`/`Player.coins` 是非负整数；`ShopDefinition` 和
    `ShopListingDefinition` 是 frozen 内容定义，`shops.json` 对所有内容包必填。
  - 商店是一房间至多一个、固定价格、无限供应的有序目录；不创建 stock、补货、动态价格或
    任何可变商店存档状态。非堆叠目录物品参加既有跨来源唯一性检查。
  - `shop` 只读，`buy`/`sell` 支持默认和显式正整数数量、稳定 ID 或唯一名称。买入预检金币、
    容量、栈上限（包括新建空栈）和唯一性，并与 collect_item 奖励同事务回滚；卖出拒绝已装备
    物品且不撤销任务。
  - 倒下时可以查看 `shop`，不能买卖；所有交易路径保持活动对话并不修改目录。save v7 保存金币，
    商店从当前内容包恢复。
  - original_demo 为 0.6.0，初始 20 金币，`shop_chen_travel_goods` 在琉草小径以买 4 / 卖 2
    交易 `item_linglu_pill`。
- **Codex 本地修正验证证据**:
  - `tests.test_shop`：13 项通过；新增空栈 buy ×6 超栈上限拒绝，World 与 CLI 均保持状态
    不变。
  - 全量 unittest：569 项通过；compileall、original_demo 校验、历史安全扫描和 diff 检查通过。
  - 仓库外 CLI：拾取 3、卖出 3 后 buy ×6 被拒绝；金币保持 26、背包为空，save/load 成功。
- **GPT-5.6-sol 独立验收封板**:
  - `59ca3cd` 修正的新栈上限预检使非法栈无法写入；聚焦复验无 findings。
  - 该 GO 仅封板 M4+M5，不授权 M6 或其他功能开发。

## M6: Examine、帮助和错误反馈

- **状态**: GPT-5.6-sol 已完成独立验收，结论 GO、无 findings。
- **执行者**: Codex。
- **验收者**: GPT-5.6-sol。
- **强制完成条件**:
  - `examine` 成为公开命令，并与 `inspect` 兼容。
  - 可以查看当前可见的房间物品、背包物品、怪物、角色和当前房间摘要。
  - 查看操作保持只读。
  - 不暴露其他房间或尚未取得的奖励。
  - `help [command]` 显示语法、参数、上下文限制和死亡限制。
  - 参数错误、目标不存在、目标歧义、状态不允许返回稳定原因或用法文本。
  - 错误路径必须证明运行时状态不变。
- **Codex 本地实现与验证证据**:
  - `World.examine()` 返回 frozen item/monster/character tagged outcomes；只解析当前房间、
    背包和当前房间角色/怪物。跨类型同名或重复 ID 要求类型限定，同类型重名要求稳定 ID。
  - `inspect` 保持物品专用兼容；`CommandSpec` 同时驱动真实路由、别名、总帮助、
    `help [command]` 和死亡允许集合，DEC-0020 门禁顺序不变。
  - 22 项 M6、187 项聚焦和 591 项全量 unittest 通过；compileall、内容包校验、历史安全
    扫描、diff 检查及仓库外 CLI 通过。original_demo 保持 0.6.0，save 保持 v7。
- **GPT-5.6-sol 独立验收封板**:
  - 基线为 `53a071f`；相对 `f0acd3f` 的既定 11 文件范围一致，所有验收项通过、无 findings。
  - 验收覆盖 typed visible examine、`inspect` 兼容、`help [command]`、注册表/路由/死亡规则
    双向一致、死亡与对话边界、只读状态不变性，以及仓库外 CLI/save v7。
- **边界**: 跨类型歧义夹具只在测试内存构造；未修改 Schema、原创内容 JSON、内容包版本、
  save 契约或依赖。M7 未开始，仍须项目负责人另行明确授权；本次不授权 push。

## M7: 原创内容规模验收

- **状态**: 规划中。
- **强制完成条件** — original_demo 至少达到：
  - 8 个房间。
  - 4 只怪物。
  - 4 条任务。
  - 三类任务（`monster_defeated`、`reach_room`、`collect_item`）均有真实原创内容覆盖。
  - 至少一个对话效果改变经验、任务或 flag。
  - 至少一个堆叠物品。
  - 至少一个可实际买卖的商店。
  - 至少一个可复现的死亡/恢复流程。
- 内容扩容队列第一步：新增第二原创遭遇（房间 + 怪物 + 任务）。不得成为 M2。

## M8: 公共引擎完成独立审计

- **状态**: 未开始。
- **强制完成条件** — 只有 M1–M7 全部满足，并通过以下门槛，才能宣布公共引擎完成：
  - 全量 unittest。
  - 各里程碑专项失败不变性测试。
  - save/load 往返和非法输入矩阵。
  - 内容包校验。
  - compileall。
  - `check_repo_safety.py --history`。
  - 真实 CLI 主流程。
  - 8/4/4 原创内容规模。
  - 工作树、提交和远端状态可解释。
  - GPT-5.6-sol 独立复核真实差异和证据。
- M8 前只能称为"公共引擎开发中"或 `Conditional GO`。

---

## 安全边界：私有小说事实层

私有小说事实层**不属于** M1–M8 公共引擎路线。M8 完成后仍需项目负责人给出新的
明确授权。公共引擎完成状态不能自动推导为私有事实层授权。
