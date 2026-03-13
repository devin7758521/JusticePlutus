# JusticePlutus API 集成与 OpenClaw 交接说明

这份文档是**公开安全版**。

用途：

- 给新 session 快速说明当前项目接了哪些 API
- 给未来的 OpenClaw 自动接入提供清晰的环境变量映射
- 在项目公开前，避免把任何明文密钥提交进仓库

如果你在本机继续推进，还有一份**未纳入 git 的本地私有交接文档**：

- `docs/API_INVENTORY.private.md`

## 1. 当前已跑通的线上链路

当前 `JusticePlutus` 已验证通过的最小闭环是：

1. `GitHub Actions workflow_dispatch`
2. 输入 `STOCK_LIST` 或临时 `stocks`
3. 行情层获取 A 股数据
4. `Tavily` 搜索增强
5. `AIHubMix OpenAI-compatible API` 调用 `Gemini` 模型
6. `Telegram Bot API` 推送到群

当前已验证成功的多股联调 run：

- `https://github.com/Etherstrings/JusticePlutus/actions/runs/23063113248`

## 2. 分层 API 地图

### 2.1 LLM 层

这一层负责最终分析生成。

| 服务 | 当前状态 | 变量名 | 请求协议 | 官方文档 | 当前用途 |
|------|----------|--------|----------|----------|----------|
| AIHubMix | 已接入 | `OPENAI_API_KEY` `OPENAI_BASE_URL` `OPENAI_MODEL` | OpenAI-compatible | `https://docs.aihubmix.com/en` | 当前主 LLM 路线 |
| Gemini 直连 | 代码支持，未启用 | `GEMINI_API_KEY` `GEMINI_MODEL` | Gemini SDK / LiteLLM | `https://ai.google.dev` | 保留备用 |
| Anthropic | 代码支持，未启用 | `ANTHROPIC_API_KEY` `ANTHROPIC_MODEL` | LiteLLM / Anthropic API | `https://docs.anthropic.com` | 保留备用 |

当前线上实际使用：

- `OPENAI_BASE_URL=https://aihubmix.com/v1`
- `OPENAI_MODEL=gemini-flash-lite-latest`

### 2.2 搜索增强层

这一层负责提供新闻、舆情、风险、业绩、行业背景。

| 服务 | 当前状态 | 变量名 | 官方文档 | 当前用途 |
|------|----------|--------|----------|----------|
| Tavily | 已接入并验证 | `TAVILY_API_KEYS` | `https://docs.tavily.com/documentation/api-reference/endpoint/search` | 当前唯一启用搜索增强 |
| Bocha | 已保留配置位，未纳入当前执行路径 | `BOCHA_API_KEYS` | `https://open.bocha.cn/` | 预留中文搜索增强 |
| SerpAPI | 已保留配置位，未纳入当前执行路径 | `SERPAPI_API_KEYS` | `https://serpapi.com/search-api` | 预留补充搜索源 |

### 2.3 行情与技术面层

这一层负责日线、实时行情、技术指标、部分补充字段。

| 服务 | 当前状态 | 变量名 | 官方文档 / 来源 | 当前用途 |
|------|----------|--------|------------------|----------|
| Tushare | 已接入，但当前 token 权限不足以作为主数据源稳定使用 | `TUSHARE_TOKEN` | `https://tushare.pro/` | 首先尝试日线 / 实时 |
| Efinance | 已实际回退成功 | 无额外 key | `https://github.com/Micro-sheep/efinance` | 当前日线主要回退源 |
| Akshare | 代码支持 | 无额外 key | `https://github.com/akfamily/akshare` | 实时与备用数据源 |
| Tencent 实时接口 | 已实际用于补全字段 | 由 `REALTIME_SOURCE_PRIORITY` 控制 | 代码内直连 | 当前实时补充字段来源 |
| Sina 实时接口 | 代码支持 | 由 `REALTIME_SOURCE_PRIORITY` 控制 | 代码内直连 | 备用实时源 |
| YFinance | 代码支持 | 无额外 key | `https://pypi.org/project/yfinance/` | 美股/美股指数备用 |

### 2.4 通知层

| 服务 | 当前状态 | 变量名 | 官方文档 | 当前用途 |
|------|----------|--------|----------|----------|
| Telegram Bot API | 已接入并验证 | `TELEGRAM_BOT_TOKEN` `TELEGRAM_CHAT_ID` | `https://core.telegram.org/bots/api` | 当前唯一已验证通知渠道 |
| 企业微信 | 代码支持，未启用 | `WECHAT_WEBHOOK_URL` | `https://developer.work.weixin.qq.com/` | 预留 |
| 飞书 | 代码支持，未启用 | `FEISHU_WEBHOOK_URL` | `https://open.feishu.cn/` | 预留 |
| Email | 代码支持，未启用 | `EMAIL_*` | SMTP | 预留 |
| PushPlus | 代码支持，未启用 | `PUSHPLUS_TOKEN` | `https://www.pushplus.plus/` | 预留 |
| Server酱3 | 代码支持，未启用 | `SERVERCHAN3_SENDKEY` | `https://sc3.ft07.com/` | 预留 |
| Discord | 代码支持，未启用 | `DISCORD_*` | `https://discord.com/developers/docs/intro` | 预留 |
| 自定义 Webhook | 代码支持，未启用 | `CUSTOM_WEBHOOK_*` | 目标服务自定义 | 预留 |

## 3. 当前 GitHub Actions 变量映射

### 3.1 必需 Secrets

| Secret 名 | 作用 |
|-----------|------|
| `OPENAI_API_KEY` | AIHubMix key |
| `TAVILY_API_KEYS` | Tavily 搜索增强 |
| `TELEGRAM_BOT_TOKEN` | Telegram 机器人发消息 |
| `TUSHARE_TOKEN` | A 股数据增强入口 |

### 3.2 必需 Variables

| Variable 名 | 当前建议值 | 作用 |
|-------------|------------|------|
| `OPENAI_BASE_URL` | `https://aihubmix.com/v1` | AIHubMix OpenAI-compatible 接口 |
| `OPENAI_MODEL` | `gemini-flash-lite-latest` | 当前已验证可用模型 |
| `TELEGRAM_CHAT_ID` | 目标群 ID | Telegram 推送目标 |
| `STOCK_LIST` | 例如 `600519,000001,300750` | 默认股票列表 |
| `MAX_WORKERS` | `1` | 确保顺序执行 |
| `REPORT_TYPE` | `simple` | 保持当前单股推送格式 |
| `ENABLE_CHIP_DISTRIBUTION` | `false` | 关闭不稳定筹码接口 |

## 4. OpenClaw 自动接入建议

如果在新 session 里做 OpenClaw 自动接入，建议先按“能力包”接入，不要直接把整仓库当作 Skill。

推荐接入边界：

- 输入：股票代码列表
- 执行：行情获取 + 搜索增强 + LLM 分析
- 输出：Markdown / JSON
- 可选：Telegram 推送

OpenClaw Skill 需要至少声明这些环境变量：

```yaml
metadata:
  openclaw:
    requires:
      env:
        - OPENAI_API_KEY
        - OPENAI_BASE_URL
        - OPENAI_MODEL
        - TAVILY_API_KEYS
        - TUSHARE_TOKEN
        - TELEGRAM_BOT_TOKEN
        - TELEGRAM_CHAT_ID
      bins:
        - python
    primaryEnv: OPENAI_API_KEY
```

推荐给 OpenClaw 的调用入口：

```powershell
python -m daily_stock_pipeline run --stocks 600519
```

如果需要只生成结果不推送：

```powershell
python -m daily_stock_pipeline run --stocks 600519 --no-notify
```

## 5. 项目公开前的安全要求

如果后续要把仓库公开，必须先做这些动作：

1. 旋转全部已有密钥
- AIHubMix
- Telegram Bot Token
- Tavily
- Bocha
- SerpAPI
- Tushare Token

2. 确保仓库中不包含任何明文密钥
- 当前本公开文档已避免记录明文
- 不要把 `docs/API_INVENTORY.private.md` 提交

3. 检查 GitHub Secrets / Variables 配置是否与 README 一致

4. 确保公开文档只记录：
- 变量名
- 获取地址
- 当前接线路线
- 不记录真实密钥

## 6. 当前确认过的运行行为

### 单股运行

- 会生成：
  - `stocks/<code>.md`
  - `stocks/<code>.json`
  - `summary.md`
  - `summary.json`
  - `run_meta.json`
- Telegram 会收到单股即时消息

### 多股运行

当前已确认：

- 多股情况下是**多条单股即时推送**
- 不是一条大汇总消息

已经验证通过的 3 股联调输入：

```text
600519,000001,300750
```

## 7. 相关文档

- [快速开始与分层架构](QUICKSTART_ARCHITECTURE.md)
- [OpenClaw Skill TODO](TODO_OPENCLAW_SKILL.md)
