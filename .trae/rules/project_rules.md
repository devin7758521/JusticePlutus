---
alwaysApply: false
description: 
---
# JusticePlutus 项目规则

## 🎯 核心配置（必须记住）

### 1. Baostock数据源优先级
- **优先级：-1**（必须优先于Efinance）
- **位置：** `data_provider/weekly_fetcher.py` 第736行
- **原因：** Baostock数据更稳定，应该优先使用
- **验证方法：** 检查 `priority = -1` 是否存在

### 2. 企业微信推送配置
- **环境变量：** `WECHAT_WORK_WEBHOOK` 或 `WECHAT_WEBHOOK_URL`
- **配置位置：** GitHub Secrets
- **推送格式：** text（不是markdown）
- **推送时机：**
  - 启动时：`push_workflow_start()`
  - 完成时：`push_workflow_complete()`

### 3. Python字节码缓存问题
- **问题：** GitHub Actions可能使用旧的字节码缓存
- **解决方案：**
  1. 环境变量：`PYTHONDONTWRITEBYTECODE=1`
  2. 代码中：`sys.dont_write_bytecode = True`
  3. 清除缓存：`find . -type d -name __pycache__ -exec rm -rf {} +`
  4. 重新加载模块：删除sys.modules中的相关模块

### 4. 股票代码格式
- **标准格式：** 6位数字（如 "000001"）
- **错误格式：** 带后缀（如 "000001.SZ"）
- **处理方法：** 使用 `normalize_stock_code()` 函数

---

## 🚨 常见问题和解决方案

### 问题1：Baostock优先级显示错误（P3而不是P-1）
**原因：** Python字节码缓存导致使用旧代码
**解决：**
1. 检查workflow中是否设置了 `PYTHONDONTWRITEBYTECODE=1`
2. 检查代码中是否有 `sys.dont_write_bytecode = True`
3. 检查是否清除了 `__pycache__` 目录

### 问题2：企业微信推送未收到
**检查步骤：**
1. 确认GitHub Secrets中配置了 `WECHAT_WORK_WEBHOOK`
2. 确认webhook URL格式正确
3. 查看workflow日志中的推送状态
4. 测试webhook：运行 `python test_push_config.py`

### 问题3：股票代码格式错误
**症状：** 日志显示 "股票代码显示可能错误"
**解决：**
1. 检查 `BaostockWeeklyFetcher.get_all_stock_list()` 是否调用了 `normalize_stock_code()`
2. 检查 `EfinanceWeeklyFetcher` 是否去除了 `.SZ/.SH` 后缀

### 问题4：GitHub推送失败
**原因：** 网络连接问题
**解决方案：**
1. 等待网络恢复后重试
2. 使用GitHub API推送（需要GITHUB_TOKEN）
3. 使用SSH方式推送

---

## 📝 代码规范

### 1. 日志输出
- **启动推送：** 必须在workflow开始时调用
- **进度显示：** 筛选步骤要显示百分比
- **完成推送：** 必须在workflow结束时调用

### 2. 数据源优先级
```
BaostockWeeklyFetcher: P-1 (最高优先级)
EfinanceWeeklyFetcher: P0
AkshareWeeklyFetcher: P1
TushareWeeklyFetcher: P2
PytdxWeeklyFetcher: P2
YfinanceWeeklyFetcher: P4
```

### 3. 列名映射
- **Efinance返回中文列名：** 必须映射为英文
- **映射规则：**
  - '日期' -> 'date'
  - '开盘' -> 'open'
  - '收盘' -> 'close'
  - '最高' -> 'high'
  - '最低' -> 'low'
  - '成交量' -> 'volume'
  - '成交额' -> 'amount'

---

## 🔍 验证清单

每次修改后必须验证：

1. ✅ Baostock优先级是否为 -1
2. ✅ 企业微信推送是否正常
3. ✅ 股票代码格式是否正确
4. ✅ 字节码缓存是否已禁用
5. ✅ 列名映射是否完整

---

## 📚 重要文件位置

| 文件 | 用途 | 关键行号 |
|------|------|---------|
| `data_provider/weekly_fetcher.py` | 数据源配置 | 736 (Baostock优先级) |
| `weekly_push.py` | 企业微信推送 | - |
| `weekly_stock_selector_plan_a.py` | 主流程 | 96 (启动推送) |
| `.github/workflows/weekly_selection_plan_a.yml` | GitHub Actions配置 | 89 (清除缓存) |

---

## ⚠️ 注意事项

1. **不要大改代码：** 小步迭代，避免引入新错误
2. **保持日志清晰：** 方便排查问题
3. **验证GitHub Actions：** 每次修改后检查workflow日志
4. **检查字节码缓存：** 确保使用最新代码
5. **使用Skills工具：** 遇到问题时，优先使用 `find-skills` 或其他相关skills工具来解决问题

---

## 🎓 学习要点

### GitHub Actions字节码缓存问题
- **现象：** 代码已更新，但运行时还是旧代码
- **原因：** Python会缓存编译后的字节码（.pyc文件）
- **专业解决：**
  1. 环境变量：`PYTHONDONTWRITEBYTECODE=1`
  2. 代码中：`sys.dont_write_bytecode = True`
  3. 清除缓存：删除所有 `__pycache__` 目录
  4. 重新加载：删除 `sys.modules` 中的相关模块

### 企业微信Webhook推送
- **格式：** text格式（不是markdown）
- **URL：** 需要在GitHub Secrets中配置
- **测试：** 使用 `test_push_config.py` 验证配置

---

**最后更新：** 2026-04-08
**维护者：** AI Assistant
