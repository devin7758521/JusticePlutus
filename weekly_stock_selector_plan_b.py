# -*- coding: utf-8 -*-
"""
周K线选股策略 - 方案B（激进型）
================================================================================

方案B特点：
1. 第五步：只筛选价格和成交额
2. 第六步：获取实时日K数据，拟合本周周K
3. 权重分配：周一高权重，逐渐下降，周五不给权重
4. 根据成交量均线和偏离度筛选

权重分配策略：
- 周一：40% 权重（最重要，市场情绪最强烈）
- 周二：30% 权重
- 周三：20% 权重
- 周四：10% 权重
- 周五：0% 权重（不参与拟合，使用上周完整数据）

================================================================================
"""

from typing import List, Dict, Any, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from data_provider import DataFetcherManager
from weekly_stock_selector import WeeklyStockSelector
from weekly_config import (
    get_fitting_multiplier,
    get_deviation_range,
    get_price_range,
    get_turnover_threshold,
    get_volume_ma_periods,
    get_price_ma_period,
    get_min_data_weeks,
    get_thread_config,
    get_data_source_priority,
)


class WeeklyStockSelectorPlanB(WeeklyStockSelector):
    """
    周K线选股策略 - 方案B（激进型）
    
    继承自 WeeklyStockSelector，增加周K拟合功能
    """
    
    def __init__(self):
        """初始化选股器"""
        super().__init__()
        
        # 从配置文件读取参数
        self.deviation_range = get_deviation_range()
        self.price_range = get_price_range()
        self.turnover_threshold = get_turnover_threshold()
        self.volume_ma_periods = get_volume_ma_periods()
        self.price_ma_period = get_price_ma_period()
        self.min_data_weeks = get_min_data_weeks()
        self.thread_config = get_thread_config()
        self.data_source_priority = get_data_source_priority()
        
        # AI分析和新闻相关
        self.pipeline = None
        self.ai_results = []
    
    def run_plan_b(
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
        min_data_points_step6: int = 65,
        verbose: bool = True
    ) -> List[Dict[str, Any]]:
        """
        运行方案B（激进型）选股流程
        
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
            min_data_points_step6: 步骤6最小数据点数，默认65周
            verbose: 是否打印详细信息，默认True
            
        Returns:
            通过筛选的股票列表
        """
        if verbose:
            self._print_header_plan_b()
        
        # ====================================================================
        # 步骤1-4: 与方案A相同
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
        
        if verbose:
            print("\n" + "=" * 80)
            print("步骤2: 筛选沪深主板、非ST、上市2年以上")
            print("=" * 80)
        
        filtered_stocks = self.manager.filter_main_board_stocks(all_stocks)
        self.step2_result = filtered_stocks
        
        if verbose:
            print(f"✓ 筛选后剩余 {len(filtered_stocks)} 只股票")
        
        if verbose:
            print("\n" + "=" * 80)
            print("步骤3: 获取周K数据（前复权、多线程）")
            print("=" * 80)
        
        stock_codes = [stock['code'] for stock in filtered_stocks]
        
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
            print(f"  通过率: {stats_step4['pass_rate']:.2f}%")
        
        # ====================================================================
        # 步骤5: 只筛选价格和成交额
        # ====================================================================
        if verbose:
            print("\n" + "=" * 80)
            print("步骤5: 根据价格和成交额筛选")
            print("=" * 80)
            print("  条件:")
            print(f"    - 价格: {min_price}-{max_price}元")
            print(f"    - 成交额: >= {min_amount/1e8:.1f}亿元")
        
        passed_stocks_step5 = self._filter_by_price_and_amount(
            weekly_data=weekly_data,
            passed_from_step4=passed_stocks_step4,
            min_price=min_price,
            max_price=max_price,
            min_amount=min_amount,
            verbose=verbose
        )
        
        if verbose:
            print(f"\n✓ 筛选完成: 通过 {len(passed_stocks_step5)} 只股票")
        
        # ====================================================================
        # 步骤6: 获取实时日K数据，拟合本周周K，筛选
        # ====================================================================
        if verbose:
            print("\n" + "=" * 80)
            print("步骤6: 获取实时日K数据，拟合本周周K")
            print("=" * 80)
        
        passed_stocks_step6 = self._fit_and_filter_weekly_k(
            weekly_data=weekly_data,
            passed_from_step5=passed_stocks_step5,
            min_deviation=min_deviation,
            max_deviation=max_deviation,
            min_data_points=min_data_points_step6,
            max_workers=max_workers,
            verbose=verbose
        )
        
        if verbose:
            print(f"\n✓ 最终筛选完成: 通过 {len(passed_stocks_step6)} 只股票")
        
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
            print(f"步骤5: 根据价格和成交额筛选 → {len(passed_stocks_step5)} 只通过")
            print(f"步骤6: 拟合周K并筛选 → {len(passed_stocks_step6)} 只通过")
            print("=" * 80)
        
        return passed_stocks_step6
    
    def _filter_by_price_and_amount(
        self,
        weekly_data: Dict[str, pd.DataFrame],
        passed_from_step4: List[Dict[str, Any]],
        min_price: float,
        max_price: float,
        min_amount: float,
        verbose: bool = True
    ) -> List[Dict[str, Any]]:
        """
        步骤5: 只筛选价格和成交额
        
        Args:
            weekly_data: 股票代码->周K线数据的字典
            passed_from_step4: 第四步筛选通过的股票列表
            min_price: 最低价格
            max_price: 最高价格
            min_amount: 最低成交额
            verbose: 是否打印详细信息
            
        Returns:
            通过筛选的股票列表
        """
        passed_stocks = []
        step4_codes = {stock['code'] for stock in passed_from_step4}
        
        for code, df in weekly_data.items():
            try:
                if code not in step4_codes:
                    continue
                
                if df is None or len(df) < 1:
                    continue
                
                df_sorted = df.sort_values('date')
                latest = df_sorted.iloc[-1]
                
                latest_close = latest['close']
                latest_amount = latest['amount']
                
                if not (min_price <= latest_close <= max_price):
                    continue
                
                if latest_amount < min_amount:
                    continue
                
                passed_stocks.append({
                    'code': code,
                    'close': latest_close,
                    'amount': latest_amount
                })
                
            except Exception as e:
                continue
        
        return passed_stocks
    
    def _fit_and_filter_weekly_k(
        self,
        weekly_data: Dict[str, pd.DataFrame],
        passed_from_step5: List[Dict[str, Any]],
        min_deviation: float,
        max_deviation: float,
        min_data_points: int,
        max_workers: int,
        verbose: bool = True
    ) -> List[Dict[str, Any]]:
        """
        步骤6: 获取实时日K数据，拟合本周周K，筛选
        
        Args:
            weekly_data: 股票代码->周K线数据的字典
            passed_from_step5: 第五步筛选通过的股票列表
            min_deviation: 最小偏离度
            max_deviation: 最大偏离度
            min_data_points: 最小数据点数
            max_workers: 最大并发线程数
            verbose: 是否打印详细信息
            
        Returns:
            通过筛选的股票列表
        """
        # 获取今天是星期几（0=周一，4=周五）
        today_weekday = datetime.now().weekday()
        
        # 如果是周五，直接使用上周数据，不拟合
        if today_weekday == 4:
            if verbose:
                print("  今天是周五，使用上周完整周K数据，不拟合")
            
            # 直接从周K数据中筛选
            return self._filter_by_volume_ma(
                weekly_data=weekly_data,
                passed_from_step5=passed_from_step5,
                min_deviation=min_deviation,
                max_deviation=max_deviation,
                min_data_points=min_data_points,
                verbose=verbose
            )
        
        # 周一到周四：获取日K数据，拟合本周周K
        if verbose:
            print(f"  今天是周{['一','二','三','四','五'][today_weekday]}，开始拟合本周周K")
            print(f"  权重分配: {self.weekday_weights[today_weekday]*100:.0f}%")
        
        # 提取股票代码
        stock_codes = [stock['code'] for stock in passed_from_step5]
        
        # 获取本周的日K数据（最近5个交易日）
        if verbose:
            print(f"  获取本周日K数据...")
        
        daily_data, source = self.manager.get_daily_data_batch_with_failover(
            stock_codes=stock_codes,
            days=5,
            max_workers=max_workers
        )
        
        if verbose:
            print(f"  ✓ 成功获取 {len(daily_data)} 只股票的日K数据")
        
        # 拟合本周周K
        fitted_weekly_data = self._fit_current_week_k(
            weekly_data=weekly_data,
            daily_data=daily_data,
            passed_from_step5=passed_from_step5,
            today_weekday=today_weekday,
            verbose=verbose
        )
        
        # 根据拟合后的周K数据筛选
        return self._filter_by_volume_ma(
            weekly_data=fitted_weekly_data,
            passed_from_step5=passed_from_step5,
            min_deviation=min_deviation,
            max_deviation=max_deviation,
            min_data_points=min_data_points,
            verbose=verbose
        )
    
    def _fit_current_week_k(
        self,
        weekly_data: Dict[str, pd.DataFrame],
        daily_data: Dict[str, pd.DataFrame],
        passed_from_step5: List[Dict[str, Any]],
        today_weekday: int,
        verbose: bool = True
    ) -> Dict[str, pd.DataFrame]:
        """
        拟合本周周K数据
        
        Args:
            weekly_data: 历史周K数据
            daily_data: 本周日K数据
            passed_from_step5: 第五步筛选通过的股票列表
            today_weekday: 今天是星期几（0=周一，4=周五）
            verbose: 是否打印详细信息
            
        Returns:
            拟合后的周K数据字典
        """
        fitted_weekly_data = {}
        
        for stock in passed_from_step5:
            code = stock['code']
            
            try:
                # 获取历史周K数据
                historical_weekly = weekly_data.get(code)
                if historical_weekly is None or len(historical_weekly) < 60:
                    continue
                
                # 获取本周日K数据
                current_daily = daily_data.get(code)
                if current_daily is None or len(current_daily) < 1:
                    # 如果没有日K数据，使用上周数据
                    fitted_weekly_data[code] = historical_weekly.copy()
                    continue
                
                # 拟合本周周K
                fitted_weekly = self._fit_single_weekly_k(
                    historical_weekly=historical_weekly,
                    current_daily=current_daily,
                    weekday=today_weekday
                )
                
                if fitted_weekly is not None:
                    fitted_weekly_data[code] = fitted_weekly
                    
            except Exception as e:
                if historical_weekly is not None:
                    fitted_weekly_data[code] = historical_weekly.copy()
                continue
        
        if verbose:
            print(f"  ✓ 拟合完成，共 {len(fitted_weekly_data)} 只股票")
        
        return fitted_weekly_data
    
    def _fit_single_weekly_k(
        self,
        historical_weekly: pd.DataFrame,
        current_daily: pd.DataFrame,
        weekday: int
    ) -> pd.DataFrame:
        """
        拟合单只股票的本周周K
        
        拟合策略（改进版 - 放大系数）：
        1. 价格指标（开盘价、最高价、最低价、收盘价）：使用实时数据，不拟合
        2. 成交量：使用本周累计成交量 × 放大系数
        3. 成交额：不拟合（第五步已经筛选过）
        4. 5周成交量均线：根据放大后的成交量重新计算
        5. 60周成交量均线：不变（周期太长）
        6. 偏离值：根据新的5周成交量均线重新计算
        
        Args:
            historical_weekly: 历史周K数据
            current_daily: 本周日K数据
            weekday: 当前周几（0=周一, 1=周二, ..., 4=周五）
            
        Returns:
            拟合后的周K数据
        """
        # 复制历史数据
        fitted = historical_weekly.copy()
        
        # 计算本周的实时周K数据
        daily_sorted = current_daily.sort_values('date')
        
        # 价格使用实时数据（不拟合）
        current_week_open = daily_sorted.iloc[0]['open']
        current_week_high = daily_sorted['high'].max()
        current_week_low = daily_sorted['low'].min()
        current_week_close = daily_sorted.iloc[-1]['close']
        
        # 成交量使用本周累计值 × 放大系数
        current_week_volume = daily_sorted['volume'].sum()
        multiplier = get_fitting_multiplier(weekday)
        fitted_volume = current_week_volume * multiplier
        
        # 成交额不拟合（第五步已经筛选过）
        current_week_amount = daily_sorted['amount'].sum()
        
        # 更新最后一行数据
        fitted.iloc[-1, fitted.columns.get_loc('open')] = current_week_open
        fitted.iloc[-1, fitted.columns.get_loc('high')] = current_week_high
        fitted.iloc[-1, fitted.columns.get_loc('low')] = current_week_low
        fitted.iloc[-1, fitted.columns.get_loc('close')] = current_week_close
        fitted.iloc[-1, fitted.columns.get_loc('volume')] = fitted_volume
        fitted.iloc[-1, fitted.columns.get_loc('amount')] = current_week_amount
        
        # 注意：均线指标会在筛选时重新计算
        # - 5周成交量均线：会根据放大后的成交量重新计算
        # - 60周成交量均线：不变（周期太长）
        # - 偏离值：会根据新的5周成交量均线重新计算
        
        return fitted
    
    def _filter_by_volume_ma(
        self,
        weekly_data: Dict[str, pd.DataFrame],
        passed_from_step5: List[Dict[str, Any]],
        min_deviation: float,
        max_deviation: float,
        min_data_points: int,
        verbose: bool = True
    ) -> List[Dict[str, Any]]:
        """
        根据成交量均线和偏离度筛选
        
        Args:
            weekly_data: 周K数据（可能是拟合后的）
            passed_from_step5: 第五步筛选通过的股票列表
            min_deviation: 最小偏离度
            max_deviation: 最大偏离度
            min_data_points: 最小数据点数
            verbose: 是否打印详细信息
            
        Returns:
            通过筛选的股票列表
        """
        passed_stocks = []
        step5_codes = {stock['code'] for stock in passed_from_step5}
        
        for code, df in weekly_data.items():
            try:
                if code not in step5_codes:
                    continue
                
                if df is None or len(df) < min_data_points:
                    continue
                
                df_sorted = df.sort_values('date')
                
                # 计算成交量均线
                df_sorted['volume_ma5'] = df_sorted['volume'].rolling(
                    window=5, min_periods=5
                ).mean()
                
                df_sorted['volume_ma60'] = df_sorted['volume'].rolling(
                    window=60, min_periods=60
                ).mean()
                
                # 获取最新均线值
                latest_volume_ma5 = df_sorted.iloc[-1]['volume_ma5']
                prev_volume_ma5 = df_sorted.iloc[-2]['volume_ma5']
                latest_volume_ma60 = df_sorted.iloc[-1]['volume_ma60']
                
                if pd.isna(latest_volume_ma5) or pd.isna(prev_volume_ma5) or pd.isna(latest_volume_ma60):
                    continue
                
                # 条件1: 5周成交量均线向上
                if latest_volume_ma5 <= prev_volume_ma5:
                    continue
                
                # 条件2: 偏离度在范围内
                deviation = (latest_volume_ma5 - latest_volume_ma60) / latest_volume_ma60 * 100
                
                if not (min_deviation <= deviation <= max_deviation):
                    continue
                
                # 通过筛选
                latest = df_sorted.iloc[-1]
                passed_stocks.append({
                    'code': code,
                    'close': latest['close'],
                    'amount': latest['amount'],
                    'volume_ma5': latest_volume_ma5,
                    'volume_ma60': latest_volume_ma60,
                    'deviation': deviation,
                    'data_points': len(df_sorted)
                })
                
            except Exception as e:
                continue
        
        # 按偏离度绝对值排序
        passed_stocks.sort(key=lambda x: abs(x['deviation']))
        
        if verbose:
            print(f"\n  通过筛选的股票（按偏离度绝对值排序）:")
            if passed_stocks:
                for i, stock in enumerate(passed_stocks[:10], start=1):
                    print(f"    {i:2d}. {stock['code']}: "
                          f"价格={stock['close']:6.2f}元, "
                          f"成交额={stock['amount']/1e8:5.2f}亿元, "
                          f"偏离度={stock['deviation']:5.2f}%")
            else:
                print("    没有股票通过筛选")
        
        return passed_stocks
    
    def _print_header_plan_b(self):
        """打印方案B标题"""
        print("\n" + "=" * 80)
        print("周K线选股策略 - 方案B（激进型）")
        print("=" * 80)
        print("\n步骤说明:")
        print("  1. 获取全市场股票列表（包含上市时间）")
        print("  2. 筛选沪深主板、非ST、上市2年以上")
        print("  3. 获取周K数据（前复权、多线程）")
        print("  4. 筛选站上25周均线的股票")
        print("  5. 根据价格和成交额筛选")
        print("  6. 获取实时日K数据，拟合本周周K，筛选")
        print("\n放大系数:")
        print("  周一: 15% | 周二: 10% | 周三: 5% | 周四: 3% | 周五: 0%")
        print("=" * 80)
    
    def run_with_ai_analysis(
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
        min_data_points_step6: int = 65,
        enable_ai_analysis: bool = False,
        enable_news_search: bool = False,
        enable_push: bool = False,
        verbose: bool = True
    ):
        """
        运行完整的六步选股流程 + AI分析（可选）
        
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
            min_data_points_step6: 步骤6最小数据点数，默认65周
            enable_ai_analysis: 是否启用AI分析，默认False
            enable_news_search: 是否启用新闻搜索，默认False
            enable_push: 是否推送到企业微信，默认False
            verbose: 是否打印详细信息，默认True
            
        Returns:
            Tuple[List[Dict], List[Dict]]: 
                - 通过筛选的股票列表
                - AI分析结果列表（如果启用）
        """
        # 运行六步流程
        passed_stocks = self.run_plan_b(
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
            min_data_points_step6=min_data_points_step6,
            verbose=verbose
        )
        
        # AI分析和新闻整合（可选）
        ai_results = []
        if enable_ai_analysis and passed_stocks:
            if verbose:
                print("\n" + "=" * 80)
                print("步骤7: AI分析和新闻整合")
                print("=" * 80)
            
            ai_results = self._run_ai_analysis(
                stocks=passed_stocks,
                enable_news_search=enable_news_search,
                verbose=verbose
            )
        
        # 推送到企业微信（可选）
        if enable_push and passed_stocks:
            from weekly_push import push_weekly_selection_to_wechat
            push_weekly_selection_to_wechat(
                stocks=passed_stocks,
                ai_results=ai_results,
                plan_type="B",
                verbose=verbose
            )
        
        return passed_stocks, ai_results
    
    def _run_ai_analysis(
        self,
        stocks: List[Dict[str, Any]],
        enable_news_search: bool = False,
        verbose: bool = True
    ) -> List[Dict[str, Any]]:
        """
        对筛选出的股票进行AI分析
        
        Args:
            stocks: 通过筛选的股票列表
            enable_news_search: 是否启用新闻搜索
            verbose: 是否打印详细信息
            
        Returns:
            AI分析结果列表
        """
        try:
            # 导入必要的模块
            from src.core.pipeline import StockAnalysisPipeline
            from src.config import get_config
            
            # 初始化pipeline
            config = get_config()
            config.max_workers = 1  # 单线程处理
            config.single_stock_notify = False  # 不发送通知
            config.market_review_enabled = False
            config.trading_day_check_enabled = False
            config.backtest_enabled = False
            
            self.pipeline = StockAnalysisPipeline(
                config=config,
                max_workers=1,
                query_source="weekly_selector_plan_b"
            )
            
            # 提取股票代码
            stock_codes = [stock['code'] for stock in stocks]
            
            if verbose:
                print(f"开始AI分析 {len(stock_codes)} 只股票...")
                if enable_news_search:
                    print("  新闻搜索: 已启用")
                else:
                    print("  新闻搜索: 未启用")
            
            # 运行分析
            results = self.pipeline.run(
                stock_codes=stock_codes,
                dry_run=False,
                send_notification=False
            )
            
            # 转换结果
            ai_results = []
            for result in results:
                ai_results.append({
                    'code': result.code,
                    'name': result.name,
                    'sentiment_score': result.sentiment_score,
                    'operation_advice': result.operation_advice,
                    'analysis_summary': result.analysis_summary,
                    'buy_reason': getattr(result, 'buy_reason', ''),
                    'key_points': getattr(result, 'key_points', ''),
                    'risk_warning': getattr(result, 'risk_warning', ''),
                    'dashboard': result.dashboard
                })
            
            if verbose:
                print(f"✓ AI分析完成，共 {len(ai_results)} 只股票")
            
            return ai_results
            
        except Exception as e:
            if verbose:
                print(f"✗ AI分析失败: {e}")
            return []


def run_weekly_selection_plan_b(
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
    min_data_points_step6: int = 65,
    verbose: bool = True
) -> List[Dict[str, Any]]:
    """
    快捷函数：运行方案B（激进型）
    
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
        min_data_points_step6: 步骤6最小数据点数，默认65周
        verbose: 是否打印详细信息，默认True
        
    Returns:
        通过筛选的股票列表
        
    Example:
        >>> # 使用默认参数
        >>> stocks = run_weekly_selection_plan_b()
        
        >>> # 自定义参数
        >>> stocks = run_weekly_selection_plan_b(
        ...     max_stocks=100,
        ...     min_price=5.0,
        ...     max_price=50.0
        ... )
    """
    selector = WeeklyStockSelectorPlanB()
    return selector.run_plan_b(
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
        min_data_points_step6=min_data_points_step6,
        verbose=verbose
    )


if __name__ == '__main__':
    # 运行选股（测试模式：只处理前20只股票）
    stocks = run_weekly_selection_plan_b(
        max_stocks=20,
        verbose=True
    )
    
    print(f"\n最终选出 {len(stocks)} 只股票")
