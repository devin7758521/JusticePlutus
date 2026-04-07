"""
方案B拟合细节 - 完整示例
================================================================================

展示每一步的计算过程

================================================================================
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

print("=" * 80)
print("方案B拟合细节 - 完整示例")
print("=" * 80)

# ==============================================================================
# 步骤1: 准备历史数据
# ==============================================================================
print("\n步骤1: 准备历史数据")
print("-" * 80)

# 假设今天是周一
today = datetime.now()
today_weekday = today.weekday()  # 0=周一

print(f"今天是: 周{['一','二','三','四','五'][today_weekday]}")

# 历史周K数据（最近65周，只展示最近10周）
dates = [(today - timedelta(weeks=65-i)).strftime('%Y-%m-%d') for i in range(65)]

# 生成模拟数据（最近65周的成交量）
np.random.seed(42)
volumes = []
for i in range(65):
    # 生成随机成交量，范围在80万到120万之间
    vol = np.random.randint(800000, 1200000)
    volumes.append(vol)

historical_weekly = pd.DataFrame({
    'date': dates,
    'open': [10.0 + i*0.1 for i in range(65)],
    'high': [10.5 + i*0.1 for i in range(65)],
    'low': [9.8 + i*0.1 for i in range(65)],
    'close': [10.2 + i*0.1 for i in range(65)],
    'volume': volumes,
    'amount': [v * 10 for v in volumes]
})

print(f"\n历史周K数据（最近10周）:")
for i in range(-10, 0):
    row = historical_weekly.iloc[i]
    print(f"  {row['date']}: volume={row['volume']:,.0f}")

# ==============================================================================
# 步骤2: 计算60周成交量均线
# ==============================================================================
print("\n步骤2: 计算60周成交量均线")
print("-" * 80)

# 60周成交量均线（使用最近60周数据）
ma60_volume = historical_weekly['volume'].iloc[-60:].mean()
print(f"60周成交量均线 = {ma60_volume:,.0f}")
print(f"  计算方式: 最近60周成交量的平均值")
print(f"  数据范围: {historical_weekly.iloc[-60]['date']} 到 {historical_weekly.iloc[-1]['date']}")

# ==============================================================================
# 步骤3: 获取本周日K数据
# ==============================================================================
print("\n步骤3: 获取本周日K数据")
print("-" * 80)

# 假设本周一成交量放大
current_daily = pd.DataFrame({
    'date': [today.strftime('%Y-%m-%d')],
    'open': [16.5],
    'high': [16.8],
    'low': [16.3],
    'close': [16.7],
    'volume': [1500000],  # 本周成交量放大到150万
    'amount': [15000000]
})

print(f"本周日K数据（周一）:")
print(f"  open={current_daily.iloc[0]['open']}")
print(f"  high={current_daily.iloc[0]['high']}")
print(f"  low={current_daily.iloc[0]['low']}")
print(f"  close={current_daily.iloc[0]['close']}")
print(f"  volume={current_daily.iloc[0]['volume']:,}")
print(f"  amount={current_daily.iloc[0]['amount']:,}")

# ==============================================================================
# 步骤4: 拟合本周周K
# ==============================================================================
print("\n步骤4: 拟合本周周K")
print("-" * 80)

# 复制历史数据
fitted = historical_weekly.copy()

# 价格使用实时数据（不拟合）
current_week_open = current_daily.iloc[0]['open']
current_week_high = current_daily.iloc[0]['high']
current_week_low = current_daily.iloc[0]['low']
current_week_close = current_daily.iloc[0]['close']

# 成交量使用本周累计值（不拟合）
current_week_volume = current_daily['volume'].sum()

# 成交额使用本周累计值（不拟合）
current_week_amount = current_daily['amount'].sum()

print(f"拟合结果:")
print(f"  open={current_week_open}（实时）")
print(f"  high={current_week_high}（实时）")
print(f"  low={current_week_low}（实时）")
print(f"  close={current_week_close}（实时）")
print(f"  volume={current_week_volume:,}（本周累计）")
print(f"  amount={current_week_amount:,}（本周累计）")

# 更新最后一行数据
fitted.iloc[-1, fitted.columns.get_loc('open')] = current_week_open
fitted.iloc[-1, fitted.columns.get_loc('high')] = current_week_high
fitted.iloc[-1, fitted.columns.get_loc('low')] = current_week_low
fitted.iloc[-1, fitted.columns.get_loc('close')] = current_week_close
fitted.iloc[-1, fitted.columns.get_loc('volume')] = current_week_volume
fitted.iloc[-1, fitted.columns.get_loc('amount')] = current_week_amount

# ==============================================================================
# 步骤5: 计算新的5周成交量均线
# ==============================================================================
print("\n步骤5: 计算新的5周成交量均线")
print("-" * 80)

# 历史5周成交量均线（拟合前）
historical_ma5 = historical_weekly['volume'].iloc[-5:].mean()
print(f"历史5周成交量均线（拟合前）= {historical_ma5:,.0f}")
print(f"  数据: {[f'{v:,}' for v in historical_weekly['volume'].iloc[-5:].values]}")

# 新的5周成交量均线（拟合后）
# 去掉最早一周，加上本周
new_volumes = list(fitted['volume'].iloc[-5:].values)
new_ma5 = np.mean(new_volumes)
print(f"\n新的5周成交量均线（拟合后）= {new_ma5:,.0f}")
print(f"  数据: {[f'{v:,}' for v in new_volumes]}")

# ==============================================================================
# 步骤6: 计算新的偏离值
# ==============================================================================
print("\n步骤6: 计算新的偏离值")
print("-" * 80)

# 60周成交量均线不变
new_ma60 = ma60_volume
print(f"60周成交量均线 = {new_ma60:,.0f}（不变）")

# 计算偏离值
deviation = (new_ma5 - new_ma60) / new_ma60 * 100
print(f"\n偏离值 = (new_ma5 - ma60) / ma60 * 100")
print(f"       = ({new_ma5:,.0f} - {new_ma60:,.0f}) / {new_ma60:,.0f} * 100")
print(f"       = {deviation:.2f}%")

# ==============================================================================
# 步骤7: 判断是否通过筛选
# ==============================================================================
print("\n步骤7: 判断是否通过筛选")
print("-" * 80)

# 条件1: 5周成交量均线向上
prev_ma5 = historical_weekly['volume'].iloc[-6:-1].mean()
if new_ma5 > prev_ma5:
    print(f"✓ 5周成交量均线向上: {new_ma5:,.0f} > {prev_ma5:,.0f}")
else:
    print(f"✗ 5周成交量均线向下: {new_ma5:,.0f} <= {prev_ma5:,.0f}")

# 条件2: 偏离度在范围内
if -3 <= deviation <= 7:
    print(f"✓ 偏离度在范围内: {deviation:.2f}% ∈ [-3%, 7%]")
else:
    print(f"✗ 偏离度不在范围内: {deviation:.2f}% ∉ [-3%, 7%]")

# ==============================================================================
# 总结
# ==============================================================================
print("\n" + "=" * 80)
print("总结")
print("=" * 80)

print(f"\n拟合前:")
print(f"  5周成交量均线: {historical_ma5:,.0f}")
print(f"  60周成交量均线: {ma60_volume:,.0f}")
print(f"  偏离值: {(historical_ma5 - ma60_volume) / ma60_volume * 100:.2f}%")

print(f"\n拟合后:")
print(f"  5周成交量均线: {new_ma5:,.0f}")
print(f"  60周成交量均线: {new_ma60:,.0f}（不变）")
print(f"  偏离值: {deviation:.2f}%")

print(f"\n变化:")
print(f"  5周成交量均线: {historical_ma5:,.0f} → {new_ma5:,.0f} (变化 {(new_ma5 - historical_ma5) / historical_ma5 * 100:+.2f}%)")
print(f"  偏离值: {(historical_ma5 - ma60_volume) / ma60_volume * 100:.2f}% → {deviation:.2f}% (变化 {deviation - (historical_ma5 - ma60_volume) / ma60_volume * 100:+.2f}%)")

print("\n" + "=" * 80)
