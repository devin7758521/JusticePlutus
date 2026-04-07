# -*- coding: utf-8 -*-
"""
快速验证周K线数据获取功能
"""

import logging
from data_provider import DataFetcherManager, is_main_board_stock, is_listed_over_2_years

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_functions():
    """测试核心函数"""
    print("=" * 80)
    print("测试核心函数")
    print("=" * 80)
    
    # 测试股票筛选
    test_cases = [
        ("600519", "贵州茅台", "2001-08-27", True),   # 沪市主板，上市超过2年
        ("000001", "平安银行", "1991-04-03", True),   # 深市主板，上市超过2年
        ("688001", "华兴源创", "2019-07-22", False),  # 科创板
        ("300001", "特锐德", "2009-10-30", False),    # 创业板
        ("600698", "ST天雁", "1993-10-08", False),    # ST股票
        ("601318", "中国平安", "2007-03-01", True),   # 沪市主板
        ("002415", "海康威视", "2010-05-28", True),   # 深市主板
    ]
    
    print("\n测试股票筛选逻辑：")
    for code, name, list_date, expected in test_cases:
        is_main = is_main_board_stock(code, name)
        is_2y = is_listed_over_2_years(list_date)
        result = is_main and is_2y
        status = "✓" if result == expected else "✗"
        print(f"{status} {code} ({name}): 主板={is_main}, 上市2年={is_2y}, 结果={result}, 预期={expected}")
    
    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)

if __name__ == "__main__":
    test_functions()
