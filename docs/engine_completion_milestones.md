# Engine Completion Milestones

_Last updated: 2026-07-29（M3 已由 GPT-5.6-sol 独立验收 GO）_

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

- **状态**: 规划中。
- **强制完成条件**:
  - 对话选项使用有序 typed effects 列表，不使用通用未校验字典。
  - 首批效果为：`grant_experience`、`accept_quest`、`set_flag`。
  - 所有效果先校验，再原子执行。
  - 任一效果失败时，对话位置、玩家、任务、背包和 flags 均不改变。
  - flags 使用稳定 ID 和布尔值，并进入存档。
  - `accept_quest` 不得重复创建已接受或已完成任务。
  - 对话效果不能绕过 World 的任务、经验和状态规则。

## M5: 固定金币商店

- **状态**: 规划中。
- **强制完成条件**:
  - Player 增加非负整数金币。
  - 新增强类型 `ShopDefinition` 和 `shops.json`。
  - 商店使用内容包定义的确定性买卖价格。
  - 商店库存为固定目录，不增加随机库存或额外 mutable stock。
  - 买卖默认一个单位，也支持堆叠数量。
  - 金币、物品数量和容量必须在状态变化前全部检查。
  - 金币进入存档，存档版本按实际字段升级。
  - original_demo 至少有一个可以实际买卖的原创商店。

## M6: Examine、帮助和错误反馈

- **状态**: 规划中。
- **强制完成条件**:
  - `examine` 成为公开命令，并与 `inspect` 兼容。
  - 可以查看当前可见的房间物品、背包物品、怪物、角色和当前房间摘要。
  - 查看操作保持只读。
  - 不暴露其他房间或尚未取得的奖励。
  - `help [command]` 显示语法、参数、上下文限制和死亡限制。
  - 参数错误、目标不存在、目标歧义、状态不允许返回稳定原因或用法文本。
  - 错误路径必须证明运行时状态不变。

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
