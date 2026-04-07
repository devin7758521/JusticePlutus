"""
测试固定五步流程
"""
from weekly_stock_selector import run_weekly_selection

print("=" * 80)
print("测试固定五步流程")
print("=" * 80)

# 运行选股（测试模式：只处理前10只股票）
stocks = run_weekly_selection(
    max_stocks=10,  # 只处理前10只股票（测试用）
    verbose=True
)

print(f"\n\n最终选出 {len(stocks)} 只股票")
