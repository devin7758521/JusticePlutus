# -*- coding: utf-8 -*-
"""
方案B拟合配置
================================================================================

用于调整周一到周四的成交量放大系数

使用方法：
1. 直接修改 WEEKLY_FITTING_MULTIPLIERS 字典中的值
2. 重新运行选股程序即可生效

================================================================================
"""

# 周K拟合放大系数（周一到周四）
# 用于补偿数据不完整的误差
WEEKLY_FITTING_MULTIPLIERS = {
    0: 1.15,  # 周一 - 放大15%
    1: 1.10,  # 周二 - 放大10%
    2: 1.05,  # 周三 - 放大5%
    3: 1.03,  # 周四 - 放大3%
    4: 1.00,  # 周五 - 不放大（完整数据）
}

# 偏离值筛选范围
DEVIATION_RANGE = {
    'min': -3.0,  # 最小偏离度
    'max': 7.0,   # 最大偏离度
}

# 价格筛选范围（元）
PRICE_RANGE = {
    'min': 3.0,   # 最低价格
    'max': 70.0,  # 最高价格
}

# 成交额筛选阈值（元）
TURNOVER_THRESHOLD = 500_000_000  # 5亿

# 成交量均线周期
VOLUME_MA_PERIODS = {
    'short': 5,   # 短期均线（5周）
    'long': 60,   # 长期均线（60周）
}

# 价格均线周期
PRICE_MA_PERIOD = 25  # 25周均线

# 数据要求
MIN_DATA_YEARS = 2  # 最少2年数据
MIN_DATA_WEEKS = 104  # 最少104周数据（2年）

# 多线程配置
THREAD_CONFIG = {
    'max_workers': 5,  # 最大线程数
    'timeout': 30,     # 超时时间（秒）
}

# 数据源优先级
DATA_SOURCE_PRIORITY = [
    'akshare',
    'efinance',
    'yfinance',
]

# 日志配置
LOG_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
}

# ==============================================================================
# 辅助函数
# ==============================================================================

def get_fitting_multiplier(weekday: int) -> float:
    """
    获取指定周几的放大系数
    
    Args:
        weekday: 周几（0=周一, 1=周二, ..., 4=周五）
        
    Returns:
        放大系数
    """
    return WEEKLY_FITTING_MULTIPLIERS.get(weekday, 1.0)


def get_deviation_range() -> tuple:
    """
    获取偏离值范围
    
    Returns:
        (最小值, 最大值)
    """
    return (DEVIATION_RANGE['min'], DEVIATION_RANGE['max'])


def get_price_range() -> tuple:
    """
    获取价格范围
    
    Returns:
        (最低价格, 最高价格)
    """
    return (PRICE_RANGE['min'], PRICE_RANGE['max'])


def get_turnover_threshold() -> float:
    """
    获取成交额阈值
    
    Returns:
        成交额阈值（元）
    """
    return TURNOVER_THRESHOLD


def get_volume_ma_periods() -> tuple:
    """
    获取成交量均线周期
    
    Returns:
        (短期周期, 长期周期)
    """
    return (VOLUME_MA_PERIODS['short'], VOLUME_MA_PERIODS['long'])


def get_price_ma_period() -> int:
    """
    获取价格均线周期
    
    Returns:
        价格均线周期
    """
    return PRICE_MA_PERIOD


def get_min_data_weeks() -> int:
    """
    获取最少数据周数
    
    Returns:
        最少数据周数
    """
    return MIN_DATA_WEEKS


def get_thread_config() -> dict:
    """
    获取线程配置
    
    Returns:
        线程配置字典
    """
    return THREAD_CONFIG


def get_data_source_priority() -> list:
    """
    获取数据源优先级
    
    Returns:
        数据源优先级列表
    """
    return DATA_SOURCE_PRIORITY


# ==============================================================================
# 配置验证
# ==============================================================================

def validate_config():
    """验证配置是否合理"""
    
    # 验证放大系数
    for weekday, multiplier in WEEKLY_FITTING_MULTIPLIERS.items():
        if weekday < 0 or weekday > 4:
            raise ValueError(f"无效的周几: {weekday}")
        if multiplier < 1.0:
            print(f"警告: 周{weekday+1}的放大系数 {multiplier} < 1.0，可能导致数据低估")
    
    # 验证偏离值范围
    if DEVIATION_RANGE['min'] >= DEVIATION_RANGE['max']:
        raise ValueError("偏离值范围设置错误：最小值必须小于最大值")
    
    # 验证价格范围
    if PRICE_RANGE['min'] >= PRICE_RANGE['max']:
        raise ValueError("价格范围设置错误：最低价格必须小于最高价格")
    
    # 验证成交额阈值
    if TURNOVER_THRESHOLD <= 0:
        raise ValueError("成交额阈值必须大于0")
    
    # 验证均线周期
    if VOLUME_MA_PERIODS['short'] >= VOLUME_MA_PERIODS['long']:
        raise ValueError("短期均线周期必须小于长期均线周期")
    
    print("✓ 配置验证通过")


if __name__ == "__main__":
    # 打印当前配置
    print("=" * 80)
    print("方案B拟合配置")
    print("=" * 80)
    
    print("\n周K拟合放大系数:")
    for weekday, multiplier in WEEKLY_FITTING_MULTIPLIERS.items():
        weekday_name = ['周一', '周二', '周三', '周四', '周五'][weekday]
        print(f"  {weekday_name}: {multiplier:.2f} (放大 {(multiplier - 1) * 100:.0f}%)")
    
    print(f"\n偏离值范围: {DEVIATION_RANGE['min']}% ~ {DEVIATION_RANGE['max']}%")
    print(f"价格范围: {PRICE_RANGE['min']}元 ~ {PRICE_RANGE['max']}元")
    print(f"成交额阈值: {TURNOVER_THRESHOLD / 100_000_000:.0f}亿元")
    print(f"成交量均线周期: {VOLUME_MA_PERIODS['short']}周 / {VOLUME_MA_PERIODS['long']}周")
    print(f"价格均线周期: {PRICE_MA_PERIOD}周")
    print(f"最少数据要求: {MIN_DATA_YEARS}年 ({MIN_DATA_WEEKS}周)")
    
    print("\n数据源优先级:")
    for i, source in enumerate(DATA_SOURCE_PRIORITY, 1):
        print(f"  {i}. {source}")
    
    print("\n线程配置:")
    print(f"  最大线程数: {THREAD_CONFIG['max_workers']}")
    print(f"  超时时间: {THREAD_CONFIG['timeout']}秒")
    
    # 验证配置
    print("\n" + "=" * 80)
    validate_config()
    print("=" * 80)
