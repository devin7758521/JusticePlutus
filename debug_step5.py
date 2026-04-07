"""
调试第五步：生成符合偏离度要求且MA5向上的数据
"""
from data_provider import DataFetcherManager
import pandas as pd
from datetime import datetime, timedelta

print("=" * 80)
print("调试第五步：生成符合偏离度要求且MA5向上的数据")
print("=" * 80)

# 创建符合所有条件的测试数据
def create_test_data(
    weeks: int = 70,
    target_deviation: float = 2.0
) -> pd.DataFrame:
    """创建符合偏离度要求且MA5向上的测试数据"""
    dates = [(datetime.now() - timedelta(weeks=weeks-i)).strftime('%Y-%m-%d') 
             for i in range(weeks)]
    
    # 固定价格和成交额
    closes = [30.0] * weeks
    amounts = [6e8] * weeks
    
    # 成交量：精确控制MA5和MA60的偏离度，且MA5向上
    ma60_base = 1000000
    
    # 计算MA5的目标值
    ma5_target = ma60_base * (1 + target_deviation / 100)
    
    # 构造成交量序列
    volumes = []
    
    # 前60周：使用MA60的值
    for i in range(60):
        volumes.append(ma60_base)
    
    # 第61-65周：逐渐增加到MA5目标值
    for i in range(5):
        volumes.append(ma60_base + (ma5_target - ma60_base) * (i + 1) / 5)
    
    # 第66-70周：继续增加，使MA5向上
    # 最后5周的平均值应该接近ma5_target，且最后一周 > 倒数第二周
    for i in range(5):
        # 逐渐增加
        volumes.append(ma5_target + i * 10000)
    
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

# 测试不同的偏离度
test_deviations = [-2.0, 0.0, 2.0, 5.0]

for target_dev in test_deviations:
    print(f"\n{'='*60}")
    print(f"目标偏离度: {target_dev}%")
    print(f"{'='*60}")
    
    df = create_test_data(70, target_dev)
    
    # 计算MA5和MA60
    df_sorted = df.sort_values('date').copy()
    df_sorted['volume_ma5'] = df_sorted['volume'].rolling(window=5, min_periods=5).mean()
    df_sorted['volume_ma60'] = df_sorted['volume'].rolling(window=60, min_periods=60).mean()
    
    # 获取最新值
    latest = df_sorted.iloc[-1]
    prev = df_sorted.iloc[-2]
    
    print(f"  最新MA5: {latest['volume_ma5']:.0f}")
    print(f"  前一周MA5: {prev['volume_ma5']:.0f}")
    print(f"  MA5是否向上: {latest['volume_ma5'] > prev['volume_ma5']}")
    print(f"  最新MA60: {latest['volume_ma60']:.0f}")
    
    # 计算偏离度
    actual_deviation = (latest['volume_ma5'] - latest['volume_ma60']) / latest['volume_ma60'] * 100
    print(f"  实际偏离度: {actual_deviation:.2f}%")
    print(f"  是否在范围内: {-3 <= actual_deviation <= 7}")

# 测试筛选
print(f"\n{'='*80}")
print("测试筛选（目标偏离度2%）")
print(f"{'='*80}")

df = create_test_data(70, 2.0)
weekly_data = {'600001': df}
passed_from_step4 = [{'code': '600001', 'close': 30.0, 'ma': 28.5, 'pct_above': 5.0}]

manager = DataFetcherManager()
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
print(f"  通过: {len(passed_stocks)}")
print(f"  失败原因: {stats['reasons']}")

if passed_stocks:
    print(f"\n通过的股票:")
    for stock in passed_stocks:
        print(f"  {stock}")

print("\n" + "=" * 80)
