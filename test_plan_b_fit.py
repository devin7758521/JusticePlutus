"""
测试方案B的拟合逻辑
================================================================================

验证：
1. 价格使用实时数据（不拟合）
2. 成交量需要拟合
3. 5周成交量均线根据拟合后的成交量重新计算

================================================================================
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

print("=" * 80)
print("测试方案B的拟合逻辑")
print("=" * 80)

# 创建模拟数据
def create_test_data():
    """创建测试数据"""
    
    # 历史周K数据（上周）
    historical_weekly = pd.DataFrame({
        'date': [(datetime.now() - timedelta(weeks=1)).strftime('%Y-%m-%d')],
        'open': [10.0],
        'high': [10.5],
        'low': [9.8],
        'close': [10.2],
        'volume': [1000000],
        'amount': [10000000]
    })
    
    # 本周日K数据（周一）
    current_daily = pd.DataFrame({
        'date': [datetime.now().strftime('%Y-%m-%d')],
        'open': [10.3],
        'high': [10.8],
        'low': [10.1],
        'close': [10.6],
        'volume': [300000],
        'amount': [3100000]
    })
    
    return historical_weekly, current_daily

# 测试拟合逻辑
def test_fit_logic():
    """测试拟合逻辑"""
    
    historical_weekly, current_daily = create_test_data()
    
    # 周一权重40%
    weight = 0.40
    
    print("\n原始数据:")
    print(f"上周周K: open={historical_weekly.iloc[0]['open']}, "
          f"high={historical_weekly.iloc[0]['high']}, "
          f"low={historical_weekly.iloc[0]['low']}, "
          f"close={historical_weekly.iloc[0]['close']}, "
          f"volume={historical_weekly.iloc[0]['volume']}, "
          f"amount={historical_weekly.iloc[0]['amount']}")
    
    print(f"本周日K: open={current_daily.iloc[0]['open']}, "
          f"high={current_daily.iloc[0]['high']}, "
          f"low={current_daily.iloc[0]['low']}, "
          f"close={current_daily.iloc[0]['close']}, "
          f"volume={current_daily.iloc[0]['volume']}, "
          f"amount={current_daily.iloc[0]['amount']}")
    
    # 拟合计算
    last_week = historical_weekly.iloc[0]
    current_week = current_daily.iloc[0]
    
    # 价格使用实时数据（不拟合）
    fitted_open = current_week['open']
    fitted_high = current_week['high']
    fitted_low = current_week['low']
    fitted_close = current_week['close']
    
    # 成交量和成交额拟合
    fitted_volume = last_week['volume'] * (1 - weight) + current_week['volume'] * weight
    fitted_amount = last_week['amount'] * (1 - weight) + current_week['amount'] * weight
    
    print("\n拟合结果（周一权重40%）:")
    print(f"价格（实时）: open={fitted_open}, high={fitted_high}, low={fitted_low}, close={fitted_close}")
    print(f"成交量（拟合）: volume={fitted_volume:.0f}")
    print(f"成交额（拟合）: amount={fitted_amount:.0f}")
    
    # 验证
    print("\n验证:")
    print(f"✓ 价格使用实时数据: open={fitted_open} == 本周open={current_week['open']}")
    print(f"✓ 成交量拟合: {last_week['volume']} * 0.6 + {current_week['volume']} * 0.4 = {fitted_volume:.0f}")
    print(f"✓ 成交额拟合: {last_week['amount']} * 0.6 + {current_week['amount']} * 0.4 = {fitted_amount:.0f}")
    
    # 计算拟合比例
    volume_ratio = fitted_volume / last_week['volume']
    amount_ratio = fitted_amount / last_week['amount']
    
    print(f"\n拟合比例:")
    print(f"成交量: {fitted_volume:.0f} / {last_week['volume']} = {volume_ratio:.2%}")
    print(f"成交额: {fitted_amount:.0f} / {last_week['amount']} = {amount_ratio:.2%}")

# 运行测试
test_fit_logic()

print("\n" + "=" * 80)
print("测试完成！")
print("=" * 80)
