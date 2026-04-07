"""
测试完整的四步流程：
步骤1: 获取全市场股票列表
步骤2: 筛选沪深主板、非ST、上市2年以上
步骤3: 获取周K数据（前复权、多线程）
步骤4: 筛选站上25周均线的股票
"""
from data_provider import DataFetcherManager
import pandas as pd

print("=" * 80)
print("完整四步流程测试")
print("=" * 80)

# 初始化管理器
manager = DataFetcherManager()

# 步骤1: 获取全市场股票列表
print("\n【步骤1】获取全市场股票列表...")
try:
    all_stocks, source1 = manager.get_all_stock_list_with_failover()
    print(f"✓ 成功获取 {len(all_stocks)} 只股票（数据源: {source1}）")
except Exception as e:
    print(f"✗ 步骤1失败: {e}")
    exit(1)

# 步骤2: 筛选沪深主板、非ST、上市2年以上
print("\n【步骤2】筛选沪深主板、非ST、上市2年以上...")
filtered_stocks = manager.filter_main_board_stocks(all_stocks)
print(f"✓ 筛选后剩余 {len(filtered_stocks)} 只股票")

# 为了测试，只取前10只股票
test_stocks = filtered_stocks[:10]
stock_codes = [stock['code'] for stock in test_stocks]
print(f"\n为了测试，只获取前 {len(stock_codes)} 只股票的周K数据")

# 步骤3: 获取周K数据（前复权、多线程）
print("\n【步骤3】获取周K数据（前复权、多线程）...")
try:
    weekly_data, source3 = manager.get_weekly_data_batch_with_failover(
        stock_codes=stock_codes,
        weeks=104,  # 2年
        max_workers=5
    )
    print(f"✓ 成功获取 {len(weekly_data)} 只股票的周K数据（数据源: {source3}）")
except Exception as e:
    print(f"✗ 步骤3失败: {e}")
    exit(1)

# 显示部分数据
if weekly_data:
    sample_code = list(weekly_data.keys())[0]
    sample_df = weekly_data[sample_code]
    print(f"\n示例数据 [{sample_code}]:")
    print(sample_df.tail(5))

# 步骤4: 筛选站上25周均线的股票
print("\n【步骤4】筛选站上25周均线的股票...")
passed_stocks, stats = manager.filter_stocks_above_ma(
    weekly_data=weekly_data,
    ma_period=25,
    min_data_points=30
)

print(f"\n✓ 筛选完成:")
print(f"  - 总数: {stats['total']}")
print(f"  - 通过: {stats['passed']}")
print(f"  - 失败: {stats['failed']}")
print(f"  - 通过率: {stats['pass_rate']:.2f}%")
print(f"  - 失败原因:")
print(f"    * 数据不足: {stats['reasons']['insufficient_data']}")
print(f"    * 均线下方: {stats['reasons']['below_ma']}")

# 显示通过筛选的股票
if passed_stocks:
    print(f"\n站上25周均线的股票（按高出百分比排序）:")
    for i, stock in enumerate(passed_stocks[:10], start=1):
        print(f"  {i}. {stock['code']}: "
              f"价格={stock['close']:.2f}, "
              f"MA25={stock['ma']:.2f}, "
              f"高出={stock['pct_above']:.2f}%, "
              f"数据点={stock['data_points']}")
else:
    print("\n没有股票站上25周均线")

print("\n" + "=" * 80)
print("测试完成！")
print("=" * 80)
