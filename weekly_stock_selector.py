# -*- coding: utf-8 -*-
"""
周K线选股策略 - 固定五步流程
================================================================================

本模块实现了完整的周K线选股策略，包含五个固定步骤：

步骤1: 获取全市场股票列表（包含上市时间）
步骤2: 筛选沪深主板、非ST、上市2年以上
步骤3: 获取周K数据（前复权、多线程）
步骤4: 筛选站上25周均线的股票
步骤5: 根据价格、成交额和成交量均线筛选

================================================================================
"""

from typing import List, Dict, Any, Tuple
import pandas as pd
from data_provider import DataFetcherManager


class WeeklyStockSelector:
    """
    周K线选股策略
    
    使用固定的五步流程筛选股票
    """
    
    def __init__(self):
        """初始化选股器"""
        self.manager = DataFetcherManager()
        
        # 步骤结果存储
        self.step1_result: Tuple[List[Dict], str] = None
        self.step2_result: List[Dict] = None
        self.step3_result: Tuple[Dict[str, pd.DataFrame], str] = None
        self.step4_result: Tuple[List[Dict], Dict] = None
        self.step5_result: Tuple[List[Dict], Dict] = None
    
    def run(
        self,
        max_stocks: int = None,
        weeks: int = 104,
        max_workers: int = 5,
        ma_period: int = 25,
        min_data_points_step4: int = 30,
        min_price: float = 3.0,
        max_price: float = 70.0,
        min_amount: float = 5e8,
        min_deviation: float = -3.0,
        max_deviation: float = 7.0,
        min_data_points_step5: int = 65,
        verbose: bool = True
    ) -> List[Dict[str, Any]]:
        """
        运行完整的五步选股流程
        
        Args:
            max_stocks: 最多处理的股票数量（用于测试，None表示全部）
            weeks: 获取周K数据的周数，默认104周（2年）
            max_workers: 多线程并发数，默认5
            ma_period: 均线周期，默认25周
            min_data_points_step4: 步骤4最小数据点数，默认30周
            min_price: 最低价格（人民币元），默认3元
            max_price: 最高价格（人民币元），默认70元
            min_amount: 最低成交额（人民币元），默认5亿元
            min_deviation: 最小偏离度，默认-3%
            max_deviation: 最大偏离度，默认7%
            min_data_points_step5: 步骤5最小数据点数，默认65周
            verbose: 是否打印详细信息，默认True
            
        Returns:
            最终通过筛选的股票列表
        """
        if verbose:
            self._print_header()
        
        # ====================================================================
        # 步骤1: 获取全市场股票列表
        # ====================================================================
        if verbose:
            print("\n" + "=" * 80)
            print("步骤1: 获取全市场股票列表")
            print("=" * 80)
        
        try:
            all_stocks, source = self.manager.get_all_stock_list_with_failover()
            self.step1_result = (all_stocks, source)
            
            if verbose:
                print(f"✓ 成功获取 {len(all_stocks)} 只股票")
                print(f"  数据源: {source}")
        except Exception as e:
            if verbose:
                print(f"✗ 步骤1失败: {e}")
            return []
        
        # ====================================================================
        # 步骤2: 筛选沪深主板、非ST、上市2年以上
        # ====================================================================
        if verbose:
            print("\n" + "=" * 80)
            print("步骤2: 筛选沪深主板、非ST、上市2年以上")
            print("=" * 80)
        
        filtered_stocks = self.manager.filter_main_board_stocks(all_stocks)
        self.step2_result = filtered_stocks
        
        if verbose:
            print(f"✓ 筛选后剩余 {len(filtered_stocks)} 只股票")
            print(f"  过滤掉 {len(all_stocks) - len(filtered_stocks)} 只股票")
        
        # ====================================================================
        # 步骤3: 获取周K数据（前复权、多线程）
        # ====================================================================
        if verbose:
            print("\n" + "=" * 80)
            print("步骤3: 获取周K数据（前复权、多线程）")
            print("=" * 80)
        
        # 提取股票代码
        stock_codes = [stock['code'] for stock in filtered_stocks]
        
        # 限制股票数量（用于测试）
        if max_stocks and len(stock_codes) > max_stocks:
            stock_codes = stock_codes[:max_stocks]
            if verbose:
                print(f"为了测试，只处理前 {max_stocks} 只股票")
        
        try:
            weekly_data, source = self.manager.get_weekly_data_batch_with_failover(
                stock_codes=stock_codes,
                weeks=weeks,
                max_workers=max_workers
            )
            self.step3_result = (weekly_data, source)
            
            if verbose:
                print(f"✓ 成功获取 {len(weekly_data)} 只股票的周K数据")
                print(f"  数据源: {source}")
        except Exception as e:
            if verbose:
                print(f"✗ 步骤3失败: {e}")
            return []
        
        # ====================================================================
        # 步骤4: 筛选站上25周均线的股票
        # ====================================================================
        if verbose:
            print("\n" + "=" * 80)
            print(f"步骤4: 筛选站上{ma_period}周均线的股票")
            print("=" * 80)
        
        passed_stocks_step4, stats_step4 = self.manager.filter_stocks_above_ma(
            weekly_data=weekly_data,
            ma_period=ma_period,
            min_data_points=min_data_points_step4
        )
        self.step4_result = (passed_stocks_step4, stats_step4)
        
        if verbose:
            print(f"\n✓ 筛选完成:")
            print(f"  总数: {stats_step4['total']}")
            print(f"  通过: {stats_step4['passed']}")
            print(f"  失败: {stats_step4['failed']}")
            print(f"  通过率: {stats_step4['pass_rate']:.2f}%")
        
        # ====================================================================
        # 步骤5: 根据价格、成交额和成交量均线筛选
        # ====================================================================
        if verbose:
            print("\n" + "=" * 80)
            print("步骤5: 根据价格、成交额和成交量均线筛选")
            print("=" * 80)
            print("  条件:")
            print(f"    - 价格: {min_price}-{max_price}元")
            print(f"    - 成交额: >= {min_amount/1e8:.1f}亿元")
            print(f"    - 5周成交量均线: 向上")
            print(f"    - 偏离度: {min_deviation}% ~ {max_deviation}%")
        
        passed_stocks_step5, stats_step5 = self.manager.filter_stocks_by_price_volume(
            weekly_data=weekly_data,
            passed_from_step4=passed_stocks_step4,
            min_price=min_price,
            max_price=max_price,
            min_amount=min_amount,
            min_deviation=min_deviation,
            max_deviation=max_deviation,
            min_data_points=min_data_points_step5
        )
        self.step5_result = (passed_stocks_step5, stats_step5)
        
        if verbose:
            print(f"\n✓ 筛选完成:")
            print(f"  总数: {stats_step5['total']}")
            print(f"  通过: {stats_step5['passed']}")
            print(f"  失败: {stats_step5['failed']}")
            print(f"  通过率: {stats_step5['pass_rate']:.2f}%")
            print(f"\n  失败原因:")
            print(f"    不在第四步: {stats_step5['reasons']['not_in_step4']}")
            print(f"    价格不符: {stats_step5['reasons']['price_out_of_range']}")
            print(f"    成交额不足: {stats_step5['reasons']['amount_too_low']}")
            print(f"    数据不足: {stats_step5['reasons']['insufficient_data']}")
            print(f"    MA5不向上: {stats_step5['reasons']['volume_ma5_not_rising']}")
            print(f"    偏离度不符: {stats_step5['reasons']['deviation_out_of_range']}")
        
        # ====================================================================
        # 显示最终结果
        # ====================================================================
        if verbose:
            print(f"\n  通过筛选的股票（按偏离度绝对值排序）:")
            if passed_stocks_step5:
                for i, stock in enumerate(passed_stocks_step5, start=1):
                    print(f"    {i:2d}. {stock['code']}: "
                          f"价格={stock['close']:6.2f}元, "
                          f"成交额={stock['amount']/1e8:5.2f}亿元, "
                          f"偏离度={stock['deviation']:5.2f}%")
            else:
                print("    没有股票通过筛选")
        
        # ====================================================================
        # 总结
        # ====================================================================
        if verbose:
            print("\n" + "=" * 80)
            print("流程总结")
            print("=" * 80)
            print(f"步骤1: 获取全市场股票列表 → {len(all_stocks)} 只")
            print(f"步骤2: 筛选沪深主板、非ST、上市2年以上 → {len(filtered_stocks)} 只")
            print(f"步骤3: 获取周K数据（前复权、多线程） → {len(weekly_data)} 只成功")
            print(f"步骤4: 筛选站上{ma_period}周均线 → {len(passed_stocks_step4)} 只通过")
            print(f"步骤5: 根据价格、成交额和成交量均线筛选 → {len(passed_stocks_step5)} 只通过")
            print("=" * 80)
        
        return passed_stocks_step5
    
    def _print_header(self):
        """打印标题"""
        print("\n" + "=" * 80)
        print("周K线选股策略 - 固定五步流程")
        print("=" * 80)
        print("\n步骤说明:")
        print("  1. 获取全市场股票列表（包含上市时间）")
        print("  2. 筛选沪深主板、非ST、上市2年以上")
        print("  3. 获取周K数据（前复权、多线程）")
        print("  4. 筛选站上25周均线的股票")
        print("  5. 根据价格、成交额和成交量均线筛选")
        print("=" * 80)
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取选股流程的统计摘要
        
        Returns:
            包含各步骤统计信息的字典
        """
        summary = {
            'step1': {
                'total': len(self.step1_result[0]) if self.step1_result else 0,
                'source': self.step1_result[1] if self.step1_result else None
            },
            'step2': {
                'total': len(self.step2_result) if self.step2_result else 0
            },
            'step3': {
                'total': len(self.step3_result[0]) if self.step3_result else 0,
                'source': self.step3_result[1] if self.step3_result else None
            },
            'step4': {
                'passed': len(self.step4_result[0]) if self.step4_result else 0,
                'stats': self.step4_result[1] if self.step4_result else None
            },
            'step5': {
                'passed': len(self.step5_result[0]) if self.step5_result else 0,
                'stats': self.step5_result[1] if self.step5_result else None
            }
        }
        return summary


def run_weekly_selection(
    max_stocks: int = None,
    weeks: int = 104,
    max_workers: int = 5,
    ma_period: int = 25,
    min_data_points_step4: int = 30,
    min_price: float = 3.0,
    max_price: float = 70.0,
    min_amount: float = 5e8,
    min_deviation: float = -3.0,
    max_deviation: float = 7.0,
    min_data_points_step5: int = 65,
    verbose: bool = True
) -> List[Dict[str, Any]]:
    """
    快捷函数：运行完整的五步选股流程
    
    Args:
        max_stocks: 最多处理的股票数量（用于测试，None表示全部）
        weeks: 获取周K数据的周数，默认104周（2年）
        max_workers: 多线程并发数，默认5
        ma_period: 均线周期，默认25周
        min_data_points_step4: 步骤4最小数据点数，默认30周
        min_price: 最低价格（人民币元），默认3元
        max_price: 最高价格（人民币元），默认70元
        min_amount: 最低成交额（人民币元），默认5亿元
        min_deviation: 最小偏离度，默认-3%
        max_deviation: 最大偏离度，默认7%
        min_data_points_step5: 步骤5最小数据点数，默认65周
        verbose: 是否打印详细信息，默认True
        
    Returns:
        最终通过筛选的股票列表
        
    Example:
        >>> # 使用默认参数
        >>> stocks = run_weekly_selection()
        
        >>> # 自定义参数
        >>> stocks = run_weekly_selection(
        ...     max_stocks=100,  # 只处理前100只股票（测试用）
        ...     min_price=5.0,   # 最低价格5元
        ...     max_price=50.0,  # 最高价格50元
        ...     min_amount=3e8   # 最低成交额3亿元
        ... )
    """
    selector = WeeklyStockSelector()
    return selector.run(
        max_stocks=max_stocks,
        weeks=weeks,
        max_workers=max_workers,
        ma_period=ma_period,
        min_data_points_step4=min_data_points_step4,
        min_price=min_price,
        max_price=max_price,
        min_amount=min_amount,
        min_deviation=min_deviation,
        max_deviation=max_deviation,
        min_data_points_step5=min_data_points_step5,
        verbose=verbose
    )


if __name__ == '__main__':
    # 运行选股（测试模式：只处理前20只股票）
    stocks = run_weekly_selection(
        max_stocks=20,
        verbose=True
    )
    
    print(f"\n最终选出 {len(stocks)} 只股票")
