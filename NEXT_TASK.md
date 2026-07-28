# Next Task

_Last updated: 2026-07-28_

## Status
等待项目负责人复核今日三段交付的公开安全与原创试玩证据，再选择下一项纵向功能。

当前 v5 存档已在构造替换世界前拒绝顶层、内容包、玩家、房间与怪物对象的未知字段；
原创演示内容包 v0.2.6 已加入经严格校验的一次性对话铜牌奖励，并要求持有该铜牌才能从
琉草小径向西返回。出口门禁不消耗物品、不新增存档字段；恢复时仍以实时远端为准。

## Single next action
独立复核本次门禁出口提交的公共安全扫描、完整测试、内容包校验和原创试玩证据；确认
远端 `main` 与本地预期提交一致，再由项目负责人选择下一项纵向功能。

## Acceptance criteria

- `python scripts/check_repo_safety.py --history` 无违规；
- 完整测试、编译、`lore2mud validate` 与“无铜牌拒绝 / 对话获得铜牌后通行”的原创 CLI 冒烟均通过；
- `git diff --check` 与 `git status --short --branch` 无意外差异；
- 四个交接文件只陈述已验证事实，且本文件仍只有上述一个下一动作。
