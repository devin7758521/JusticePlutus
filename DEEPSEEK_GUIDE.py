# -*- coding: utf-8 -*-
"""
DeepSeek配置指南
================================================================================

DeepSeek API配置和使用说明

================================================================================
"""

# ==============================================================================
# 环境变量配置
# ==============================================================================

"""
在项目根目录创建 .env 文件，添加以下内容：

# 方式1：单Key配置
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx

# 方式2：多Key配置（轮换使用）
DEEPSEEK_API_KEYS=sk-xxx1,sk-xxx2,sk-xxx3

# 设置使用DeepSeek Reasoner作为主模型（推荐）
LITELLM_MODEL=deepseek/deepseek-reasoner

# 或者使用DeepSeek Chat（V3.1）
# LITELLM_MODEL=deepseek/deepseek-chat

# 或者使用channels配置（推荐）
LLM_CHANNELS=deepseek,gemini
LLM_DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
LLM_DEEPSEEK_MODELS=deepseek/deepseek-reasoner
"""

# ==============================================================================
# DeepSeek Thinking模式说明
# ==============================================================================

"""
DeepSeek的thinking模式可以增强推理能力：

1. 自动启用：当使用deepseek-reasoner或deepseek-chat模型时，代码会自动添加thinking参数
2. 推理增强：DeepSeek会进行深度思考，分析历史事件和因果关系
3. 适用场景：
   - 历史事件分析（如美国加息、海湾战争等）
   - 因果关系推理
   - 复杂逻辑判断
   - 多维度综合分析

DeepSeek Reasoner (R1) 特点：
- Chain of Thought (CoT) 推理
- 性能媲美OpenAI o1
- 显示思考过程
- 更强的推理能力

代码实现：
```python
from src.agent.llm_adapter import get_thinking_extra_body

# 自动添加thinking参数
extra = get_thinking_extra_body("deepseek-reasoner")
# extra = {"thinking": {"type": "enabled"}}
```
"""

# ==============================================================================
# AI分析能力
# ==============================================================================

"""
AI分析已经包含的功能：

1. 新闻检索 ✅
   - 近期重要新闻/公告摘要
   - 市场情绪分析
   - 相关热点话题

2. 技术分析 ✅
   - 均线系统分析
   - 量能分析
   - K线形态分析
   - 筹码结构分析

3. 基本面分析 ✅
   - 公司亮点/风险
   - 板块行业分析
   - 业绩预期分析

4. 推理分析 ✅（DeepSeek增强）
   - 历史事件回溯
   - 因果关系推理
   - 多维度综合分析
   - 风险评估

5. 操作建议 ✅
   - 买入/卖出信号
   - 仓位管理
   - 止损止盈位
   - 风控策略
"""

# ==============================================================================
# 使用示例
# ==============================================================================

"""
# 方案A（稳健型）
from weekly_stock_selector_plan_a import WeeklyStockSelectorPlanA

selector = WeeklyStockSelectorPlanA()
stocks, ai_results = selector.run_with_ai_analysis(
    max_stocks=100,
    enable_ai_analysis=True,      # 启用AI分析（使用DeepSeek）
    enable_news_search=True,       # 启用新闻搜索
    enable_push=True,              # 推送到企业微信
    verbose=True
)

# 方案B（激进型）
from weekly_stock_selector_plan_b import WeeklyStockSelectorPlanB

selector = WeeklyStockSelectorPlanB()
stocks, ai_results = selector.run_with_ai_analysis(
    max_stocks=100,
    enable_ai_analysis=True,      # 启用AI分析（使用DeepSeek）
    enable_news_search=True,       # 启用新闻搜索
    enable_push=True,              # 推送到企业微信
    verbose=True
)
"""

# ==============================================================================
# DeepSeek vs Gemini 对比
# ==============================================================================

"""
DeepSeek Reasoner (R1) 优势：
1. Thinking模式：深度推理能力更强（Chain of Thought）
2. 历史回溯：能够分析历史事件和因果关系
3. 中文理解：对中文语境理解更好
4. 成本更低：API调用成本比Gemini低
5. 性能媲美OpenAI o1
6. 显示思考过程：可以看到AI的推理过程

DeepSeek Chat (V3.1) 优势：
1. 速度快：响应速度比Reasoner快
2. 成本低：比Reasoner更便宜
3. 适合快速分析

Gemini优势：
1. 多模态：支持图像、视频等多模态输入
2. 知识库：知识更新更及时
3. 国际化：对国际市场理解更好

推荐配置：
- 主要使用DeepSeek Reasoner进行深度推理分析
- 备用DeepSeek Chat进行快速分析
- 备用Gemini进行国际市场分析
- 配置示例：
  LLM_CHANNELS=deepseek-reasoner,deepseek-chat,gemini
"""

# ==============================================================================
# 历史事件分析示例
# ==============================================================================

"""
DeepSeek可以分析的历史事件：

1. 宏观经济事件
   - 美国加息周期对A股的影响
   - 人民币汇率波动对出口企业的影响
   - 通胀数据对消费板块的影响

2. 地缘政治事件
   - 海湾战争对石油板块的影响
   - 贸易摩擦对科技板块的影响
   - 国际关系变化对相关行业的影响

3. 行业周期事件
   - 猪周期对养殖板块的影响
   - 半导体周期对芯片板块的影响
   - 新能源补贴政策对相关板块的影响

4. 公司事件
   - 重大并购重组
   - 业绩暴雷/超预期
   - 高管变动/股权激励

AI分析会自动结合这些历史事件进行推理分析。
"""

if __name__ == "__main__":
    print("=" * 80)
    print("DeepSeek配置指南")
    print("=" * 80)
    
    print("\n环境变量配置:")
    print("  DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx")
    print("  LITELLM_MODEL=deepseek/deepseek-reasoner")
    
    print("\nDeepSeek Reasoner (R1) 优势:")
    print("  ✓ Thinking模式：深度推理能力更强（Chain of Thought）")
    print("  ✓ 历史回溯：能够分析历史事件和因果关系")
    print("  ✓ 中文理解：对中文语境理解更好")
    print("  ✓ 成本更低：API调用成本比Gemini低")
    print("  ✓ 性能媲美OpenAI o1")
    print("  ✓ 显示思考过程：可以看到AI的推理过程")
    
    print("\nAI分析能力:")
    print("  ✓ 新闻检索")
    print("  ✓ 技术分析")
    print("  ✓ 基本面分析")
    print("  ✓ 推理分析（DeepSeek增强）")
    print("  ✓ 操作建议")
    
    print("\n历史事件分析示例:")
    print("  - 美国加息周期对A股的影响")
    print("  - 海湾战争对石油板块的影响")
    print("  - 猪周期对养殖板块的影响")
    print("  - 半导体周期对芯片板块的影响")
    
    print("\n" + "=" * 80)
