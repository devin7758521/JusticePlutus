# -*- coding: utf-8 -*-
"""
测试周K线数据获取功能 - 简化版（只测试步骤1和步骤2）
"""

import logging
from data_provider import DataFetcherManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_steps_1_and_2():
    """测试步骤1和步骤2"""
    print("\n" + "=" * 80)
    print("步骤1: 获取全市场股票列表（故障切换）")
    print("=" * 80)
    
    manager = DataFetcherManager()
    
    try:
        stock_list, source = manager.get_all_stock_list_with_failover()
        print(f"✅ 成功从 [{source}] 获取到 {len(stock_list)} 只股票")
        
        if stock_list:
            print("\n前10只股票：")
            for i, stock in enumerate(stock_list[:10], 1):
                print(f"  {i}. {stock['code']} - {stock['name']} - 上市日期: {stock.get('list_date', 'N/A')}")
        
        print("\n" + "=" * 80)
        print("步骤2: 筛选沪深主板、非ST、上市2年以上")
        print("=" * 80)
        
        filtered_stocks = manager.filter_main_board_stocks(stock_list)
        print(f"✅ 筛选完成: {len(filtered_stocks)} 只股票")
        
        if filtered_stocks:
            print("\n前10只筛选后的股票：")
            for i, stock in enumerate(filtered_stocks[:10], 1):
                print(f"  {i}. {stock['code']} - {stock['name']} - 上市日期: {stock.get('list_date', 'N/A')}")
        
        print(f"\n统计：")
        print(f"  原始股票数量: {len(stock_list)}")
        print(f"  筛选后数量: {len(filtered_stocks)}")
        print(f"  过滤掉: {len(stock_list) - len(filtered_stocks)}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_steps_1_and_2()
