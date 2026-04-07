# -*- coding: utf-8 -*-
"""
测试周K线数据获取功能 - 完整流程（三步骤）

步骤1: 获取全市场股票列表（故障切换）
步骤2: 筛选沪深主板、非ST、上市2年以上
步骤3: 获取周K数据（故障切换、前复权、多线程）
"""

import logging
from data_provider import DataFetcherManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_step1_get_all_stock_list():
    """测试步骤1: 获取全市场股票列表"""
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
        
        return stock_list
        
    except Exception as e:
        print(f"❌ 获取股票列表失败: {e}")
        return []


def test_step2_filter_stocks(all_stocks):
    """测试步骤2: 筛选沪深主板、非ST、上市2年以上"""
    print("\n" + "=" * 80)
    print("步骤2: 筛选沪深主板、非ST、上市2年以上")
    print("=" * 80)
    
    if not all_stocks:
        print("❌ 股票列表为空，跳过筛选")
        return []
    
    manager = DataFetcherManager()
    
    try:
        filtered_stocks = manager.filter_main_board_stocks(all_stocks)
        print(f"✅ 筛选完成: {len(filtered_stocks)} 只股票")
        
        if filtered_stocks:
            print("\n前10只筛选后的股票：")
            for i, stock in enumerate(filtered_stocks[:10], 1):
                print(f"  {i}. {stock['code']} - {stock['name']} - 上市日期: {stock.get('list_date', 'N/A')}")
        
        return filtered_stocks
        
    except Exception as e:
        print(f"❌ 筛选股票失败: {e}")
        return []


def test_step3_get_weekly_data(filtered_stocks):
    """测试步骤3: 获取周K数据（故障切换、前复权、多线程）"""
    print("\n" + "=" * 80)
    print("步骤3: 获取周K数据（故障切换、前复权、多线程）")
    print("=" * 80)
    
    if not filtered_stocks:
        print("❌ 筛选后的股票列表为空，跳过获取周K数据")
        return None
    
    print(f"准备获取 {len(filtered_stocks)} 只股票的周K线数据（2年，前复权）")
    print("注意：此操作可能需要较长时间...")
    
    response = input("是否继续？(y/n): ")
    if response.lower() != 'y':
        print("已跳过周K线数据获取")
        return None
    
    manager = DataFetcherManager()
    
    stock_codes = [stock['code'] for stock in filtered_stocks]
    
    try:
        results, source = manager.get_weekly_data_batch_with_failover(
            stock_codes=stock_codes,
            weeks=104,
            max_workers=5
        )
        print(f"✅ 成功从 [{source}] 获取到 {len(results)}/{len(stock_codes)} 只股票的周K线数据")
        
        if results:
            first_code = list(results.keys())[0]
            df = results[first_code]
            print(f"\n股票 {first_code} 的周K线数据（前5行）：")
            print(df.head())
            print(f"\n数据形状: {df.shape}")
            print(f"数据列: {list(df.columns)}")
        
        return results
        
    except Exception as e:
        print(f"❌ 获取周K线数据失败: {e}")
        return None


def test_complete_workflow():
    """测试完整的三步骤流程"""
    print("\n" + "=" * 80)
    print("开始完整的三步骤流程测试")
    print("=" * 80)
    
    all_stocks = test_step1_get_all_stock_list()
    
    if not all_stocks:
        print("\n❌ 步骤1失败，无法继续")
        return
    
    filtered_stocks = test_step2_filter_stocks(all_stocks)
    
    if not filtered_stocks:
        print("\n❌ 步骤2失败，无法继续")
        return
    
    weekly_data = test_step3_get_weekly_data(filtered_stocks)
    
    print("\n" + "=" * 80)
    print("完整流程测试结束")
    print("=" * 80)
    
    if weekly_data:
        print(f"✅ 成功获取到 {len(weekly_data)} 只股票的周K线数据")
    else:
        print("⚠️  未获取到周K线数据")


if __name__ == "__main__":
    test_complete_workflow()
