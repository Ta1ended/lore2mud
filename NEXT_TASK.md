# Next Task

_Last updated: 2026-07-28_

## Status
持有物品门禁、`look` 状态展示与 `inspect` 已完成。`save [槽位]` / `load [槽位]` 无参数时
兼容 `default.json`；命名槽位只允许 1–32 位小写 ASCII 字母、数字、`-`、`_`，必须以字母或
数字开头，并拒绝路径、扩展名与 Windows 保留设备名。槽位仅选择保存目录内文件，非法保存
不会写入，非法读档不会替换当前世界。写入端文件系统 `OSError` 现转换为带 cause 的
`SaveLoadError`，CLI 返回“存档失败”而不逃逸异常。内容包保持 v0.2.6，存档格式保持 v5。
完整 389 项测试与 90 项聚焦 save/save-slot 回归、安全历史扫描、编译、内容包校验和真实
双槽位 CLI 试玩均已通过。

Sol 审计基线 `2ecead1` 比本地 `origin/main` 引用 `6c13fca` 领先两个提交。审计结论为
`CONDITIONAL GO`，其唯一整改项已在当前本地切片完成；尚未刷新 GitHub 服务器状态，
也未自动推送。

项目负责人提供的 GPT-5.6-sol 审计仅检查公开仓库和原创演示，未读取私有小说资料。
它报告 43 个 dangling blob，但未读取内容；可达历史安全扫描不覆盖这些不可达对象。

## Single next action
刷新远端后，如 `origin/main` 仍精确为 `6c13fca`，由项目负责人使用 GitHub Desktop
对当前本地 `main` 执行普通快进发布；若远端已变动、分支受保护或状态不干净，立即停止
并重新审查，不使用 force push。

## Acceptance criteria

- 先刷新远端和工作树；只在 `origin/main` 仍为 `6c13fca`、本地工作树干净且远端仅可
  快进时发布；
- 发布后验证 `git status --short --branch` 不再显示 ahead/behind，并再次运行可达历史
  安全检查；
- 绝不读取、复制或扫描私有小说正文、摘要、canon 或改编内容；
- 四个交接文件只陈述已验证事实，且本文件仍只有上述一个下一动作。
