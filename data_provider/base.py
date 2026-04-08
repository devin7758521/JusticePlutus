# -*- coding: utf-8 -*-
"""
===================================
数据源基类与管理器
===================================

设计模式：策略模式 (Strategy Pattern)
- BaseFetcher: 抽象基类，定义统一接口
- DataFetcherManager: 策略管理器，实现自动切换

防封禁策略：
1. 每个 Fetcher 内置流控逻辑
2. 失败自动切换到下一个数据源
3. 指数退避重试机制
"""

import logging
import random
import time
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Optional, List, Tuple, Dict, Any

import pandas as pd
import numpy as np
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.data.stock_mapping import STOCK_NAME_MAP, is_meaningful_stock_name

# 配置日志
logger = logging.getLogger(__name__)


# === 标准化列名定义 ===
STANDARD_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg']


def unwrap_exception(exc: Exception) -> Exception:
    """
    Follow chained exceptions and return the deepest non-cyclic cause.
    """
    current = exc
    visited = set()

    while current is not None and id(current) not in visited:
        visited.add(id(current))
        next_exc = current.__cause__ or current.__context__
        if next_exc is None:
            break
        current = next_exc

    return current


def summarize_exception(exc: Exception) -> Tuple[str, str]:
    """
    Build a stable summary for logs while preserving the application-layer message.
    """
    root = unwrap_exception(exc)
    error_type = type(root).__name__
    message = str(exc).strip() or str(root).strip() or error_type
    return error_type, " ".join(message.split())


def normalize_stock_code(stock_code: str) -> str:
    """
    Normalize stock code by stripping exchange prefixes/suffixes.

    Accepted formats and their normalized results:
    - '600519'      -> '600519'   (already clean)
    - 'SH600519'    -> '600519'   (strip SH prefix)
    - 'SZ000001'    -> '000001'   (strip SZ prefix)
    - 'BJ920748'    -> '920748'   (strip BJ prefix, BSE)
    - 'sh600519'    -> '600519'   (case-insensitive)
    - 'sh.600519'   -> '600519'   (Baostock format: exchange.code)
    - '600519.SH'   -> '600519'   (strip .SH suffix)
    - '000001.SZ'   -> '000001'   (strip .SZ suffix)
    - '920748.BJ'   -> '920748'   (strip .BJ suffix, BSE)
    - 'HK00700'     -> 'HK00700'  (keep HK prefix for HK stocks)
    - 'AAPL'        -> 'AAPL'     (keep US stock ticker as-is)

    This function is applied at the DataProviderManager layer so that
    all individual fetchers receive a clean 6-digit code (for A-shares/ETFs).
    """
    code = stock_code.strip()
    upper = code.upper()

    # Handle Baostock format: sh.600519, sz.000001, bj.430047
    if '.' in code:
        parts = code.split('.', 1)
        if len(parts) == 2:
            prefix, stock_num = parts
            prefix_upper = prefix.upper()
            # Baostock format: exchange.code (e.g., sh.600519)
            if prefix_upper in ('SH', 'SZ', 'BJ') and stock_num.isdigit():
                return stock_num
            # Standard suffix format: code.exchange (e.g., 600519.SH)
            if stock_num.upper() in ('SH', 'SZ', 'SS', 'BJ') and prefix.isdigit():
                return prefix

    # Strip SH/SZ prefix (e.g. SH600519 -> 600519)
    if upper.startswith(('SH', 'SZ')) and not upper.startswith('SH.') and not upper.startswith('SZ.'):
        candidate = code[2:]
        # Only strip if the remainder looks like a valid numeric code
        if candidate.isdigit() and len(candidate) in (5, 6):
            return candidate

    # Strip BJ prefix (e.g. BJ920748 -> 920748)
    if upper.startswith('BJ') and not upper.startswith('BJ.'):
        candidate = code[2:]
        if candidate.isdigit() and len(candidate) == 6:
            return candidate

    return code


def is_bse_code(code: str) -> bool:
    """
    Check if the code is a Beijing Stock Exchange (BSE) A-share code.

    BSE rules:
    - Old format (pre-2024): 8xxxxx (e.g. 838163), 4xxxxx (e.g. 430047)
    - New format (2024+, post full migration Oct 2025): 920xxx+
    Note: 900xxx are Shanghai B-shares, NOT BSE — must return False.
    """
    c = (code or "").strip().split(".")[0]
    if len(c) != 6 or not c.isdigit():
        return False
    return c.startswith(("8", "4")) or c.startswith("92")

def is_st_stock(name: str) -> bool:
    """
    Check if the stock is an ST or *ST stock based on its name.

    ST stocks have special trading rules and typically a ±5% limit.
    """
    n = (name or "").upper()
    return 'ST' in n

def is_kc_cy_stock(code: str) -> bool:
    """
    Check if the stock is a STAR Market (科创板) or ChiNext (创业板) stock based on its code.

    - STAR Market: Codes starting with 688
    - ChiNext: Codes starting with 300
    Both have a ±20% limit.
    """
    c = (code or "").strip().split(".")[0]
    return c.startswith("688") or c.startswith("30")


def canonical_stock_code(code: str) -> str:
    """
    Return the canonical (uppercase) form of a stock code.

    This is a display/storage layer concern, distinct from normalize_stock_code
    which strips exchange prefixes. Apply at system input boundaries to ensure
    consistent case across BOT, WEB UI, API, and CLI paths (Issue #355).

    Examples:
        'aapl'    -> 'AAPL'
        'AAPL'    -> 'AAPL'
        '600519'  -> '600519'  (digits are unchanged)
        'hk00700' -> 'HK00700'
    """
    return (code or "").strip().upper()


class DataFetchError(Exception):
    """数据获取异常基类"""
    pass


class RateLimitError(DataFetchError):
    """API 速率限制异常"""
    pass


class DataSourceUnavailableError(DataFetchError):
    """数据源不可用异常"""
    pass


class BaseFetcher(ABC):
    """
    数据源抽象基类
    
    职责：
    1. 定义统一的数据获取接口
    2. 提供数据标准化方法
    3. 实现通用的技术指标计算
    
    子类实现：
    - _fetch_raw_data(): 从具体数据源获取原始数据
    - _normalize_data(): 将原始数据转换为标准格式
    """
    
    name: str = "BaseFetcher"
    priority: int = 99  # 优先级数字越小越优先
    
    @abstractmethod
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        从数据源获取原始数据（子类必须实现）
        
        Args:
            stock_code: 股票代码，如 '600519', '000001'
            start_date: 开始日期，格式 'YYYY-MM-DD'
            end_date: 结束日期，格式 'YYYY-MM-DD'
            
        Returns:
            原始数据 DataFrame（列名因数据源而异）
        """
        pass
    
    @abstractmethod
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        标准化数据列名（子类必须实现）

        将不同数据源的列名统一为：
        ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg']
        """
        pass

    def get_main_indices(self, region: str = "cn") -> Optional[List[Dict[str, Any]]]:
        """
        获取主要指数实时行情

        Args:
            region: 市场区域，cn=A股 us=美股

        Returns:
            List[Dict]: 指数列表，每个元素为字典，包含:
                - code: 指数代码
                - name: 指数名称
                - current: 当前点位
                - change: 涨跌点数
                - change_pct: 涨跌幅(%)
                - volume: 成交量
                - amount: 成交额
        """
        return None

    def get_market_stats(self) -> Optional[Dict[str, Any]]:
        """
        获取市场涨跌统计

        Returns:
            Dict: 包含:
                - up_count: 上涨家数
                - down_count: 下跌家数
                - flat_count: 平盘家数
                - limit_up_count: 涨停家数
                - limit_down_count: 跌停家数
                - total_amount: 两市成交额
        """
        return None

    def get_sector_rankings(self, n: int = 5) -> Optional[Tuple[List[Dict], List[Dict]]]:
        """
        获取板块涨跌榜

        Args:
            n: 返回前n个

        Returns:
            Tuple: (领涨板块列表, 领跌板块列表)
        """
        return None

    def get_daily_data(
        self,
        stock_code: str, 
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 30
    ) -> pd.DataFrame:
        """
        获取日线数据（统一入口）
        
        流程：
        1. 计算日期范围
        2. 调用子类获取原始数据
        3. 标准化列名
        4. 计算技术指标
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期（可选）
            end_date: 结束日期（可选，默认今天）
            days: 获取天数（当 start_date 未指定时使用）
            
        Returns:
            标准化的 DataFrame，包含技术指标
        """
        # 计算日期范围
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        if start_date is None:
            # 默认获取最近 30 个交易日（按日历日估算，多取一些）
            from datetime import timedelta
            start_dt = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=days * 2)
            start_date = start_dt.strftime('%Y-%m-%d')

        request_start = time.time()
        logger.info(f"[{self.name}] 开始获取 {stock_code} 日线数据: 范围={start_date} ~ {end_date}")
        
        try:
            # Step 1: 获取原始数据
            raw_df = self._fetch_raw_data(stock_code, start_date, end_date)
            
            if raw_df is None or raw_df.empty:
                raise DataFetchError(f"[{self.name}] 未获取到 {stock_code} 的数据")
            
            # Step 2: 标准化列名
            df = self._normalize_data(raw_df, stock_code)
            
            # Step 3: 数据清洗
            df = self._clean_data(df)
            
            # Step 4: 计算技术指标
            df = self._calculate_indicators(df)

            elapsed = time.time() - request_start
            logger.info(
                f"[{self.name}] {stock_code} 获取成功: 范围={start_date} ~ {end_date}, "
                f"rows={len(df)}, elapsed={elapsed:.2f}s"
            )
            return df
            
        except Exception as e:
            elapsed = time.time() - request_start
            error_type, error_reason = summarize_exception(e)
            logger.error(
                f"[{self.name}] {stock_code} 获取失败: 范围={start_date} ~ {end_date}, "
                f"error_type={error_type}, elapsed={elapsed:.2f}s, reason={error_reason}"
            )
            raise DataFetchError(f"[{self.name}] {stock_code}: {error_reason}") from e
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        数据清洗
        
        处理：
        1. 确保日期列格式正确
        2. 数值类型转换
        3. 去除空值行
        4. 按日期排序
        """
        df = df.copy()
        
        # 确保日期列为 datetime 类型
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        
        # 数值列类型转换
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 去除关键列为空的行
        df = df.dropna(subset=['close', 'volume'])
        
        # 按日期升序排序
        df = df.sort_values('date', ascending=True).reset_index(drop=True)
        
        return df
    
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算技术指标
        
        计算指标：
        - MA5, MA10, MA20: 移动平均线
        - Volume_Ratio: 量比（今日成交量 / 5日平均成交量）
        """
        df = df.copy()
        
        # 移动平均线
        df['ma5'] = df['close'].rolling(window=5, min_periods=1).mean()
        df['ma10'] = df['close'].rolling(window=10, min_periods=1).mean()
        df['ma20'] = df['close'].rolling(window=20, min_periods=1).mean()
        
        # 量比：当日成交量 / 5日平均成交量
        # 注意：此处的 volume_ratio 是“日线成交量 / 前5日均量(shift 1)”的相对倍数，
        # 与部分交易软件口径的“分时量比（同一时刻对比）”不同，含义更接近“放量倍数”。
        # 该行为目前保留（按需求不改逻辑）。
        avg_volume_5 = df['volume'].rolling(window=5, min_periods=1).mean()
        df['volume_ratio'] = df['volume'] / avg_volume_5.shift(1)
        df['volume_ratio'] = df['volume_ratio'].fillna(1.0)
        
        # 保留2位小数
        for col in ['ma5', 'ma10', 'ma20', 'volume_ratio']:
            if col in df.columns:
                df[col] = df[col].round(2)
        
        return df
    
    @staticmethod
    def random_sleep(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
        """
        智能随机休眠（Jitter）
        
        防封禁策略：模拟人类行为的随机延迟
        在请求之间加入不规则的等待时间
        """
        sleep_time = random.uniform(min_seconds, max_seconds)
        logger.debug(f"随机休眠 {sleep_time:.2f} 秒...")
        time.sleep(sleep_time)


class DataFetcherManager:
    """
    数据源策略管理器
    
    职责：
    1. 管理多个数据源（按优先级排序）
    2. 自动故障切换（Failover）
    3. 提供统一的数据获取接口
    
    切换策略：
    - 优先使用高优先级数据源
    - 失败后自动切换到下一个
    - 所有数据源都失败时抛出异常
    """
    
    def __init__(
        self,
        fetchers: Optional[List[BaseFetcher]] = None,
        ifind_fetcher: Optional[BaseFetcher] = None,
    ):
        """
        初始化管理器
        
        Args:
            fetchers: 数据源列表（可选，默认按优先级自动创建）
        """
        self._fetchers: List[BaseFetcher] = []
        self._ifind_fetcher: Optional[BaseFetcher] = ifind_fetcher
        self._weekly_fetchers: List[BaseFetcher] = []  # 周K线数据源列表
        
        if fetchers:
            # 按优先级排序
            self._fetchers = sorted(fetchers, key=lambda f: f.priority)
        else:
            # 默认数据源将在首次使用时延迟加载
            self._init_default_fetchers()
            # 初始化周K线数据源
            self._init_weekly_fetchers()
    
    def _init_default_fetchers(self) -> None:
        """
        初始化默认数据源列表

        优先级动态调整逻辑：
        - 如果配置了 TUSHARE_TOKEN：Tushare 优先级提升为 0（最高）
        - 否则按默认优先级：
          0. EfinanceFetcher (Priority 0) - 最高优先级
          1. AkshareFetcher (Priority 1)
          2. PytdxFetcher (Priority 2) - 通达信
          2. TushareFetcher (Priority 2)
          3. BaostockFetcher (Priority 3)
          4. YfinanceFetcher (Priority 4)

        说明：
        - HSCloudFetcher / WencaiFetcher 仅用于筹码分布降级链，
          不参与日线/实时行情主路径。
        """
        from .efinance_fetcher import EfinanceFetcher
        from .akshare_fetcher import AkshareFetcher
        from .tushare_fetcher import TushareFetcher
        from .pytdx_fetcher import PytdxFetcher
        from .baostock_fetcher import BaostockFetcher
        from .yfinance_fetcher import YfinanceFetcher
        from .hscloud_fetcher import HSCloudFetcher
        from .wencai_fetcher import WencaiFetcher
        # 创建所有数据源实例（优先级在各 Fetcher 的 __init__ 中确定）
        efinance = EfinanceFetcher()
        akshare = AkshareFetcher()
        tushare = TushareFetcher()  # 会根据 Token 配置自动调整优先级
        pytdx = PytdxFetcher()      # 通达信数据源（可配 PYTDX_HOST/PYTDX_PORT）
        baostock = BaostockFetcher()
        yfinance = YfinanceFetcher()
        hscloud = HSCloudFetcher()
        wencai = WencaiFetcher()

        # 初始化数据源列表
        self._fetchers = [
            efinance,
            akshare,
            tushare,
            pytdx,
            baostock,
            yfinance,
            hscloud,
            wencai,
        ]

        # 按优先级排序（Tushare 如果配置了 Token 且初始化成功，优先级为 0）
        self._fetchers.sort(key=lambda f: f.priority)

        # 构建优先级说明
        priority_info = ", ".join([f"{f.name}(P{f.priority})" for f in self._fetchers])
        logger.info(f"已初始化 {len(self._fetchers)} 个数据源（按优先级）: {priority_info}")
    
    def _init_weekly_fetchers(self) -> None:
        """
        初始化周K线数据源列表（固定顺序，按优先级）
        
        优先级：
        0. EfinanceWeeklyFetcher - 最高优先级
        0. BaostockWeeklyFetcher - 同优先级，免费稳定
        1. AkshareWeeklyFetcher
        2. TushareWeeklyFetcher
        2. PytdxWeeklyFetcher
        4. YfinanceWeeklyFetcher - 兜底数据源
        """
        from .weekly_fetcher import (
            EfinanceWeeklyFetcher,
            AkshareWeeklyFetcher,
            TushareWeeklyFetcher,
            BaostockWeeklyFetcher,
            PytdxWeeklyFetcher,
            YfinanceWeeklyFetcher,
        )
        
        logger.info("=" * 80)
        logger.info("开始初始化周K线数据源...")
        logger.info("=" * 80)
        
        # 创建所有周K线数据源实例
        self._weekly_fetchers = [
            EfinanceWeeklyFetcher(),
            BaostockWeeklyFetcher(),
            AkshareWeeklyFetcher(),
            TushareWeeklyFetcher(),
            PytdxWeeklyFetcher(),
            YfinanceWeeklyFetcher(),
        ]
        
        # 按优先级排序
        self._weekly_fetchers.sort(key=lambda f: f.priority)
        
        # 构建优先级说明
        priority_info = ", ".join([f"{f.name}(P{f.priority})" for f in self._weekly_fetchers])
        logger.info(f"已初始化 {len(self._weekly_fetchers)} 个周K线数据源（按优先级）: {priority_info}")
        logger.info("=" * 80)
    
    def add_fetcher(self, fetcher: BaseFetcher) -> None:
        """添加数据源并重新排序"""
        self._fetchers.append(fetcher)
        self._fetchers.sort(key=lambda f: f.priority)

    @staticmethod
    def _ths_mode_enabled(config: Any) -> bool:
        """Resolve THS professional mode from helper methods or raw flags."""
        helper = getattr(config, 'is_ths_pro_data_enabled', None)
        if callable(helper):
            return bool(helper())
        return bool(getattr(config, 'enable_ths_pro_data', False)) or bool(
            getattr(config, 'enable_ifind', False)
        )

    def _can_use_ifind_daily(self, config: Any) -> bool:
        if not self._ifind_fetcher or not self._ths_mode_enabled(config):
            return False
        supports = getattr(self._ifind_fetcher, 'supports_daily_data', None)
        if callable(supports):
            return bool(supports())
        return True

    def _can_use_ifind_realtime(self, config: Any) -> bool:
        if not self._ifind_fetcher or not self._ths_mode_enabled(config):
            return False
        supports = getattr(self._ifind_fetcher, 'supports_realtime_quote', None)
        if callable(supports):
            return bool(supports())
        return True

    @staticmethod
    def _ifind_market_metrics_backfill_enabled(config: Any) -> bool:
        helper = getattr(config, 'is_ifind_financial_enhancement_enabled', None)
        if callable(helper):
            return bool(helper())
        return DataFetcherManager._ths_mode_enabled(config) and bool(
            getattr(config, 'enable_ifind_analysis_enhancement', False)
        )

    @staticmethod
    def _acceptable_ifind_metric_dates() -> set[str]:
        today_str = date.today().isoformat()
        accepted = {today_str}
        now = datetime.now()
        if (now.hour, now.minute) < (9, 30):
            previous_business_day = (pd.Timestamp(today_str) - pd.offsets.BDay(1)).date().isoformat()
            accepted.add(previous_business_day)
        return accepted
    
    def get_daily_data(
        self, 
        stock_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 30
    ) -> Tuple[pd.DataFrame, str]:
        """
        获取日线数据（自动切换数据源）
        
        故障切换策略：
        1. 美股指数/美股股票直接路由到 YfinanceFetcher
        2. 其他代码从最高优先级数据源开始尝试
        3. 捕获异常后自动切换到下一个
        4. 记录每个数据源的失败原因
        5. 所有数据源失败后抛出详细异常
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            days: 获取天数
            
        Returns:
            Tuple[DataFrame, str]: (数据, 成功的数据源名称)
            
        Raises:
            DataFetchError: 所有数据源都失败时抛出
        """
        from .us_index_mapping import is_us_index_code, is_us_stock_code
        from src.config import get_config

        # Normalize code (strip SH/SZ prefix etc.)
        stock_code = normalize_stock_code(stock_code)

        config = get_config()
        errors = []
        total_fetchers = len(self._fetchers)
        request_start = time.time()

        # 快速路径：美股指数与美股股票直接路由到 YfinanceFetcher
        if is_us_index_code(stock_code) or is_us_stock_code(stock_code):
            for attempt, fetcher in enumerate(self._fetchers, start=1):
                if fetcher.name == "YfinanceFetcher":
                    try:
                        logger.info(
                            f"[数据源尝试 {attempt}/{total_fetchers}] [{fetcher.name}] "
                            f"美股/美股指数 {stock_code} 直接路由..."
                        )
                        df = fetcher.get_daily_data(
                            stock_code=stock_code,
                            start_date=start_date,
                            end_date=end_date,
                            days=days,
                        )
                        if df is not None and not df.empty:
                            elapsed = time.time() - request_start
                            logger.info(
                                f"[数据源完成] {stock_code} 使用 [{fetcher.name}] 获取成功: "
                                f"rows={len(df)}, elapsed={elapsed:.2f}s"
                            )
                            return df, fetcher.name
                    except Exception as e:
                        error_type, error_reason = summarize_exception(e)
                        error_msg = f"[{fetcher.name}] ({error_type}) {error_reason}"
                        logger.warning(
                            f"[数据源失败 {attempt}/{total_fetchers}] [{fetcher.name}] {stock_code}: "
                            f"error_type={error_type}, reason={error_reason}"
                        )
                        errors.append(error_msg)
                    break
            # YfinanceFetcher failed or not found
            error_summary = f"美股/美股指数 {stock_code} 获取失败:\n" + "\n".join(errors)
            elapsed = time.time() - request_start
            logger.error(f"[数据源终止] {stock_code} 获取失败: elapsed={elapsed:.2f}s\n{error_summary}")
            raise DataFetchError(error_summary)

        if self._can_use_ifind_daily(config):
            try:
                logger.info("[数据源尝试 THS] [IFindFetcher] 获取 %s...", stock_code)
                df = self._ifind_fetcher.get_daily_data(
                    stock_code=stock_code,
                    start_date=start_date,
                    end_date=end_date,
                    days=days,
                )
                if df is not None and not df.empty:
                    elapsed = time.time() - request_start
                    logger.info(
                        f"[数据源完成] {stock_code} 使用 [IFindFetcher] 获取成功: "
                        f"rows={len(df)}, elapsed={elapsed:.2f}s"
                    )
                    return df, self._ifind_fetcher.name
            except Exception as e:
                error_type, error_reason = summarize_exception(e)
                error_msg = f"[IFindFetcher] ({error_type}) {error_reason}"
                logger.warning(
                    f"[数据源失败 THS] [IFindFetcher] {stock_code}: "
                    f"error_type={error_type}, reason={error_reason}"
                )
                errors.append(error_msg)

        for attempt, fetcher in enumerate(self._fetchers, start=1):
            try:
                logger.info(f"[数据源尝试 {attempt}/{total_fetchers}] [{fetcher.name}] 获取 {stock_code}...")
                df = fetcher.get_daily_data(
                    stock_code=stock_code,
                    start_date=start_date,
                    end_date=end_date,
                    days=days
                )
                
                if df is not None and not df.empty:
                    elapsed = time.time() - request_start
                    logger.info(
                        f"[数据源完成] {stock_code} 使用 [{fetcher.name}] 获取成功: "
                        f"rows={len(df)}, elapsed={elapsed:.2f}s"
                    )
                    return df, fetcher.name
                    
            except Exception as e:
                error_type, error_reason = summarize_exception(e)
                error_msg = f"[{fetcher.name}] ({error_type}) {error_reason}"
                logger.warning(
                    f"[数据源失败 {attempt}/{total_fetchers}] [{fetcher.name}] {stock_code}: "
                    f"error_type={error_type}, reason={error_reason}"
                )
                errors.append(error_msg)
                if attempt < total_fetchers:
                    next_fetcher = self._fetchers[attempt]
                    logger.info(f"[数据源切换] {stock_code}: [{fetcher.name}] -> [{next_fetcher.name}]")
                # 继续尝试下一个数据源
                continue
        
        # 所有数据源都失败
        error_summary = f"所有数据源获取 {stock_code} 失败:\n" + "\n".join(errors)
        elapsed = time.time() - request_start
        logger.error(f"[数据源终止] {stock_code} 获取失败: elapsed={elapsed:.2f}s\n{error_summary}")
        raise DataFetchError(error_summary)
    
    @property
    def available_fetchers(self) -> List[str]:
        """返回可用数据源名称列表"""
        names = [f.name for f in self._fetchers]
        if self._ifind_fetcher:
            names.insert(0, self._ifind_fetcher.name)
        return names
    
    def prefetch_realtime_quotes(self, stock_codes: List[str]) -> int:
        """
        批量预取实时行情数据（在分析开始前调用）
        
        策略：
        1. 检查优先级中是否包含全量拉取数据源（efinance/akshare_em）
        2. 如果不包含，跳过预取（新浪/腾讯是单股票查询，无需预取）
        3. 如果自选股数量 >= 5 且使用全量数据源，则预取填充缓存
        
        这样做的好处：
        - 使用新浪/腾讯时：每只股票独立查询，无全量拉取问题
        - 使用 efinance/东财时：预取一次，后续缓存命中
        
        Args:
            stock_codes: 待分析的股票代码列表
            
        Returns:
            预取的股票数量（0 表示跳过预取）
        """
        # Normalize all codes
        stock_codes = [normalize_stock_code(c) for c in stock_codes]

        from src.config import get_config

        config = get_config()

        # Issue #455: PREFETCH_REALTIME_QUOTES=false 可禁用预取，避免全市场拉取
        if not getattr(config, "prefetch_realtime_quotes", True):
            logger.debug("[预取] PREFETCH_REALTIME_QUOTES=false，跳过批量预取")
            return 0

        # 如果实时行情被禁用，跳过预取
        if not config.enable_realtime_quote:
            logger.debug("[预取] 实时行情功能已禁用，跳过预取")
            return 0
        
        # 检查优先级中是否包含全量拉取数据源
        # 注意：新增全量接口（如 tushare_realtime）时需同步更新此列表
        # 全量接口特征：一次 API 调用拉取全市场 5000+ 股票数据
        priority = config.realtime_source_priority.lower()
        bulk_sources = ['efinance', 'akshare_em', 'tushare']  # 全量接口列表
        
        # 如果优先级中前两个都不是全量数据源，跳过预取
        # 因为新浪/腾讯是单股票查询，不需要预取
        priority_list = [s.strip() for s in priority.split(',')]
        first_bulk_source_index = None
        for i, source in enumerate(priority_list):
            if source in bulk_sources:
                first_bulk_source_index = i
                break
        
        # 如果没有全量数据源，或者全量数据源排在第 3 位之后，跳过预取
        if first_bulk_source_index is None or first_bulk_source_index >= 2:
            logger.info(f"[预取] 当前优先级使用轻量级数据源(sina/tencent)，无需预取")
            return 0
        
        # 如果股票数量少于 5 个，不进行批量预取（逐个查询更高效）
        if len(stock_codes) < 5:
            logger.info(f"[预取] 股票数量 {len(stock_codes)} < 5，跳过批量预取")
            return 0
        
        logger.info(f"[预取] 开始批量预取实时行情，共 {len(stock_codes)} 只股票...")
        
        # 尝试通过 efinance 或 akshare 预取
        # 只需要调用一次 get_realtime_quote，缓存机制会自动拉取全市场数据
        try:
            # 用第一只股票触发全量拉取
            first_code = stock_codes[0]
            quote = self.get_realtime_quote(first_code)
            
            if quote:
                logger.info(f"[预取] 批量预取完成，缓存已填充")
                return len(stock_codes)
            else:
                logger.warning(f"[预取] 批量预取失败，将使用逐个查询模式")
                return 0
                
        except Exception as e:
            logger.error(f"[预取] 批量预取异常: {e}")
            return 0
    
    def get_realtime_quote(self, stock_code: str):
        """
        获取实时行情数据（自动故障切换）
        
        故障切换策略（按配置的优先级）：
        1. 美股：使用 YfinanceFetcher.get_realtime_quote()
        2. EfinanceFetcher.get_realtime_quote()
        3. AkshareFetcher.get_realtime_quote(source="em")  - 东财
        4. AkshareFetcher.get_realtime_quote(source="sina") - 新浪
        5. AkshareFetcher.get_realtime_quote(source="tencent") - 腾讯
        6. 返回 None（降级兜底）
        
        Args:
            stock_code: 股票代码
            
        Returns:
            UnifiedRealtimeQuote 对象，所有数据源都失败则返回 None
        """
        # Normalize code (strip SH/SZ prefix etc.)
        stock_code = normalize_stock_code(stock_code)

        from .realtime_types import get_realtime_circuit_breaker
        from .akshare_fetcher import _is_us_code
        from .us_index_mapping import is_us_index_code
        from src.config import get_config

        config = get_config()

        # 如果实时行情功能被禁用，直接返回 None
        if not config.enable_realtime_quote:
            logger.debug(f"[实时行情] 功能已禁用，跳过 {stock_code}")
            return None

        # 美股指数由 YfinanceFetcher 处理（在美股股票检查之前）
        if is_us_index_code(stock_code):
            for fetcher in self._fetchers:
                if fetcher.name == "YfinanceFetcher":
                    if hasattr(fetcher, 'get_realtime_quote'):
                        try:
                            quote = fetcher.get_realtime_quote(stock_code)
                            if quote is not None:
                                logger.info(f"[实时行情] 美股指数 {stock_code} 成功获取 (来源: yfinance)")
                                return quote
                        except Exception as e:
                            logger.warning(f"[实时行情] 美股指数 {stock_code} 获取失败: {e}")
                    break
            logger.warning(f"[实时行情] 美股指数 {stock_code} 无可用数据源")
            return None

        # 美股单独处理，使用 YfinanceFetcher
        if _is_us_code(stock_code):
            for fetcher in self._fetchers:
                if fetcher.name == "YfinanceFetcher":
                    if hasattr(fetcher, 'get_realtime_quote'):
                        try:
                            quote = fetcher.get_realtime_quote(stock_code)
                            if quote is not None:
                                logger.info(f"[实时行情] 美股 {stock_code} 成功获取 (来源: yfinance)")
                                return quote
                        except Exception as e:
                            logger.warning(f"[实时行情] 美股 {stock_code} 获取失败: {e}")
                    break
            logger.warning(f"[实时行情] 美股 {stock_code} 无可用数据源")
            return None
        
        # 获取配置的数据源优先级
        source_priority = config.realtime_source_priority.split(',')
        
        errors = []
        # primary_quote holds the first successful result; we may supplement
        # missing fields (volume_ratio, turnover_rate, etc.) from later sources.
        primary_quote = None
        supplement_attempts = 0

        if self._can_use_ifind_realtime(config):
            try:
                quote = self._ifind_fetcher.get_realtime_quote(stock_code)
                if quote is not None and quote.has_basic_data():
                    primary_quote = quote
                    logger.info(f"[实时行情] {stock_code} 成功获取 (来源: ifind)")
                    filled = self._backfill_ifind_market_metrics(primary_quote, stock_code, config)
                    if filled:
                        logger.info(f"[实时行情] {stock_code} 从 ifind_market_metrics 补充了缺失字段: {filled}")
                    if not self._quote_needs_supplement(primary_quote):
                        return primary_quote
                    logger.debug(f"[实时行情] {stock_code} iFinD 部分字段缺失，尝试从后续数据源补充")
            except Exception as e:
                error_msg = f"[ifind] 失败: {str(e)}"
                logger.warning(error_msg)
                errors.append(error_msg)
        
        for source in source_priority:
            source = source.strip().lower()
            
            try:
                quote = None
                
                if source == "efinance":
                    # 尝试 EfinanceFetcher
                    for fetcher in self._fetchers:
                        if fetcher.name == "EfinanceFetcher":
                            if hasattr(fetcher, 'get_realtime_quote'):
                                quote = fetcher.get_realtime_quote(stock_code)
                            break
                
                elif source == "akshare_em":
                    # 尝试 AkshareFetcher 东财数据源
                    for fetcher in self._fetchers:
                        if fetcher.name == "AkshareFetcher":
                            if hasattr(fetcher, 'get_realtime_quote'):
                                quote = fetcher.get_realtime_quote(stock_code, source="em")
                            break
                
                elif source == "akshare_sina":
                    # 尝试 AkshareFetcher 新浪数据源
                    for fetcher in self._fetchers:
                        if fetcher.name == "AkshareFetcher":
                            if hasattr(fetcher, 'get_realtime_quote'):
                                quote = fetcher.get_realtime_quote(stock_code, source="sina")
                            break
                
                elif source in ("tencent", "akshare_qq"):
                    # 尝试 AkshareFetcher 腾讯数据源
                    for fetcher in self._fetchers:
                        if fetcher.name == "AkshareFetcher":
                            if hasattr(fetcher, 'get_realtime_quote'):
                                quote = fetcher.get_realtime_quote(stock_code, source="tencent")
                            break
                
                elif source == "tushare":
                    # 尝试 TushareFetcher（需要 Tushare Pro 积分）
                    for fetcher in self._fetchers:
                        if fetcher.name == "TushareFetcher":
                            if hasattr(fetcher, 'get_realtime_quote'):
                                quote = fetcher.get_realtime_quote(stock_code)
                            break
                
                if quote is not None and quote.has_basic_data():
                    if primary_quote is None:
                        # First successful source becomes primary
                        primary_quote = quote
                        logger.info(f"[实时行情] {stock_code} 成功获取 (来源: {source})")
                        # If all key supplementary fields are present, return early
                        if not self._quote_needs_supplement(primary_quote):
                            return primary_quote
                        # Otherwise, continue to try later sources for missing fields
                        logger.debug(f"[实时行情] {stock_code} 部分字段缺失，尝试从后续数据源补充")
                        supplement_attempts = 0
                    else:
                        # Supplement missing fields from this source (limit attempts)
                        supplement_attempts += 1
                        if supplement_attempts > 1:
                            logger.debug(f"[实时行情] {stock_code} 补充尝试已达上限，停止继续")
                            break
                        merged = self._merge_quote_fields(primary_quote, quote)
                        if merged:
                            logger.info(f"[实时行情] {stock_code} 从 {source} 补充了缺失字段: {merged}")
                        # Stop supplementing once all key fields are filled
                        if not self._quote_needs_supplement(primary_quote):
                            break
                    
            except Exception as e:
                error_msg = f"[{source}] 失败: {str(e)}"
                logger.warning(error_msg)
                errors.append(error_msg)
                continue
        
        # Return primary even if some fields are still missing
        if primary_quote is not None:
            return primary_quote

        # 所有数据源都失败，返回 None（降级兜底）
        if errors:
            logger.warning(f"[实时行情] {stock_code} 所有数据源均失败，降级处理: {'; '.join(errors)}")
        else:
            logger.warning(f"[实时行情] {stock_code} 无可用数据源")
        
        return None

    # Fields worth supplementing from secondary sources when the primary
    # source returns None for them. Ordered by importance.
    _SUPPLEMENT_FIELDS = [
        'volume_ratio', 'turnover_rate',
        'pe_ratio', 'pb_ratio', 'total_mv', 'circ_mv',
        'amplitude',
    ]

    @classmethod
    def _quote_needs_supplement(cls, quote) -> bool:
        """Check if any key supplementary field is still None."""
        for f in cls._SUPPLEMENT_FIELDS:
            if getattr(quote, f, None) is None:
                return True
        return False

    @classmethod
    def _merge_quote_fields(cls, primary, secondary) -> list:
        """
        Copy non-None fields from *secondary* into *primary* where
        *primary* has None. Returns list of field names that were filled.
        """
        filled = []
        for f in cls._SUPPLEMENT_FIELDS:
            if getattr(primary, f, None) is None:
                val = getattr(secondary, f, None)
                if val is not None:
                    setattr(primary, f, val)
                    filled.append(f)
        return filled

    def _backfill_ifind_market_metrics(self, quote, stock_code: str, config: Any) -> list[str]:
        """Use same-day iFinD market metrics to reduce external supplements."""
        if not self._ifind_fetcher or not self._ifind_market_metrics_backfill_enabled(config):
            return []

        service = getattr(self._ifind_fetcher, 'service', None)
        get_pack = getattr(service, 'get_financial_pack', None)
        if not callable(get_pack):
            return []

        pack = get_pack(stock_code)
        valuation = getattr(pack, 'valuation', None)
        if valuation is None or getattr(valuation, 'as_of_date', None) not in self._acceptable_ifind_metric_dates():
            return []

        metric_values = {
            'volume_ratio': getattr(valuation, 'volume_ratio', None),
            'turnover_rate': getattr(valuation, 'turnover_rate', None),
            'pe_ratio': getattr(valuation, 'pe_ttm', None),
            'pb_ratio': getattr(valuation, 'pb', None),
            'total_mv': getattr(valuation, 'total_market_value', None),
            'circ_mv': getattr(valuation, 'circulating_market_value', None),
        }

        filled: list[str] = []
        for field in self._SUPPLEMENT_FIELDS:
            if getattr(quote, field, None) is None and metric_values.get(field) is not None:
                setattr(quote, field, metric_values[field])
                filled.append(field)
        return filled

    def get_chip_distribution(self, stock_code: str):
        """
        获取筹码分布数据（带熔断和多数据源降级）

        策略：
        1. 检查配置开关
        2. 检查熔断器状态
        3. 依次尝试多个数据源：HSCloudFetcher -> WencaiFetcher -> AkshareFetcher -> TushareFetcher -> EfinanceFetcher
        4. 所有数据源失败则返回 None（降级兜底）

        Args:
            stock_code: 股票代码

        Returns:
            ChipDistribution 对象，失败则返回 None
        """
        # Normalize code (strip SH/SZ prefix etc.)
        stock_code = normalize_stock_code(stock_code)

        from .realtime_types import get_chip_circuit_breaker
        from src.config import get_config

        config = get_config()

        # 如果筹码分布功能被禁用，直接返回 None
        if not config.enable_chip_distribution:
            logger.debug(f"[筹码分布] 功能已禁用，跳过 {stock_code}")
            return None

        circuit_breaker = get_chip_circuit_breaker()

        # 定义筹码数据源优先级列表
        chip_sources = [
            ("HSCloudFetcher", "hscloud_chip"),
            ("WencaiFetcher", "wencai_chip"),
            ("AkshareFetcher", "akshare_chip"),
            ("TushareFetcher", "tushare_chip"),
            ("EfinanceFetcher", "efinance_chip"),
        ]

        for fetcher_name, source_key in chip_sources:
            # 检查熔断器状态
            if not circuit_breaker.is_available(source_key):
                logger.debug(f"[熔断] {fetcher_name} 筹码接口处于熔断状态，尝试下一个")
                continue

            try:
                for fetcher in self._fetchers:
                    if fetcher.name == fetcher_name:
                        if hasattr(fetcher, 'get_chip_distribution'):
                            chip = fetcher.get_chip_distribution(stock_code)
                            if chip is not None:
                                circuit_breaker.record_success(source_key)
                                logger.info(f"[筹码分布] {stock_code} 成功获取 (来源: {fetcher_name})")
                                return chip
                        break
            except Exception as e:
                logger.warning(f"[筹码分布] {fetcher_name} 获取 {stock_code} 失败: {e}")
                circuit_breaker.record_failure(source_key, str(e))
                continue

        logger.warning(f"[筹码分布] {stock_code} 所有数据源均失败")
        return None

    def get_stock_name(self, stock_code: str, allow_realtime: bool = True) -> Optional[str]:
        """
        获取股票中文名称（自动切换数据源）
        
        尝试从多个数据源获取股票名称：
        1. 先从实时行情缓存中获取（如果有）
        2. 依次尝试各个数据源的 get_stock_name 方法
        3. 最后尝试让大模型通过搜索获取（需要外部调用）
        
        Args:
            stock_code: 股票代码
            allow_realtime: Whether to query realtime quote first. Set False when
                caller only wants lightweight prefetch without triggering heavy
                realtime source calls.
            
        Returns:
            股票中文名称，所有数据源都失败则返回 None
        """
        # Normalize code (strip SH/SZ prefix etc.)
        stock_code = normalize_stock_code(stock_code)
        static_name = STOCK_NAME_MAP.get(stock_code)

        from src.config import get_config

        # 1. 先检查缓存
        if hasattr(self, '_stock_name_cache') and stock_code in self._stock_name_cache:
            return self._stock_name_cache[stock_code]
        
        # 初始化缓存
        if not hasattr(self, '_stock_name_cache'):
            self._stock_name_cache = {}
        
        # 2. 尝试从实时行情中获取（最快，可按需禁用）
        if allow_realtime:
            quote = self.get_realtime_quote(stock_code)
            if quote and hasattr(quote, 'name') and is_meaningful_stock_name(getattr(quote, 'name', ''), stock_code):
                name = quote.name
                self._stock_name_cache[stock_code] = name
                logger.info(f"[股票名称] 从实时行情获取: {stock_code} -> {name}")
                return name

        config = get_config()
        if (
            self._ths_mode_enabled(config)
            and self._ifind_fetcher
            and hasattr(self._ifind_fetcher, 'get_stock_name')
            and (allow_realtime or not is_meaningful_stock_name(static_name, stock_code))
        ):
            try:
                name = self._ifind_fetcher.get_stock_name(stock_code)
                if is_meaningful_stock_name(name, stock_code):
                    self._stock_name_cache[stock_code] = name
                    logger.info(f"[股票名称] 从 IFindFetcher 获取: {stock_code} -> {name}")
                    return name
            except Exception as e:
                logger.debug(f"[股票名称] IFindFetcher 获取失败: {e}")

        if is_meaningful_stock_name(static_name, stock_code):
            self._stock_name_cache[stock_code] = static_name
            return static_name

        # 3. 依次尝试各个数据源
        for fetcher in self._fetchers:
            if hasattr(fetcher, 'get_stock_name'):
                try:
                    name = fetcher.get_stock_name(stock_code)
                    if is_meaningful_stock_name(name, stock_code):
                        self._stock_name_cache[stock_code] = name
                        logger.info(f"[股票名称] 从 {fetcher.name} 获取: {stock_code} -> {name}")
                        return name
                except Exception as e:
                    logger.debug(f"[股票名称] {fetcher.name} 获取失败: {e}")
                    continue

        # 4. 所有数据源都失败
        logger.warning(f"[股票名称] 所有数据源都无法获取 {stock_code} 的名称")
        return ""

    def prefetch_stock_names(self, stock_codes: List[str], use_bulk: bool = False) -> None:
        """
        Pre-fetch stock names into cache before parallel analysis (Issue #455).

        When use_bulk=False, only calls get_stock_name per code (no get_stock_list),
        avoiding full-market fetch. Sequential execution to avoid rate limits.

        Args:
            stock_codes: Stock codes to prefetch.
            use_bulk: If True, may use get_stock_list (full fetch). Default False.
        """
        if not stock_codes:
            return
        stock_codes = [normalize_stock_code(c) for c in stock_codes]
        if use_bulk:
            self.batch_get_stock_names(stock_codes)
            return
        for code in stock_codes:
            # Skip realtime lookup to avoid triggering expensive full-market quote
            # requests during the prefetch phase.
            self.get_stock_name(code, allow_realtime=False)

    def batch_get_stock_names(self, stock_codes: List[str]) -> Dict[str, str]:
        """
        批量获取股票中文名称
        
        先尝试从支持批量查询的数据源获取股票列表，
        然后再逐个查询缺失的股票名称。
        
        Args:
            stock_codes: 股票代码列表
            
        Returns:
            {股票代码: 股票名称} 字典
        """
        result = {}
        missing_codes = set(stock_codes)
        
        # 1. 先检查缓存
        if not hasattr(self, '_stock_name_cache'):
            self._stock_name_cache = {}
        
        for code in stock_codes:
            if code in self._stock_name_cache:
                result[code] = self._stock_name_cache[code]
                missing_codes.discard(code)
        
        if not missing_codes:
            return result
        
        # 2. 尝试批量获取股票列表
        for fetcher in self._fetchers:
            if hasattr(fetcher, 'get_stock_list') and missing_codes:
                try:
                    stock_list = fetcher.get_stock_list()
                    if stock_list is not None and not stock_list.empty:
                        for _, row in stock_list.iterrows():
                            code = row.get('code')
                            name = row.get('name')
                            if code and name:
                                self._stock_name_cache[code] = name
                                if code in missing_codes:
                                    result[code] = name
                                    missing_codes.discard(code)
                        
                        if not missing_codes:
                            break
                        
                        logger.info(f"[股票名称] 从 {fetcher.name} 批量获取完成，剩余 {len(missing_codes)} 个待查")
                except Exception as e:
                    logger.debug(f"[股票名称] {fetcher.name} 批量获取失败: {e}")
                    continue
        
        # 3. 逐个获取剩余的
        for code in list(missing_codes):
            name = self.get_stock_name(code)
            if name:
                result[code] = name
                missing_codes.discard(code)
        
        logger.info(f"[股票名称] 批量获取完成，成功 {len(result)}/{len(stock_codes)}")
        return result

    def get_main_indices(self, region: str = "cn") -> List[Dict[str, Any]]:
        """获取主要指数实时行情（自动切换数据源）"""
        for fetcher in self._fetchers:
            try:
                data = fetcher.get_main_indices(region=region)
                if data:
                    logger.info(f"[{fetcher.name}] 获取指数行情成功")
                    return data
            except Exception as e:
                logger.warning(f"[{fetcher.name}] 获取指数行情失败: {e}")
                continue
        return []

    def get_market_stats(self) -> Dict[str, Any]:
        """获取市场涨跌统计（自动切换数据源）"""
        for fetcher in self._fetchers:
            try:
                data = fetcher.get_market_stats()
                if data:
                    logger.info(f"[{fetcher.name}] 获取市场统计成功")
                    return data
            except Exception as e:
                logger.warning(f"[{fetcher.name}] 获取市场统计失败: {e}")
                continue
        return {}

    def get_sector_rankings(self, n: int = 5) -> Tuple[List[Dict], List[Dict]]:
        """获取板块涨跌榜（自动切换数据源）"""
        for fetcher in self._fetchers:
            try:
                data = fetcher.get_sector_rankings(n)
                if data:
                    logger.info(f"[{fetcher.name}] 获取板块排行成功")
                    return data
            except Exception as e:
                logger.warning(f"[{fetcher.name}] 获取板块排行失败: {e}")
                continue
        return [], []
    
    def get_all_stock_list_with_failover(self) -> Tuple[List[Dict[str, Any]], str]:
        """
        步骤1: 获取全市场股票列表（包含上市时间）- 自动切换数据源
        
        故障切换策略：
        1. 从最高优先级数据源开始尝试
        2. 一旦成功获取到股票列表，立即返回，不再尝试后续数据源
        3. 记录每个数据源的失败原因
        4. 所有数据源失败后抛出异常
        
        Returns:
            Tuple[List[Dict], str]: (股票列表, 成功的数据源名称)
            每个股票包含: {'code': 股票代码, 'name': 股票名称, 'list_date': 上市日期}
            
        Raises:
            DataFetchError: 所有数据源都失败时抛出
        """
        errors = []
        total_fetchers = len(self._weekly_fetchers)
        request_start = time.time()
        
        for attempt, fetcher in enumerate(self._weekly_fetchers, start=1):
            try:
                logger.info(f"[步骤1-数据源尝试 {attempt}/{total_fetchers}] [{fetcher.name}] 获取全市场股票列表...")
                
                if not fetcher._check_available():
                    logger.debug(f"[{fetcher.name}] 数据源不可用，跳过")
                    continue
                
                stock_list = fetcher.get_all_stock_list()
                
                if stock_list:
                    elapsed = time.time() - request_start
                    logger.info(
                        f"[步骤1-数据源完成] 全市场股票列表使用 [{fetcher.name}] 获取成功: "
                        f"count={len(stock_list)}, elapsed={elapsed:.2f}s"
                    )
                    return stock_list, fetcher.name
                else:
                    logger.warning(f"[{fetcher.name}] 获取到空列表")
                    
            except Exception as e:
                error_type, error_reason = summarize_exception(e)
                error_msg = f"[{fetcher.name}] ({error_type}) {error_reason}"
                logger.warning(
                    f"[步骤1-数据源失败 {attempt}/{total_fetchers}] [{fetcher.name}] 获取股票列表: "
                    f"error_type={error_type}, reason={error_reason}"
                )
                errors.append(error_msg)
                continue
        
        error_summary = "所有数据源获取全市场股票列表失败:\n" + "\n".join(errors)
        elapsed = time.time() - request_start
        logger.error(f"[步骤1-数据源终止] 获取股票列表失败: elapsed={elapsed:.2f}s\n{error_summary}")
        raise DataFetchError(error_summary)
    
    def filter_main_board_stocks(
        self,
        all_stocks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        步骤2: 筛选沪深主板、非ST、上市2年以上的股票
        
        筛选条件：
        1. 沪市主板：600xxx, 601xxx, 603xxx
        2. 深市主板：000xxx, 001xxx, 002xxx
        3. 排除：ST/*ST 股票
        4. 排除：上市不足2年的股票
        
        Args:
            all_stocks: 全市场股票列表，每个元素包含 'code', 'name', 'list_date'
            
        Returns:
            List[Dict]: 筛选后的股票列表
        """
        from .weekly_fetcher import is_main_board_stock, is_listed_over_2_years
        
        logger.info(f"开始筛选股票，原始数量: {len(all_stocks)}")
        
        filtered_stocks = []
        
        for stock in all_stocks:
            code = stock.get('code', '')
            name = stock.get('name', '')
            list_date = stock.get('list_date')
            
            if is_main_board_stock(code, name) and is_listed_over_2_years(list_date):
                filtered_stocks.append(stock)
        
        logger.info(
            f"筛选完成: 原始={len(all_stocks)}, "
            f"筛选后={len(filtered_stocks)}, "
            f"过滤={len(all_stocks) - len(filtered_stocks)}"
        )
        
        return filtered_stocks
    
    def get_weekly_data_batch_with_failover(
        self,
        stock_codes: List[str],
        end_date: Optional[str] = None,
        weeks: int = 104,
        max_workers: int = 1
    ) -> Tuple[Dict[str, pd.DataFrame], str]:
        """
        步骤3: 多线程并发获取周K线数据（前复权）- 自动切换数据源
        
        故障切换策略：
        1. 对每只股票尝试所有数据源
        2. 失败一次就换数据源，轮着尝试
        3. 所有数据源都失败后放弃该股票，继续处理下一只
        
        Args:
            stock_codes: 股票代码列表
            end_date: 结束日期，默认今天
            weeks: 获取周数，默认104周（2年）
            max_workers: 最大线程数，默认1
            
        Returns:
            Tuple[Dict[str, DataFrame], str]: (股票代码->周K线数据的字典, 主要使用的数据源名称)
        """
        if not stock_codes:
            logger.warning("股票代码列表为空")
            return {}, ""
        
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        results = {}
        total_stocks = len(stock_codes)
        success_count = 0
        main_data_source = ""
        
        logger.info("=" * 80)
        logger.info(f"[步骤3] 开始获取周K线数据: 股票数={total_stocks}, 结束日期={end_date}, 周数={weeks}")
        
        # 按优先级排序的数据源列表
        fetchers = self._get_sorted_weekly_fetchers()
        logger.info(f"数据源顺序: {[f.name for f in fetchers]}")
        
        for i, stock_code in enumerate(stock_codes, 1):
            logger.info(f"[处理股票 {i}/{total_stocks}] 尝试获取 {stock_code} 的周K线数据")
            
            stock_success = False
            
            for fetcher_idx, fetcher in enumerate(fetchers, 1):
                try:
                    logger.info(f"  [尝试数据源 {fetcher_idx}/{len(fetchers)}] [{fetcher.name}]")
                    
                    if not fetcher._check_available():
                        logger.warning(f"    [{fetcher.name}] 数据源不可用，切换到下一个")
                        continue
                    
                    # 尝试获取单只股票的数据
                    stock_result = fetcher.fetch_weekly_data_for_stocks(
                        stock_codes=[stock_code],
                        end_date=end_date,
                        weeks=weeks,
                        max_workers=max_workers
                    )
                    
                    if stock_result and stock_code in stock_result:
                        results[stock_code] = stock_result[stock_code]
                        success_count += 1
                        stock_success = True
                        
                        # 记录主要使用的数据源
                        if not main_data_source:
                            main_data_source = fetcher.name
                        
                        logger.info(f"    ✅ [{fetcher.name}] 获取 {stock_code} 成功")
                        break  # 成功获取，停止尝试其他数据源
                    else:
                        logger.warning(f"    ❌ [{fetcher.name}] 获取 {stock_code} 失败，切换到下一个数据源")
                        continue
                        
                except Exception as e:
                    error_type, error_reason = summarize_exception(e)
                    logger.warning(f"    ❌ [{fetcher.name}] 获取 {stock_code} 异常: {error_type} - {error_reason}")
                    continue
            
            if not stock_success:
                logger.warning(f"    ⚠️  所有数据源都无法获取 {stock_code}，放弃该股票")
        
        # 计算成功率
        if total_stocks > 0:
            success_rate = success_count / total_stocks
            logger.info(f"[步骤3-完成] 周K线数据获取完成: 成功={success_count}/{total_stocks} ({success_rate:.2f})")
        else:
            logger.info("[步骤3-完成] 周K线数据获取完成: 无股票需要处理")
        
        return results, main_data_source
    
    def get_main_board_stock_list(self) -> Tuple[List[Dict[str, str]], str]:
        """
        获取沪深主板股票列表（自动切换数据源）
        
        已废弃，请使用 get_all_stock_list_with_failover() 和 filter_main_board_stocks()
        
        Returns:
            Tuple[List[Dict], str]: (股票列表, 成功的数据源名称)
            
        Raises:
            DataFetchError: 所有数据源都失败时抛出
        """
        all_stocks, source = self.get_all_stock_list_with_failover()
        filtered_stocks = self.filter_main_board_stocks(all_stocks)
        
        return filtered_stocks, source
    
    def get_weekly_data_batch(
        self,
        end_date: Optional[str] = None,
        weeks: int = 104
    ) -> Tuple[Dict[str, pd.DataFrame], str]:
        """
        批量获取沪深主板股票的周K线数据（自动切换数据源）
        
        已废弃，请使用以下三个步骤：
        1. get_all_stock_list_with_failover()
        2. filter_main_board_stocks()
        3. get_weekly_data_batch_with_failover()
        
        Args:
            end_date: 结束日期，默认今天
            weeks: 获取周数，默认104周（2年）
            
        Returns:
            Tuple[Dict[str, DataFrame], str]: (股票代码->周K线数据的字典, 成功的数据源名称)
            
        Raises:
            DataFetchError: 所有数据源都失败时抛出
        """
        all_stocks, _ = self.get_all_stock_list_with_failover()
        filtered_stocks = self.filter_main_board_stocks(all_stocks)
        stock_codes = [stock['code'] for stock in filtered_stocks]
        
        return self.get_weekly_data_batch_with_failover(
            stock_codes=stock_codes,
            end_date=end_date,
            weeks=weeks,
            max_workers=3
        )
    
    def filter_stocks_above_ma(
        self,
        weekly_data: Dict[str, pd.DataFrame],
        ma_period: int = 25,
        min_data_points: int = 30
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        步骤4: 筛选站上均线的股票
        
        筛选条件：
        1. 有足够的数据点计算均线（至少 min_data_points 周）
        2. 最新收盘价在均线上方
        
        Args:
            weekly_data: 股票代码->周K线数据的字典
            ma_period: 均线周期，默认25周
            min_data_points: 最小数据点数，默认30周
            
        Returns:
            Tuple[List[Dict], Dict]: 
                - 符合条件的股票列表，每个元素包含 {'code': 代码, 'close': 最新价, 'ma': 均线值, 'pct_above': 高出百分比}
                - 统计信息 {'total': 总数, 'passed': 通过数, 'failed': 失败数, 'reasons': 失败原因统计}
        """
        passed_stocks = []
        failed_reasons = {
            'insufficient_data': 0,  # 数据不足
            'below_ma': 0,  # 股价在均线下方
        }
        
        logger.info(f"开始筛选站上{ma_period}周均线的股票，总数: {len(weekly_data)}")
        
        for code, df in weekly_data.items():
            try:
                # 检查数据是否足够
                if df is None or len(df) < min_data_points:
                    failed_reasons['insufficient_data'] += 1
                    continue
                
                # 确保有收盘价列
                if 'close' not in df.columns:
                    logger.warning(f"[{code}] 缺少 'close' 列")
                    failed_reasons['insufficient_data'] += 1
                    continue
                
                # 计算均线
                df_sorted = df.sort_values('date')  # 按日期排序
                df_sorted['ma'] = df_sorted['close'].rolling(window=ma_period, min_periods=ma_period).mean()
                
                # 获取最新数据
                latest = df_sorted.iloc[-1]
                latest_close = latest['close']
                latest_ma = latest['ma']
                
                # 检查均线是否有效
                if pd.isna(latest_ma):
                    failed_reasons['insufficient_data'] += 1
                    continue
                
                # 判断是否站上均线
                if latest_close > latest_ma:
                    pct_above = (latest_close - latest_ma) / latest_ma * 100
                    passed_stocks.append({
                        'code': code,
                        'close': latest_close,
                        'ma': latest_ma,
                        'pct_above': pct_above,
                        'data_points': len(df_sorted)
                    })
                else:
                    failed_reasons['below_ma'] += 1
                    
            except Exception as e:
                logger.debug(f"[{code}] 筛选失败: {e}")
                failed_reasons['insufficient_data'] += 1
                continue
        
        # 按高出均线的百分比排序（降序）
        passed_stocks.sort(key=lambda x: x['pct_above'], reverse=True)
        
        # 统计信息
        stats = {
            'total': len(weekly_data),
            'passed': len(passed_stocks),
            'failed': len(weekly_data) - len(passed_stocks),
            'pass_rate': len(passed_stocks) / len(weekly_data) * 100 if weekly_data else 0,
            'reasons': failed_reasons
        }
        
        logger.info(
            f"筛选完成: 总数={stats['total']}, 通过={stats['passed']}, "
            f"失败={stats['failed']}, 通过率={stats['pass_rate']:.2f}%"
        )
        logger.info(
            f"失败原因: 数据不足={failed_reasons['insufficient_data']}, "
            f"均线下方={failed_reasons['below_ma']}"
        )
        
        return passed_stocks, stats
    
    def filter_stocks_by_price_volume(
        self,
        weekly_data: Dict[str, pd.DataFrame],
        passed_from_step4: List[Dict[str, Any]],
        min_price: float = 3.0,
        max_price: float = 70.0,
        min_amount: float = 5e8,  # 5亿元（人民币）
        volume_ma5_period: int = 5,
        volume_ma60_period: int = 60,
        min_deviation: float = -3.0,
        max_deviation: float = 7.0,
        min_data_points: int = 65
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        步骤5: 根据价格、成交额和成交量均线筛选股票
        
        筛选条件：
        1. 价格在 [min_price, max_price] 区间内（单位：人民币元）
        2. 最新成交额 >= min_amount（单位：人民币元）
        3. 5周成交量均线向上（最新值 > 前一周的值）
        4. 5周成交量均线与60周成交量均线偏离在 [min_deviation%, max_deviation%] 区间内
        
        Args:
            weekly_data: 股票代码->周K线数据的字典
            passed_from_step4: 第四步筛选通过的股票列表
            min_price: 最低价格，默认3元（人民币）
            max_price: 最高价格，默认70元（人民币）
            min_amount: 最低成交额，默认5亿元（人民币）
            volume_ma5_period: 成交量均线周期1，默认5周
            volume_ma60_period: 成交量均线周期2，默认60周
            min_deviation: 最小偏离度，默认-3%
            max_deviation: 最大偏离度，默认7%
            min_data_points: 最小数据点数，默认65周
            
        Returns:
            Tuple[List[Dict], Dict]: 
                - 符合条件的股票列表
                - 统计信息
        """
        passed_stocks = []
        failed_reasons = {
            'not_in_step4': 0,  # 不在第四步结果中
            'price_out_of_range': 0,  # 价格不在范围内
            'amount_too_low': 0,  # 成交额不足
            'insufficient_data': 0,  # 数据不足
            'volume_ma5_not_rising': 0,  # 5周成交量均线不向上
            'deviation_out_of_range': 0,  # 偏离度不在范围内
        }
        
        # 创建第四步结果的快速查找字典
        step4_codes = {stock['code'] for stock in passed_from_step4}
        
        logger.info(
            f"开始步骤5筛选，条件: "
            f"价格[{min_price}, {max_price}]元, "
            f"成交额>={min_amount/1e8:.1f}亿元, "
            f"成交量MA5向上, "
            f"偏离度[{min_deviation}%, {max_deviation}%]"
        )
        logger.info(f"待筛选股票数: {len(weekly_data)}, 第四步通过数: {len(step4_codes)}")
        
        for code, df in weekly_data.items():
            try:
                # 检查是否在第四步结果中
                if code not in step4_codes:
                    failed_reasons['not_in_step4'] += 1
                    continue
                
                # 检查数据是否足够
                if df is None or len(df) < min_data_points:
                    failed_reasons['insufficient_data'] += 1
                    continue
                
                # 确保有必要的数据列
                required_cols = ['close', 'amount', 'volume']
                if not all(col in df.columns for col in required_cols):
                    logger.warning(f"[{code}] 缺少必要列")
                    failed_reasons['insufficient_data'] += 1
                    continue
                
                # 按日期排序
                df_sorted = df.sort_values('date').copy()
                
                # 获取最新数据
                latest = df_sorted.iloc[-1]
                latest_close = latest['close']
                latest_amount = latest['amount']
                
                # 条件1: 价格在范围内
                if not (min_price <= latest_close <= max_price):
                    failed_reasons['price_out_of_range'] += 1
                    continue
                
                # 条件2: 成交额足够
                if latest_amount < min_amount:
                    failed_reasons['amount_too_low'] += 1
                    continue
                
                # 计算成交量均线
                df_sorted['volume_ma5'] = df_sorted['volume'].rolling(
                    window=volume_ma5_period, 
                    min_periods=volume_ma5_period
                ).mean()
                
                df_sorted['volume_ma60'] = df_sorted['volume'].rolling(
                    window=volume_ma60_period, 
                    min_periods=volume_ma60_period
                ).mean()
                
                # 获取最新的均线值
                latest_volume_ma5 = df_sorted.iloc[-1]['volume_ma5']
                prev_volume_ma5 = df_sorted.iloc[-2]['volume_ma5']
                latest_volume_ma60 = df_sorted.iloc[-1]['volume_ma60']
                
                # 检查均线是否有效
                if pd.isna(latest_volume_ma5) or pd.isna(prev_volume_ma5) or pd.isna(latest_volume_ma60):
                    failed_reasons['insufficient_data'] += 1
                    continue
                
                # 条件3: 5日成交量均线向上
                if latest_volume_ma5 <= prev_volume_ma5:
                    failed_reasons['volume_ma5_not_rising'] += 1
                    continue
                
                # 条件4: 计算偏离度
                deviation = (latest_volume_ma5 - latest_volume_ma60) / latest_volume_ma60 * 100
                
                if not (min_deviation <= deviation <= max_deviation):
                    failed_reasons['deviation_out_of_range'] += 1
                    continue
                
                # 所有条件通过
                passed_stocks.append({
                    'code': code,
                    'close': latest_close,
                    'amount': latest_amount,
                    'volume_ma5': latest_volume_ma5,
                    'volume_ma60': latest_volume_ma60,
                    'deviation': deviation,
                    'data_points': len(df_sorted)
                })
                
            except Exception as e:
                logger.debug(f"[{code}] 筛选失败: {e}")
                failed_reasons['insufficient_data'] += 1
                continue
        
        # 按偏离度排序（从低到高，越接近0越好）
        passed_stocks.sort(key=lambda x: abs(x['deviation']))
        
        # 统计信息
        stats = {
            'total': len(weekly_data),
            'passed': len(passed_stocks),
            'failed': len(weekly_data) - len(passed_stocks),
            'pass_rate': len(passed_stocks) / len(weekly_data) * 100 if weekly_data else 0,
            'reasons': failed_reasons
        }
        
        logger.info(
            f"筛选完成: 总数={stats['total']}, 通过={stats['passed']}, "
            f"失败={stats['failed']}, 通过率={stats['pass_rate']:.2f}%"
        )
        logger.info(
            f"失败原因: "
            f"不在第四步={failed_reasons['not_in_step4']}, "
            f"价格不符={failed_reasons['price_out_of_range']}, "
            f"成交额不足={failed_reasons['amount_too_low']}, "
            f"数据不足={failed_reasons['insufficient_data']}, "
            f"MA5不向上={failed_reasons['volume_ma5_not_rising']}, "
            f"偏离度不符={failed_reasons['deviation_out_of_range']}"
        )
        
        return passed_stocks, stats
    
    def get_daily_data_batch_with_failover(
        self,
        stock_codes: List[str],
        days: int = 10,
        max_workers: int = 3
    ) -> Tuple[Dict[str, pd.DataFrame], str]:
        """
        批量获取日K数据（多线程、故障切换）
        
        Args:
            stock_codes: 股票代码列表
            days: 获取天数，默认10天
            max_workers: 最大并发线程数，默认5
            
        Returns:
            Tuple[Dict[str, DataFrame], str]: 
                - 股票代码->日K数据的字典
                - 成功的数据源名称
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        daily_data = {}
        successful_source = None
        
        logger.info(f"开始批量获取日K数据，共 {len(stock_codes)} 只股票，{days} 天数据")
        
        # 使用线程池并发获取
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_code = {
                executor.submit(
                    self.get_daily_data,
                    code,
                    None,
                    None,
                    days
                ): code for code in stock_codes
            }
            
            # 收集结果
            for future in as_completed(future_to_code):
                code = future_to_code[future]
                try:
                    df, source = future.result()
                    if df is not None and not df.empty:
                        daily_data[code] = df
                        if successful_source is None:
                            successful_source = source
                except Exception as e:
                    logger.debug(f"[{code}] 获取日K数据失败: {e}")
        
        logger.info(f"批量获取日K数据完成: 成功 {len(daily_data)}/{len(stock_codes)}")
        
        return daily_data, successful_source
