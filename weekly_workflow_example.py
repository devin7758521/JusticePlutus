"""
周K线数据获取与筛选 - 完整四步流程使用说明
================================================================================

本模块实现了完整的周K线数据获取和筛选流程，包含四个步骤：

步骤1: 获取全市场股票列表（包含上市时间）
步骤2: 筛选沪深主板、非ST、上市2年以上
步骤3: 获取周K数据（前复权、多线程）
步骤4: 筛选站上25周均线的股票

================================================================================
"""

from data_provider import DataFetcherManager
import pandas as pd
from typing import List, Dict, Any

def main():
    """完整的四步流程示例"""
    
    # 初始化管理器
    manager = DataFetcherManager()
    
    # ========================================================================
    # 步骤1: 获取全市场股票列表
    # ========================================================================
    print("\n" + "=" * 80)
    print("步骤1: 获取全市场股票列表")
    print("=" * 80)
    
    try:
        all_stocks, source = manager.get_all_stock_list_with_failover()
        print(f"✓ 成功获取 {len(all_stocks)} 只股票")
        print(f"  数据源: {source}")
        print(f"  示例: {all_stocks[:3]}")
    except Exception as e:
        print(f"✗ 步骤1失败: {e}")
        return
    
    # ========================================================================
    # 步骤2: 筛选沪深主板、非ST、上市2年以上
    # ========================================================================
    print("\n" + "=" * 80)
    print("步骤2: 筛选沪深主板、非ST、上市2年以上")
    print("=" * 80)
    
    filtered_stocks = manager.filter_main_board_stocks(all_stocks)
    print(f"✓ 筛选后剩余 {len(filtered_stocks)} 只股票")
    print(f"  过滤掉 {len(all_stocks) - len(filtered_stocks)} 只股票")
    print(f"  示例: {filtered_stocks[:3]}")
    
    # ========================================================================
    # 步骤3: 获取周K数据（前复权、多线程）
    # ========================================================================
    print("\n" + "=" * 80)
    print("步骤3: 获取周K数据（前复权、多线程）")
    print("=" * 80)
    
    # 提取股票代码
    stock_codes = [stock['code'] for stock in filtered_stocks]
    
    # 为了演示，只取前20只股票
    test_codes = stock_codes[:20]
    print(f"为了演示，只获取前 {len(test_codes)} 只股票")
    
    try:
        weekly_data, source = manager.get_weekly_data_batch_with_failover(
            stock_codes=test_codes,
            weeks=104,  # 2年数据
            max_workers=5  # 5个线程并发
        )
        print(f"✓ 成功获取 {len(weekly_data)} 只股票的周K数据")
        print(f"  数据源: {source}")
        
        # 显示示例数据
        if weekly_data:
            sample_code = list(weekly_data.keys())[0]
            sample_df = weekly_data[sample_code]
            print(f"\n  示例数据 [{sample_code}]:")
            print(f"  数据点: {len(sample_df)} 周")
            print(f"  最新5周:")
            print(sample_df.tail(5).to_string(index=False))
    except Exception as e:
        print(f"✗ 步骤3失败: {e}")
        return
    
    # ========================================================================
    # 步骤4: 筛选站上25周均线的股票
    # ========================================================================
    print("\n" + "=" * 80)
    print("步骤4: 筛选站上25周均线的股票")
    print("=" * 80)
    
    passed_stocks, stats = manager.filter_stocks_above_ma(
        weekly_data=weekly_data,
        ma_period=25,  # 25周均线
        min_data_points=30  # 至少30周数据
    )
    
    print(f"\n✓ 筛选完成:")
    print(f"  总数: {stats['total']}")
    print(f"  通过: {stats['passed']}")
    print(f"  失败: {stats['failed']}")
    print(f"  通过率: {stats['pass_rate']:.2f}%")
    print(f"\n  失败原因:")
    print(f"    数据不足: {stats['reasons']['insufficient_data']}")
    print(f"    均线下方: {stats['reasons']['below_ma']}")
    
    # 显示通过筛选的股票（前10只）
    if passed_stocks:
        print(f"\n  站上25周均线的股票（按高出百分比排序，前10只）:")
        for i, stock in enumerate(passed_stocks[:10], start=1):
            print(f"    {i:2d}. {stock['code']}: "
                  f"价格={stock['close']:8.2f}, "
                  f"MA25={stock['ma']:8.2f}, "
                  f"高出={stock['pct_above']:6.2f}%, "
                  f"数据点={stock['data_points']}")
    else:
        print("\n  没有股票站上25周均线")
    
    # ========================================================================
    # 总结
    # ========================================================================
    print("\n" + "=" * 80)
    print("流程总结")
    print("=" * 80)
    print(f"步骤1: 获取全市场股票列表 → {len(all_stocks)} 只")
    print(f"步骤2: 筛选沪深主板、非ST、上市2年以上 → {len(filtered_stocks)} 只")
    print(f"步骤3: 获取周K数据（前复权、多线程） → {len(weekly_data)} 只成功")
    print(f"步骤4: 筛选站上25周均线 → {len(passed_stocks)} 只通过")
    print("=" * 80)


def custom_ma_filter_example():
    """自定义均线筛选示例"""
    
    manager = DataFetcherManager()
    
    # 获取数据（简化流程）
    all_stocks, _ = manager.get_all_stock_list_with_failover()
    filtered_stocks = manager.filter_main_board_stocks(all_stocks)
    stock_codes = [s['code'] for s in filtered_stocks[:50]]
    weekly_data, _ = manager.get_weekly_data_batch_with_failover(
        stock_codes=stock_codes,
        weeks=104,
        max_workers=5
    )
    
    # 自定义均线筛选
    # 示例1: 筛选站上20周均线的股票
    print("\n筛选站上20周均线的股票:")
    passed_20, stats_20 = manager.filter_stocks_above_ma(
        weekly_data=weekly_data,
        ma_period=20,
        min_data_points=25
    )
    print(f"  通过: {len(passed_20)} 只")
    
    # 示例2: 筛选站上60周均线的股票
    print("\n筛选站上60周均线的股票:")
    passed_60, stats_60 = manager.filter_stocks_above_ma(
        weekly_data=weekly_data,
        ma_period=60,
        min_data_points=70
    )
    print(f"  通过: {len(passed_60)} 只")


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("周K线数据获取与筛选 - 完整四步流程")
    print("=" * 80)
    
    # 运行完整流程
    main()
    
    # 运行自定义均线筛选示例
    # custom_ma_filter_example()
