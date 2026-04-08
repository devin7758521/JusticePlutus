# -*- coding: utf-8 -*-
"""
周K线选股策略 - 方案A（稳健型）
================================================================================

方案A特点：
1. 使用上周的完整周K数据（数据准确，无预测误差）
2. 五步流程筛选股票
3. 整合AI分析和新闻功能

步骤：
1. 获取全市场股票列表（包含上市时间）
2. 筛选沪深主板、非ST、上市2年以上
3. 获取周K数据（前复权、多线程）
4. 筛选站上25周均线的股票
5. 根据价格、成交额和成交量均线筛选
6. AI分析和新闻整合（可选）

================================================================================
"""

from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
from datetime import datetime
from pathlib import Path

from data_provider import DataFetcherManager
from weekly_stock_selector import WeeklyStockSelector


class WeeklyStockSelectorPlanA(WeeklyStockSelector):
    """
    周K线选股策略 - 方案A（稳健型）
    
    继承自 WeeklyStockSelector，增加AI分析和新闻整合功能
    """
    
    def __init__(self):
        """初始化选股器"""
        super().__init__()
        
        # AI分析和新闻相关
        self.pipeline = None
        self.ai_results = []
    
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
        min_data_points_step5: int = 65,
        enable_ai_analysis: bool = False,
        enable_news_search: bool = False,
        enable_push: bool = False,
        verbose: bool = True
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        运行完整的五步选股流程 + AI分析（可选）
        
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
            enable_ai_analysis: 是否启用AI分析，默认False
            enable_news_search: 是否启用新闻搜索，默认False
            enable_push: 是否推送到企业微信，默认False
            verbose: 是否打印详细信息，默认True
            
        Returns:
            Tuple[List[Dict], List[Dict]]: 
                - 通过筛选的股票列表
                - AI分析结果列表（如果启用）
        """
        import time
        from weekly_push import push_workflow_start, push_workflow_complete
        
        start_time = time.time()
        error_msg = None
        
        # 推送启动消息
        if enable_push:
            push_workflow_start(
                plan_type="A",
                max_stocks=max_stocks,
                enable_ai=enable_ai_analysis,
                enable_news=enable_news_search,
                verbose=verbose
            )
        
        try:
            # 运行五步流程
            passed_stocks = self.run(
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
            
            # AI分析和新闻整合（可选）
            ai_results = []
            if enable_ai_analysis and passed_stocks:
                if verbose:
                    print("\n" + "=" * 80)
                    print("步骤6: AI分析和新闻整合")
                    print("=" * 80)
                
                ai_results = self._run_ai_analysis(
                    stocks=passed_stocks,
                    enable_news_search=enable_news_search,
                    verbose=verbose
                )
            
            # 推送选股结果到企业微信（可选）
            if enable_push and passed_stocks:
                from weekly_push import push_weekly_selection_to_wechat
                push_weekly_selection_to_wechat(
                    stocks=passed_stocks,
                    ai_results=ai_results,
                    plan_type="A",
                    verbose=verbose
                )
            
            return passed_stocks, ai_results
            
        except Exception as e:
            error_msg = str(e)
            raise
            
        finally:
            # 推送完成消息
            if enable_push:
                elapsed_time = f"{time.time() - start_time:.1f}秒"
                push_workflow_complete(
                    plan_type="A",
                    total_stocks=len(self.weekly_data) if hasattr(self, 'weekly_data') else 0,
                    passed_stocks=len(passed_stocks) if 'passed_stocks' in locals() else 0,
                    elapsed_time=elapsed_time,
                    error=error_msg,
                    verbose=verbose
                )
    
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
                query_source="weekly_selector_plan_a"
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


def run_weekly_selection_plan_a(
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
    enable_ai_analysis: bool = False,
    enable_news_search: bool = False,
    verbose: bool = True
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    快捷函数：运行方案A（稳健型）
    
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
        enable_ai_analysis: 是否启用AI分析，默认False
        enable_news_search: 是否启用新闻搜索，默认False
        verbose: 是否打印详细信息，默认True
        
    Returns:
        Tuple[List[Dict], List[Dict]]: 
            - 通过筛选的股票列表
            - AI分析结果列表（如果启用）
            
    Example:
        >>> # 使用默认参数（不启用AI分析）
        >>> stocks, _ = run_weekly_selection_plan_a()
        
        >>> # 启用AI分析和新闻搜索
        >>> stocks, ai_results = run_weekly_selection_plan_a(
        ...     max_stocks=100,
        ...     enable_ai_analysis=True,
        ...     enable_news_search=True
        ... )
    """
    selector = WeeklyStockSelectorPlanA()
    return selector.run_with_ai_analysis(
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
        enable_ai_analysis=enable_ai_analysis,
        enable_news_search=enable_news_search,
        verbose=verbose
    )


if __name__ == '__main__':
    # 运行选股（测试模式：只处理前20只股票，不启用AI分析）
    stocks, ai_results = run_weekly_selection_plan_a(
        max_stocks=20,
        enable_ai_analysis=False,
        verbose=True
    )
    
    print(f"\n最终选出 {len(stocks)} 只股票")
    if ai_results:
        print(f"AI分析结果 {len(ai_results)} 只股票")
