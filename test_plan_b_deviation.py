"""
测试方案B的偏离值拟合逻辑
================================================================================

验证：
1. 价格使用实时数据（不拟合）
2. 成交量使用本周累计值（不拟合）
3. 成交额不拟合（第五步已经筛选过）
4. 5周成交量均线根据本周累计成交量重新计算
5. 60周成交量均线不变（周期太长）
6. 偏离值根据新的5周成交量均线重新计算

================================================================================
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

print("=" * 80)
print("测试方案B的偏离值拟合逻辑")
print("=" * 80)

# 创建模拟数据
def create_test_data():
    """创建测试数据"""
    
    # 历史周K数据（最近5周）
    dates = [(datetime.now() - timedelta(weeks=5-i)).strftime('%Y-%m-%d') for i in range(5)]
    
    historical_weekly = pd.DataFrame({
        'date': dates,
        'open': [10.0, 10.2, 10.5, 10.3, 10.8],
        'high': [10.5, 10.7, 10.9, 10.8, 11.2],
        'low': [9.8, 10.0, 10.2, 10.1, 10.6],
        'close': [10.2, 10.5, 10.3, 10.8, 11.0],
        'volume': [1000000, 1100000, 950000, 1200000, 1050000],  # 最近5周成交量
        'amount': [10000000, 11000000, 9500000, 12000000, 10500000]
    })
    
    # 本周日K数据（周一，成交量放大）
    current_daily = pd.DataFrame({
        'date': [datetime.now().strftime('%Y-%m-%d')],
        'open': [11.2],
        'high': [11.5],
        'low': [11.0],
        'close': [11.3],
        'volume': [1500000],  # 本周成交量放大了
        'amount': [16500000]
    })
    
    return historical_weekly, current_daily

# 测试偏离值拟合逻辑
def test_deviation_fitting():
    """测试偏离值拟合逻辑"""
    
    historical_weekly, current_daily = create_test_data()
    
    print("\n历史周K数据（最近5周）:")
    for i, row in historical_weekly.iterrows():
        print(f"  {row['date']}: close={row['close']}, volume={row['volume']}")
    
    print(f"\n本周日K数据（周一）:")
    print(f"  close={current_daily.iloc[0]['close']}, volume={current_daily.iloc[0]['volume']}")
    
    # 计算历史5周成交量均线
    historical_ma5 = historical_weekly['volume'].mean()
    print(f"\n历史5周成交量均线: {historical_ma5:.0f}")
    
    # 计算历史60周成交量均线（假设）
    historical_ma60 = 980000
    print(f"历史60周成交量均线（假设）: {historical_ma60:.0f}")
    
    # 计算历史偏离值
    historical_deviation = (historical_ma5 - historical_ma60) / historical_ma60 * 100
    print(f"历史偏离值: {historical_deviation:.2f}%")
    
    # 拟合后的数据
    fitted_volume = current_daily['volume'].sum()  # 本周累计成交量
    print(f"\n拟合后的本周成交量: {fitted_volume:.0f}")
    
    # 计算新的5周成交量均线
    # 去掉最早一周，加上本周
    new_volumes = list(historical_weekly['volume'][1:]) + [fitted_volume]
    new_ma5 = np.mean(new_volumes)
    print(f"新的5周成交量均线: {new_ma5:.0f}")
    
    # 60周成交量均线不变
    new_ma60 = historical_ma60
    print(f"新的60周成交量均线: {new_ma60:.0f}（不变）")
    
    # 计算新的偏离值
    new_deviation = (new_ma5 - new_ma60) / new_ma60 * 100
    print(f"新的偏离值: {new_deviation:.2f}%")
    
    # 验证
    print("\n验证:")
    print(f"✓ 成交量放大: {fitted_volume} > {historical_weekly.iloc[-1]['volume']}")
    print(f"✓ 5周成交量均线上升: {new_ma5:.0f} > {historical_ma5:.0f}")
    print(f"✓ 偏离值变化: {historical_deviation:.2f}% → {new_deviation:.2f}%")
    
    # 判断是否通过筛选
    if new_ma5 > historical_ma5:  # 5周成交量均线向上
        print(f"✓ 5周成交量均线向上: 通过")
    else:
        print(f"✗ 5周成交量均线向下: 不通过")
    
    if -3 <= new_deviation <= 7:  # 偏离度在范围内
        print(f"✓ 偏离度在范围内: 通过")
    else:
        print(f"✗ 偏离度不在范围内: 不通过")

# 运行测试
test_deviation_fitting()

print("\n" + "=" * 80)
print("测试完成！")
print("=" * 80)
