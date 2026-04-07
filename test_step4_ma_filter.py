"""
测试第四步：筛选站上25周均线的股票（使用模拟数据）
"""
from data_provider import DataFetcherManager
import pandas as pd
from datetime import datetime, timedelta

print("=" * 80)
print("测试第四步：筛选站上25周均线的股票")
print("=" * 80)

# 创建模拟数据
def create_mock_weekly_data(trend: str, weeks: int = 50) -> pd.DataFrame:
    """创建模拟的周K数据"""
    dates = [(datetime.now() - timedelta(weeks=weeks-i)).strftime('%Y-%m-%d') 
             for i in range(weeks)]
    
    if trend == 'up':
        # 上升趋势：价格从10涨到20
        closes = [10 + i * 0.2 for i in range(weeks)]
    elif trend == 'down':
        # 下降趋势：价格从20跌到10
        closes = [20 - i * 0.2 for i in range(weeks)]
    else:
        # 横盘：价格在15附近波动
        closes = [15 + (i % 5 - 2) * 0.5 for i in range(weeks)]
    
    df = pd.DataFrame({
        'date': dates,
        'open': closes,
        'high': [c * 1.02 for c in closes],
        'low': [c * 0.98 for c in closes],
        'close': closes,
        'volume': [1000000] * weeks,
        'amount': [10000000] * weeks,
        'pct_chg': [0] * weeks
    })
    
    return df

# 创建测试数据
weekly_data = {
    '600001': create_mock_weekly_data('up', 50),      # 上升趋势，应该通过
    '600002': create_mock_weekly_data('down', 50),    # 下降趋势，应该失败
    '600003': create_mock_weekly_data('sideways', 50), # 横盘，可能通过
    '600004': create_mock_weekly_data('up', 20),      # 数据不足，应该失败
    '600005': create_mock_weekly_data('up', 30),      # 刚好够数据，应该通过
}

print(f"\n创建了 {len(weekly_data)} 只股票的模拟数据:")
for code, df in weekly_data.items():
    print(f"  {code}: {len(df)} 周数据, 最新价={df.iloc[-1]['close']:.2f}")

# 初始化管理器
manager = DataFetcherManager()

# 步骤4: 筛选站上25周均线的股票
print("\n开始筛选...")
passed_stocks, stats = manager.filter_stocks_above_ma(
    weekly_data=weekly_data,
    ma_period=25,
    min_data_points=30
)

print(f"\n筛选结果:")
print(f"  - 总数: {stats['total']}")
print(f"  - 通过: {stats['passed']}")
print(f"  - 失败: {stats['failed']}")
print(f"  - 通过率: {stats['pass_rate']:.2f}%")
print(f"  - 失败原因:")
print(f"    * 数据不足: {stats['reasons']['insufficient_data']}")
print(f"    * 均线下方: {stats['reasons']['below_ma']}")

print(f"\n通过筛选的股票:")
for stock in passed_stocks:
    print(f"  {stock['code']}: "
          f"价格={stock['close']:.2f}, "
          f"MA25={stock['ma']:.2f}, "
          f"高出={stock['pct_above']:.2f}%, "
          f"数据点={stock['data_points']}")

# 验证结果
print("\n" + "=" * 80)
print("验证结果:")
print("=" * 80)

expected_passed = ['600001', '600003', '600005']  # 预期通过的股票
actual_passed = [s['code'] for s in passed_stocks]

print(f"预期通过: {expected_passed}")
print(f"实际通过: {actual_passed}")

if set(expected_passed) == set(actual_passed):
    print("✓ 测试通过！")
else:
    print("✗ 测试失败！")
    print(f"  缺失: {set(expected_passed) - set(actual_passed)}")
    print(f"  多余: {set(actual_passed) - set(expected_passed)}")

print("\n" + "=" * 80)
print("测试完成！")
print("=" * 80)
