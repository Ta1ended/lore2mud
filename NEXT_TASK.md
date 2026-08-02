# Next Task

_Last updated: 2026-08-02（Runtime Campaign Foundation 实施完成，等待全新只读验收）_

## Single next action

在当前 runtime worktree `D:\MUD game kaifa\.codex-worktrees\runtime-campaign-foundation-v1`
（基线 `812a00f`，分支 `workstream/runtime-campaign-foundation-v1`）候选已形成单个提交；
把 `812a00f..HEAD` 交给全新只读 reviewer 输出 GO/REVISE。
独立 GO 前不得提交到 `main`、合并、push 或 release。另两个前置门同样等待 fresh review：
CampaignSpec v1 候选 `15f47ca`，以及私人 1-58 章 Canon 修正产物；三处全部 GO 后才能进入
公共整合与私人 1-58 Demo 制作。

## Completed evidence

- Runtime Campaign Foundation 修复 loader 必填字段语法后通过：382 项聚焦/回归测试、
  1333 项 full unittest（10 skip）、1323 项 full pytest（10 skip）、compileall 与
  Ruff、Pyright、original_demo 与两个 campaign fixture 内容校验、Draft 2020-12 Schema、
  history safety、fsck、桌面/390/320 浏览器交互与 save/load 检查均已完成；fresh 只读验收待派发。
- CampaignSpec v1 分支 `15f47ca` 已按第二轮 P2 修正（完成匹配场景必须出现在目标、精确阶段且
  不在互斥目标中），等待 fresh review。
- 私人 1-58 章 Canon 修正产物已就绪（446 source members、223 registry entities、
  58 sources、1021 claims），等待 fresh review 后才生成最终报告与 NarrativePlan。
- 公开仓库本轮未写入任何私人小说、章节、摘要、canon、游戏内容或图片；私人处理保持在私人工作区。

## Boundaries

- 未完成独立验收前：不整合 runtime/campaign-spec 到 `main`，不 push，不 release。
- 不读取第 59 章及以后，不把私人材料写入公开仓库。
