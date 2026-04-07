"""
测试周K线数据源是否写死
"""
from data_provider import DataFetcherManager

manager = DataFetcherManager()

print("=" * 80)
print("测试周K线数据源列表是否写死")
print("=" * 80)

print(f"\n周K线数据源数量: {len(manager._weekly_fetchers)}")
print("\n数据源列表（按优先级排序）:")
for i, fetcher in enumerate(manager._weekly_fetchers, start=1):
    print(f"  {i}. {fetcher.name} (优先级 {fetcher.priority})")

print("\n" + "=" * 80)
print("测试完成！")
print("=" * 80)
