"""
测试两个方案的完整流程
================================================================================

方案A（稳健型）：
- 使用上周的完整周K数据
- 五步流程筛选股票
- 可选AI分析和新闻整合

方案B（激进型）：
- 第五步：只筛选价格和成交额
- 第六步：获取实时日K数据，拟合本周周K
- 权重分配：周一40%，周二30%，周三20%，周四10%，周五0%
- 根据成交量均线和偏离度筛选

================================================================================
"""

print("=" * 80)
print("测试两个方案的完整流程")
print("=" * 80)

# 测试方案A
print("\n\n" + "=" * 80)
print("方案A（稳健型）")
print("=" * 80)

try:
    from weekly_stock_selector_plan_a import run_weekly_selection_plan_a
    
    stocks_a, ai_results = run_weekly_selection_plan_a(
        max_stocks=10,  # 只处理前10只股票（测试用）
        enable_ai_analysis=False,  # 不启用AI分析（测试用）
        verbose=True
    )
    
    print(f"\n方案A最终选出 {len(stocks_a)} 只股票")
    
except Exception as e:
    print(f"\n方案A测试失败: {e}")
    import traceback
    traceback.print_exc()

# 测试方案B
print("\n\n" + "=" * 80)
print("方案B（激进型）")
print("=" * 80)

try:
    from weekly_stock_selector_plan_b import run_weekly_selection_plan_b
    
    stocks_b = run_weekly_selection_plan_b(
        max_stocks=10,  # 只处理前10只股票（测试用）
        verbose=True
    )
    
    print(f"\n方案B最终选出 {len(stocks_b)} 只股票")
    
except Exception as e:
    print(f"\n方案B测试失败: {e}")
    import traceback
    traceback.print_exc()

# 对比结果
print("\n\n" + "=" * 80)
print("结果对比")
print("=" * 80)

print(f"\n方案A（稳健型）：选出 {len(stocks_a) if 'stocks_a' in locals() else 0} 只股票")
print(f"方案B（激进型）：选出 {len(stocks_b) if 'stocks_b' in locals() else 0} 只股票")

print("\n" + "=" * 80)
print("测试完成！")
print("=" * 80)
