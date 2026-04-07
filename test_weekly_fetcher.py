# -*- coding: utf-8 -*-
"""
测试周K线数据获取功能
"""

import logging
from data_provider import DataFetcherManager, is_main_board_stock

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_is_main_board_stock():
    """测试股票代码筛选逻辑"""
    print("\n=== 测试股票代码筛选逻辑 ===")
    
    test_cases = [
        ("600519", "贵州茅台", True),   # 沪市主板
        ("000001", "平安银行", True),   # 深市主板
        ("002415", "海康威视", True),   # 深市主板
        ("688001", "华兴源创", False),  # 科创板
        ("300001", "特锐德", False),    # 创业板
        ("830799", "ST艾能", False),    # 北交所
        ("600698", "ST天雁", False),    # ST股票
        ("601318", "中国平安", True),   # 沪市主板
    ]
    
    for code, name, expected in test_cases:
        result = is_main_board_stock(code, name)
        status = "✓" if result == expected else "✗"
        print(f"{status} {code} ({name}): {'沪深主板' if result else '非沪深主板'}")
    
    print()


def test_get_stock_list():
    """测试获取股票列表"""
    print("\n=== 测试获取沪深主板股票列表 ===")
    
    manager = DataFetcherManager()
    
    try:
        stock_list, source = manager.get_main_board_stock_list()
        print(f"成功从 [{source}] 获取到 {len(stock_list)} 只沪深主板股票")
        
        if stock_list:
            print("\n前10只股票：")
            for i, stock in enumerate(stock_list[:10], 1):
                print(f"  {i}. {stock['code']} - {stock['name']}")
        
    except Exception as e:
        print(f"获取股票列表失败: {e}")


def test_get_weekly_data():
    """测试批量获取周K线数据"""
    print("\n=== 测试批量获取周K线数据 ===")
    print("注意：此测试会获取大量数据，可能需要较长时间...")
    
    # 询问用户是否继续
    response = input("是否继续？(y/n): ")
    if response.lower() != 'y':
        print("已跳过周K线数据获取测试")
        return
    
    manager = DataFetcherManager()
    
    try:
        results, source = manager.get_weekly_data_batch(weeks=104)
        print(f"成功从 [{source}] 获取到 {len(results)} 只股票的周K线数据")
        
        if results:
            # 显示第一只股票的数据
            first_code = list(results.keys())[0]
            df = results[first_code]
            print(f"\n股票 {first_code} 的周K线数据（前5行）：")
            print(df.head())
            print(f"\n数据形状: {df.shape}")
        
    except Exception as e:
        print(f"获取周K线数据失败: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("周K线数据获取功能测试")
    print("=" * 60)
    
    # 测试股票代码筛选逻辑
    test_is_main_board_stock()
    
    # 测试获取股票列表
    test_get_stock_list()
    
    # 测试批量获取周K线数据（需要用户确认）
    # test_get_weekly_data()
    
    print("\n测试完成！")
