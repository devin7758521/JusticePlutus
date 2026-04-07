"""
测试第五步：根据价格、成交额和成交量均线筛选股票（修正版）
"""
from data_provider import DataFetcherManager
import pandas as pd
from datetime import datetime, timedelta

print("=" * 80)
print("测试第五步：根据价格、成交额和成交量均线筛选股票")
print("=" * 80)

# 创建符合所有条件的测试数据
def create_test_data(
    weeks: int = 70,
    price: float = 30.0,
    amount: float = 6e8,
    target_deviation: float = 2.0,
    ma5_rising: bool = True
) -> pd.DataFrame:
    """创建符合偏离度要求且MA5向上的测试数据"""
    dates = [(datetime.now() - timedelta(weeks=weeks-i)).strftime('%Y-%m-%d') 
             for i in range(weeks)]
    
    # 价格和成交额
    closes = [price] * weeks
    amounts = [amount] * weeks
    
    # 成交量：精确控制MA5和MA60的偏离度
    # 为了精确控制，我们需要理解：
    # MA60 = (v[-60] + v[-59] + ... + v[-1]) / 60
    # MA5 = (v[-5] + v[-4] + v[-3] + v[-2] + v[-1]) / 5
    
    # 策略：
    # 1. 前55周使用基础值
    # 2. 第56-60周调整，使MA60接近目标
    # 3. 第61-70周调整，使MA5达到目标偏离度
    
    base_volume = 1000000
    volumes = [base_volume] * 55  # 前55周
    
    # 计算MA5的目标值
    ma5_target = base_volume * (1 + target_deviation / 100)
    
    # 第56-60周：调整以影响MA60
    # MA60 = (sum(v[0:55]) + v[55] + v[56] + v[57] + v[58] + v[59]) / 60
    # 我们希望MA60接近base_volume
    for i in range(5):
        volumes.append(base_volume)
    
    # 第61-65周：逐渐调整到MA5目标值
    for i in range(5):
        volumes.append(base_volume + (ma5_target - base_volume) * (i + 1) / 5)
    
    # 第66-70周：控制MA5方向
    if ma5_rising:
        # MA5向上：逐渐增加
        for i in range(5):
            volumes.append(ma5_target + i * 10000)
    else:
        # MA5向下：逐渐减少
        for i in range(5):
            volumes.append(ma5_target - i * 10000)
    
    df = pd.DataFrame({
        'date': dates,
        'open': closes,
        'high': [c * 1.02 for c in closes],
        'low': [c * 0.98 for c in closes],
        'close': closes,
        'volume': volumes,
        'amount': amounts,
        'pct_chg': [0] * weeks
    })
    
    return df

# 创建测试数据
test_cases = [
    # (code, price, amount, deviation, ma5_rising, expected_pass)
    ('600001', 30, 6e8, 2.0, True, True),     # 应该通过
    ('600002', 2, 6e8, 2.0, True, False),     # 价格太低
    ('600003', 80, 6e8, 2.0, True, False),    # 价格太高
    ('600004', 30, 3e8, 2.0, True, False),    # 成交额不足
    ('600005', 30, 6e8, 2.0, False, False),   # MA5不向上
    ('600006', 30, 6e8, -10.0, True, False),  # 偏离度太低（修改为-10%）
    ('600007', 30, 6e8, 15.0, True, False),   # 偏离度太高（修改为15%）
    ('600008', 30, 6e8, 0.0, True, True),     # 偏离度为0，应该通过
    ('600009', 50, 10e8, 5.0, True, True),    # 应该通过
    ('600010', 10, 8e8, -2.0, True, True),    # 应该通过
]

weekly_data = {}
expected_results = {}

for code, price, amount, deviation, ma5_rising, expected_pass in test_cases:
    df = create_test_data(70, price, amount, deviation, ma5_rising)
    weekly_data[code] = df
    expected_results[code] = expected_pass

print(f"\n创建了 {len(weekly_data)} 只股票的模拟数据:")
for code, df in weekly_data.items():
    print(f"  {code}: {len(df)} 周数据, "
          f"价格={df.iloc[-1]['close']:.2f}, "
          f"成交额={df.iloc[-1]['amount']/1e8:.2f}亿")

# 模拟第四步的结果（所有股票都通过第四步）
passed_from_step4 = [
    {'code': code, 'close': df.iloc[-1]['close'], 'ma': df.iloc[-1]['close'] * 0.95, 'pct_above': 5.0}
    for code, df in weekly_data.items()
]

# 初始化管理器
manager = DataFetcherManager()

# 步骤5: 根据价格、成交额和成交量均线筛选
print("\n开始筛选...")
passed_stocks, stats = manager.filter_stocks_by_price_volume(
    weekly_data=weekly_data,
    passed_from_step4=passed_from_step4,
    min_price=3.0,
    max_price=70.0,
    min_amount=5e8,
    min_deviation=-3.0,
    max_deviation=7.0,
    min_data_points=65
)

print(f"\n筛选结果:")
print(f"  - 总数: {stats['total']}")
print(f"  - 通过: {stats['passed']}")
print(f"  - 失败: {stats['failed']}")
print(f"  - 通过率: {stats['pass_rate']:.2f}%")
print(f"\n  失败原因:")
print(f"    不在第四步: {stats['reasons']['not_in_step4']}")
print(f"    价格不符: {stats['reasons']['price_out_of_range']}")
print(f"    成交额不足: {stats['reasons']['amount_too_low']}")
print(f"    数据不足: {stats['reasons']['insufficient_data']}")
print(f"    MA5不向上: {stats['reasons']['volume_ma5_not_rising']}")
print(f"    偏离度不符: {stats['reasons']['deviation_out_of_range']}")

print(f"\n通过筛选的股票（按偏离度绝对值排序）:")
for stock in passed_stocks:
    print(f"  {stock['code']}: "
          f"价格={stock['close']:.2f}, "
          f"成交额={stock['amount']/1e8:.2f}亿, "
          f"MA5={stock['volume_ma5']:.0f}, "
          f"MA60={stock['volume_ma60']:.0f}, "
          f"偏离度={stock['deviation']:.2f}%")

# 验证结果
print("\n" + "=" * 80)
print("验证结果:")
print("=" * 80)

expected_passed = [code for code, expected in expected_results.items() if expected]
actual_passed = [s['code'] for s in passed_stocks]

print(f"预期通过: {expected_passed}")
print(f"实际通过: {actual_passed}")

if set(expected_passed) == set(actual_passed):
    print("✓ 测试通过！")
else:
    print("✗ 测试失败！")
    print(f"  缺失: {set(expected_passed) - set(actual_passed)}")
    print(f"  多余: {set(actual_passed) - set(expected_passed)}")

print("\n" + "=" * 80)
print("测试完成！")
print("=" * 80)
