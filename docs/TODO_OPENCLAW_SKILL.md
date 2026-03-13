# TODO: OpenClaw Skill 化

后续单开 session 处理，不和当前可运行版联调任务混在一起。

## 目标

- 将 JusticePlutus 的“股票分析能力”重构为 OpenClaw Skill
- 不直接把整个仓库当作 Skill 发布
- 拆出适合 Skill 的最小能力包

## 待办

1. 明确 Skill 边界
- 输入：单股票 / 多股票 / 是否允许群发
- 输出：Markdown / JSON / Telegram 推送
- 是否包含搜索增强

2. 设计 Skill 目录结构
- `SKILL.md`
- `scripts/`
- `references/`

3. 从现有项目中提取最小可复用执行逻辑
- 行情获取
- 搜索增强
- LLM 分析
- Telegram 推送

4. 设计 OpenClaw Skill metadata
- `metadata.openclaw.requires.env`
- `primaryEnv`
- 所需二进制与运行条件

5. 准备发布与演示文档
- 本地调用示例
- OpenClaw 调用方式
- 错误处理说明
