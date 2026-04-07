"""
完整的五步流程示例
================================================================================

步骤1: 获取全市场股票列表（包含上市时间）
步骤2: 筛选沪深主板、非ST、上市2年以上
步骤3: 获取周K数据（前复权、多线程）
步骤4: 筛选站上25周均线的股票
步骤5: 根据价格、成交额和成交量均线筛选

================================================================================
"""

from data_provider import DataFetcherManager
import pandas as pd
from typing import List, Dict, Any

def main():
    """完整的五步流程示例"""
    
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
    except Exception as e:
        print(f"✗ 步骤3失败: {e}")
        return
    
    # ========================================================================
    # 步骤4: 筛选站上25周均线的股票
    # ========================================================================
    print("\n" + "=" * 80)
    print("步骤4: 筛选站上25周均线的股票")
    print("=" * 80)
    
    passed_stocks_step4, stats_step4 = manager.filter_stocks_above_ma(
        weekly_data=weekly_data,
        ma_period=25,  # 25周均线
        min_data_points=30  # 至少30周数据
    )
    
    print(f"\n✓ 筛选完成:")
    print(f"  总数: {stats_step4['total']}")
    print(f"  通过: {stats_step4['passed']}")
    print(f"  失败: {stats_step4['failed']}")
    print(f"  通过率: {stats_step4['pass_rate']:.2f}%")
    
    # ========================================================================
    # 步骤5: 根据价格、成交额和成交量均线筛选
    # ========================================================================
    print("\n" + "=" * 80)
    print("步骤5: 根据价格、成交额和成交量均线筛选")
    print("=" * 80)
    print("  条件:")
    print("    - 价格: 3-70元")
    print("    - 成交额: >= 5亿")
    print("    - 5周成交量均线: 向上")
    print("    - 偏离度: -3% ~ 7%")
    
    passed_stocks_step5, stats_step5 = manager.filter_stocks_by_price_volume(
        weekly_data=weekly_data,
        passed_from_step4=passed_stocks_step4,
        min_price=3.0,
        max_price=70.0,
        min_amount=5e8,  # 5亿
        min_deviation=-3.0,
        max_deviation=7.0,
        min_data_points=65
    )
    
    print(f"\n✓ 筛选完成:")
    print(f"  总数: {stats_step5['total']}")
    print(f"  通过: {stats_step5['passed']}")
    print(f"  失败: {stats_step5['failed']}")
    print(f"  通过率: {stats_step5['pass_rate']:.2f}%")
    print(f"\n  失败原因:")
    print(f"    不在第四步: {stats_step5['reasons']['not_in_step4']}")
    print(f"    价格不符: {stats_step5['reasons']['price_out_of_range']}")
    print(f"    成交额不足: {stats_step5['reasons']['amount_too_low']}")
    print(f"    数据不足: {stats_step5['reasons']['insufficient_data']}")
    print(f"    MA5不向上: {stats_step5['reasons']['volume_ma5_not_rising']}")
    print(f"    偏离度不符: {stats_step5['reasons']['deviation_out_of_range']}")
    
    # 显示通过筛选的股票
    if passed_stocks_step5:
        print(f"\n  通过筛选的股票（按偏离度绝对值排序，前10只）:")
        for i, stock in enumerate(passed_stocks_step5[:10], start=1):
            print(f"    {i:2d}. {stock['code']}: "
                  f"价格={stock['close']:6.2f}元, "
                  f"成交额={stock['amount']/1e8:5.2f}亿, "
                  f"偏离度={stock['deviation']:5.2f}%")
    else:
        print("\n  没有股票通过筛选")
    
    # ========================================================================
    # 总结
    # ========================================================================
    print("\n" + "=" * 80)
    print("流程总结")
    print("=" * 80)
    print(f"步骤1: 获取全市场股票列表 → {len(all_stocks)} 只")
    print(f"步骤2: 筛选沪深主板、非ST、上市2年以上 → {len(filtered_stocks)} 只")
    print(f"步骤3: 获取周K数据（前复权、多线程） → {len(weekly_data)} 只成功")
    print(f"步骤4: 筛选站上25周均线 → {len(passed_stocks_step4)} 只通过")
    print(f"步骤5: 根据价格、成交额和成交量均线筛选 → {len(passed_stocks_step5)} 只通过")
    print("=" * 80)


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("周K线数据获取与筛选 - 完整五步流程")
    print("=" * 80)
    
    # 运行完整流程
    main()
