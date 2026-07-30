# Codex 全程工作流（GPT-5.6-sol）

## 角色分工

Codex 是唯一活动开发 Agent，方案、实现、测试、交接与复验会话全部选择
GPT-5.6-sol。Hermes 不再承担新切片；既有提交和决定中的历史归属不改写。
项目负责人负责批准切片范围和 push，不再负责在不同 Agent 之间人工转交 prompt。

职责仍按阶段分离：实现任务负责交付一个经确认的纵向切片；需要独立验收时，
由新的 Codex 复验任务或干净上下文只读核对真实差异、测试、安全检查和试玩证据。
实现上下文的完成报告不能单独构成 GO；独立复验未完成时必须记录为 pending。

模型输出、小说提取结果和玩家输入都不可信，必须经过显式校验。任何 Agent 都不得
直接用自然语言输出修改玩家状态。本地提交不自动 push。

## 每次任务的起点

Codex 按顺序阅读：

1. `PROJECT_MEMORY.md`
2. `PROJECT_STATE.md`
3. `NEXT_TASK.md`
4. `AGENTS.md`
5. `CHANGELOG.md` 的 `Unreleased`
6. 相关模块、测试和文档

再报告当前数据流、文件范围、明确不改的模块、风险和验证方案。项目负责人明确
授权切片后，Codex 才开始修改。若交接文件与代码、测试或 Git 冲突，以当前仓库
证据为准并修正交接文件。

## 执行与验收

- 每次只实现一个可测试的纵向功能；不顺手重构或扩张范围。
- 数据结构变更同时更新加载器、Schema、原创演示、测试和格式文档。
- 状态失败路径必须在状态写入前拒绝，并有场景测试证明不变性。
- 提交前运行完整单元测试、`python scripts/check_repo_safety.py --history`、
  编译检查、内容包 `validate` 和与改动相符的 CLI 冒烟。
- 完成时同步 `PROJECT_MEMORY.md`、`PROJECT_STATE.md`、`NEXT_TASK.md` 和
  `CHANGELOG.md`，只记载已验证的事实；`NEXT_TASK.md` 只能保留一个下一任务。
- 完成报告以一个自包含的 `text` fenced code block 结束，包含基线、唯一任务、
  文件范围、风险、验证结果和下一动作。

## 可复制任务模板

```text
请使用 GPT-5.6-sol 读取 AGENTS.md、PROJECT_MEMORY.md、PROJECT_STATE.md、
NEXT_TASK.md、CHANGELOG.md 的 Unreleased 及相关代码和测试，先不要修改。

目标：<一个可验证的纵向切片>
不做：<明确排除项>

请先报告数据流、文件范围、状态/兼容风险和测试计划。经项目负责人确认后由
Codex 实施。完成前运行完整测试、历史安全检查、编译、内容校验和相关 CLI
冒烟；最后更新四个交接文件并提供证据。需要独立验收时，另开 Codex
GPT-5.6-sol 复验任务，只读检查基线到实施提交并给出 GO/REVISE。
```
