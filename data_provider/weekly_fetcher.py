# -*- coding: utf-8 -*-
"""
===================================
WeeklyFetcher - 周K线数据获取器（沪深主板专用）
===================================

设计目标：
1. 从多个数据源获取周K线数据
2. 遵循项目策略模式，继承 BaseFetcher
3. 实现自动故障切换
4. 仅获取沪深主板股票（排除ST、科创板、创业板、北交所）
5. 支持多线程并发获取

数据源优先级：
0. Efinance (优先，数据质量高)
0. Baostock (优先，免费稳定)
1. Akshare (备选)
2. Tushare (备选，需Token)
4. Yfinance (兜底)

过滤规则：
- 沪市主板：600xxx, 601xxx, 603xxx
- 深市主板：000xxx, 001xxx, 002xxx
- 排除：ST/*ST 股票、科创板(688)、创业板(300)、北交所(8/4)
- 排除：上市不足2年的股票
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any

import pandas as pd
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .base import BaseFetcher, DataFetchError, normalize_stock_code, STANDARD_COLUMNS

logger = logging.getLogger(__name__)


def is_main_board_stock(stock_code: str, stock_name: Optional[str] = None) -> bool:
    """
    判断是否为沪深主板股票（排除ST）
    
    沪市主板：600xxx, 601xxx, 603xxx
    深市主板：000xxx, 001xxx, 002xxx
    排除：ST/*ST 股票、科创板(688)、创业板(300)、北交所(8/4)
    
    Args:
        stock_code: 股票代码
        stock_name: 股票名称（可选）
        
    Returns:
        True=沪深主板，False=非沪深主板
    """
    code = normalize_stock_code(stock_code)
    
    # 排除科创板
    if code.startswith('688'):
        return False
    
    # 排除创业板
    if code.startswith('300'):
        return False
    
    # 排除北交所
    if code.startswith('8') or code.startswith('4'):
        return False
    
    # 排除ST股票
    if stock_name:
        name_upper = stock_name.upper()
        if 'ST' in name_upper or '*ST' in name_upper:
            return False
    
    # 沪市主板：600, 601, 603
    if code.startswith('600') or code.startswith('601') or code.startswith('603'):
        return True
    
    # 深市主板：000, 001, 002
    if code.startswith('000') or code.startswith('001') or code.startswith('002'):
        return True
    
    return False


def is_listed_over_2_years(list_date: Optional[str]) -> bool:
    """
    判断股票是否上市超过2年
    
    Args:
        list_date: 上市日期，格式 'YYYY-MM-DD' 或 'YYYYMMDD'
        
    Returns:
        True=上市超过2年，False=上市不足2年或日期无效
    """
    if not list_date:
        return False
    
    try:
        # 处理不同的日期格式
        if '-' in list_date:
            list_dt = datetime.strptime(list_date, '%Y-%m-%d')
        else:
            list_dt = datetime.strptime(list_date, '%Y%m%d')
        
        # 计算上市时长
        days_listed = (datetime.now() - list_dt).days
        years_listed = days_listed / 365.25
        
        return years_listed >= 2.0
    except Exception as e:
        logger.debug(f"解析上市日期失败 {list_date}: {e}")
        return False


class EfinanceWeeklyFetcher(BaseFetcher):
    """
    使用 Efinance 获取周K线数据（仅沪深主板）
    """
    
    name = "EfinanceWeeklyFetcher"
    priority = 0
    version = "v1.0.0"
    last_updated = "2026-04-08"
    
    def __init__(self):
        self._available = None
        logger.info(f"[{self.name}] 初始化数据源 | 版本: {self.version} | 更新时间: {self.last_updated} | 优先级: P{self.priority}")
    
    def _check_available(self) -> bool:
        """检查 Efinance 是否可用"""
        if self._available is not None:
            return self._available
        
        try:
            import efinance
            self._available = True
            logger.info(f"{self.name} 可用")
            return True
        except ImportError:
            self._available = False
            logger.debug(f"{self.name} 依赖 efinance 未安装")
            return False
    
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从 Efinance 获取周K线原始数据"""
        import efinance
        
        code = normalize_stock_code(stock_code)
        
        # 根据股票代码判断市场
        if code.startswith('6'):
            market = 'sh'
            code = f'{code}.SH'
        elif code.startswith('3') or code.startswith('0'):
            market = 'sz'
            code = f'{code}.SZ'
        elif code.startswith('8') or code.startswith('4'):
            market = 'bj'
            code = f'{code}.BJ'
        else:
            market = 'sz'
            code = f'{code}.SZ'
        
        # 获取周K线数据（前复权）
        df = efinance.stock.get_quote_history(
            code, 
            market=market,
            period='week',
            adjust='qfq'
        )
        
        if df is None or df.empty:
            raise DataFetchError(f"未获取到 {stock_code} 的周K线数据")
        
        return df
    
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """标准化周K线数据列名"""
        normalized = df.copy()
        
        column_mapping = {
            'date': 'date',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume',
            'amount': 'amount',
            'pct_chg': 'pct_chg',
            '涨跌幅': 'pct_chg',
        }
        
        for old_name, new_name in column_mapping.items():
            if old_name in normalized.columns and new_name not in normalized.columns:
                normalized = normalized.rename(columns={old_name: new_name})
        
        missing = [col for col in STANDARD_COLUMNS if col not in normalized.columns]
        if missing:
            raise DataFetchError(
                f"Efinance 周K线数据缺少必需列: {','.join(missing)}"
            )
        
        return normalized[STANDARD_COLUMNS]
    
    def get_all_stock_list(self) -> List[Dict[str, Any]]:
        """
        获取全市场股票列表（包含上市时间）
        
        Returns:
            List[Dict]: 股票列表，每个元素包含 'code', 'name', 'list_date'
        """
        import efinance
        
        try:
            logger.info("正在获取所有股票列表...")
            
            # Efinance 没有直接获取上市时间的接口，使用 akshare 的数据
            # 这里返回空列表，让故障切换机制切换到下一个数据源
            logger.warning("Efinance 不支持获取上市时间，跳过")
            return []
            
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []
    
    def fetch_weekly_data_for_stocks(
        self,
        stock_codes: List[str],
        end_date: str = None,
        weeks: int = 104,
        max_workers: int = 5
    ) -> Dict[str, pd.DataFrame]:
        """
        多线程并发获取多只股票的周K线数据
        
        Args:
            stock_codes: 股票代码列表
            end_date: 结束日期
            weeks: 获取周数
            max_workers: 最大线程数
            
        Returns:
            字典，键为股票代码，值为 DataFrame
        """
        import efinance
        
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        start_date = (datetime.now() - timedelta(weeks=weeks)).strftime('%Y-%m-%d')
        
        logger.info(f"开始并发获取 {len(stock_codes)} 只股票的周K线数据（{max_workers}线程）")
        
        results = {}
        
        def fetch_single_stock(stock_code: str) -> Tuple[str, Optional[pd.DataFrame]]:
            """获取单只股票的周K线数据"""
            try:
                code = normalize_stock_code(stock_code)
                
                # 根据股票代码判断市场
                if code.startswith('6'):
                    market = 'sh'
                    code_with_market = f'{code}.SH'
                elif code.startswith('3') or code.startswith('0'):
                    market = 'sz'
                    code_with_market = f'{code}.SZ'
                else:
                    market = 'sz'
                    code_with_market = f'{code}.SZ'
                
                # 获取周K线数据（前复权）
                df = efinance.stock.get_quote_history(
                    code_with_market, 
                    market=market,
                    period='week',
                    adjust='qfq'
                )
                
                if df is not None and not df.empty and len(df) >= weeks:
                    return stock_code, df
                else:
                    return stock_code, None
                    
            except Exception as e:
                logger.debug(f"获取 {stock_code} 周K线数据失败: {e}")
                return stock_code, None
        
        # 使用线程池并发获取
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_code = {
                executor.submit(fetch_single_stock, code): code 
                for code in stock_codes
            }
            
            # 收集结果
            completed = 0
            for future in as_completed(future_to_code):
                code, df = future.result()
                if df is not None:
                    results[code] = df
                
                completed += 1
                if completed % 100 == 0:
                    logger.info(f"进度: {completed}/{len(stock_codes)} ({len(results)} 成功)")
        
        logger.info(f"并发获取完成: {len(results)}/{len(stock_codes)} 成功")
        return results


class AkshareWeeklyFetcher(BaseFetcher):
    """
    使用 Akshare 获取周K线数据（仅沪深主板）
    """
    
    name = "AkshareWeeklyFetcher"
    priority = 1
    version = "v1.0.0"
    last_updated = "2026-04-08"
    
    def __init__(self):
        self._available = None
        logger.info(f"[{self.name}] 初始化数据源 | 版本: {self.version} | 更新时间: {self.last_updated} | 优先级: P{self.priority}")
    
    def _check_available(self) -> bool:
        """检查 Akshare 是否可用"""
        if self._available is not None:
            return self._available
        
        try:
            import akshare as ak
            self._available = True
            logger.info(f"{self.name} 可用")
            return True
        except ImportError:
            self._available = False
            logger.debug(f"{self.name} 依赖 akshare 未安装")
            return False
    
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从 Akshare 获取周K线原始数据"""
        import akshare as ak
        
        code = normalize_stock_code(stock_code)
        
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="周",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )
        
        if df is None or df.empty:
            raise DataFetchError(f"未获取到 {stock_code} 的周K线数据")
        
        return df
    
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """标准化周K线数据列名"""
        normalized = df.copy()
        
        column_mapping = {
            '日期': 'date',
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '成交量': 'volume',
            '成交额': 'amount',
            '涨跌幅': 'pct_chg',
        }
        
        for old_name, new_name in column_mapping.items():
            if old_name in normalized.columns and new_name not in normalized.columns:
                normalized = normalized.rename(columns={old_name: new_name})
        
        missing = [col for col in STANDARD_COLUMNS if col not in normalized.columns]
        if missing:
            raise DataFetchError(
                f"Akshare 周K线数据缺少必需列: {','.join(missing)}"
            )
        
        return normalized[STANDARD_COLUMNS]
    
    def get_all_stock_list(self) -> List[Dict[str, Any]]:
        """
        获取全市场股票列表（包含上市时间）
        
        Returns:
            List[Dict]: 股票列表，每个元素包含 'code', 'name', 'list_date'
        """
        import akshare as ak
        
        try:
            logger.info("正在获取所有A股股票列表（包含上市时间）...")
            
            all_stocks = []
            
            try:
                df_info = ak.stock_info_sh_name_code()
                for idx, row in df_info.iterrows():
                    code = str(row.get('证券代码', ''))
                    name = str(row.get('证券简称', ''))
                    list_date = str(row.get('上市日期', ''))
                    
                    if code and name:
                        all_stocks.append({
                            'code': code,
                            'name': name,
                            'list_date': list_date if list_date and list_date != 'nan' else None
                        })
            except Exception as e:
                logger.debug(f"获取沪市股票列表失败: {e}")
            
            try:
                df_info_sz = ak.stock_info_sz_name_code()
                for idx, row in df_info_sz.iterrows():
                    code = str(row.get('A股代码', ''))
                    name = str(row.get('A股简称', ''))
                    list_date = str(row.get('A股上市日期', ''))
                    
                    if code and name:
                        all_stocks.append({
                            'code': code,
                            'name': name,
                            'list_date': list_date if list_date and list_date != 'nan' else None
                        })
            except Exception as e:
                logger.debug(f"获取深市股票列表失败: {e}")
            
            logger.info(f"共获取到 {len(all_stocks)} 只股票")
            return all_stocks
            
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []
    
    def fetch_weekly_data_for_stocks(
        self,
        stock_codes: List[str],
        end_date: str = None,
        weeks: int = 104,
        max_workers: int = 5
    ) -> Dict[str, pd.DataFrame]:
        """
        多线程并发获取多只股票的周K线数据
        
        Args:
            stock_codes: 股票代码列表
            end_date: 结束日期
            weeks: 获取周数
            max_workers: 最大线程数
            
        Returns:
            字典，键为股票代码，值为 DataFrame
        """
        import akshare as ak
        
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        start_date = (datetime.now() - timedelta(weeks=weeks)).strftime('%Y-%m-%d')
        
        logger.info(f"开始并发获取 {len(stock_codes)} 只股票的周K线数据（{max_workers}线程）")
        
        results = {}
        
        def fetch_single_stock(stock_code: str) -> Tuple[str, Optional[pd.DataFrame]]:
            """获取单只股票的周K线数据"""
            try:
                code = normalize_stock_code(stock_code)
                
                # 获取周K线数据
                df = ak.stock_zh_a_hist(
                    symbol=code,
                    period="周",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"
                )
                
                if df is not None and not df.empty and len(df) >= weeks:
                    return stock_code, df
                else:
                    return stock_code, None
                    
            except Exception as e:
                logger.debug(f"获取 {stock_code} 周K线数据失败: {e}")
                return stock_code, None
        
        # 使用线程池并发获取
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_code = {
                executor.submit(fetch_single_stock, code): code 
                for code in stock_codes
            }
            
            # 收集结果
            completed = 0
            for future in as_completed(future_to_code):
                code, df = future.result()
                if df is not None:
                    results[code] = df
                
                completed += 1
                if completed % 100 == 0:
                    logger.info(f"进度: {completed}/{len(stock_codes)} ({len(results)} 成功)")
        
        logger.info(f"并发获取完成: {len(results)}/{len(stock_codes)} 成功")
        return results


class TushareWeeklyFetcher(BaseFetcher):
    """
    使用 Tushare 获取周K线数据（仅沪深主板）
    """
    
    name = "TushareWeeklyFetcher"
    priority = 2
    version = "v1.0.0"
    last_updated = "2026-04-08"
    
    def __init__(self):
        self._available = None
        self._token = None
        self._api = None
        logger.info(f"[{self.name}] 初始化数据源 | 版本: {self.version} | 更新时间: {self.last_updated} | 优先级: P{self.priority}")
    
    def _check_available(self) -> bool:
        """检查 Tushare 是否可用"""
        if self._available is not None:
            return self._available
        
        try:
            import tushare as ts
            self._token = ts.get_token()
            if self._token:
                self._api = ts.pro_api(self._token)
                self._available = True
                logger.info(f"{self.name} 可用")
                return True
            else:
                logger.debug(f"{self.name} 未配置 TUSHARE_TOKEN")
                self._available = False
                return False
        except ImportError:
            self._available = False
            logger.debug(f"{self.name} 依赖 tushare 未安装")
            return False
    
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从 Tushare 获取周K线原始数据"""
        if not self._check_available():
            raise DataFetchError(f"{self.name} 不可用")
        
        code = normalize_stock_code(stock_code)
        
        if code.startswith('6'):
            ts_code = f'{code}.SH'
        elif code.startswith('3') or code.startswith('0'):
            ts_code = f'{code}.SZ'
        elif code.startswith('8') or code.startswith('4'):
            ts_code = f'{code}.BJ'
        else:
            ts_code = f'{code}.SZ'
        
        df = self._api.pro_bar(
            ts_code=ts_code,
            adj='qfq',
            freq='W',
            start_date=start_date,
            end_date=end_date
        )
        
        if df is None or df.empty:
            raise DataFetchError(f"未获取到 {stock_code} 的周K线数据")
        
        return df
    
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """标准化周K线数据列名"""
        normalized = df.copy()
        
        column_mapping = {
            'trade_date': 'date',
            'vol': 'volume',
        }
        
        for old_name, new_name in column_mapping.items():
            if old_name in normalized.columns and new_name not in normalized.columns:
                normalized = normalized.rename(columns={old_name: new_name})
        
        missing = [col for col in STANDARD_COLUMNS if col not in normalized.columns]
        if missing:
            raise DataFetchError(
                f"Tushare 周K线数据缺少必需列: {','.join(missing)}"
            )
        
        return normalized[STANDARD_COLUMNS]
    
    def get_all_stock_list(self) -> List[Dict[str, Any]]:
        """
        获取全市场股票列表（包含上市时间）
        
        Returns:
            List[Dict]: 股票列表，每个元素包含 'code', 'name', 'list_date'
        """
        if not self._check_available():
            raise DataFetchError(f"{self.name} 不可用")
        
        try:
            logger.info("正在获取所有A股股票列表（包含上市时间）...")
            
            # 获取所有A股列表（包含上市时间）
            df_stocks = self._api.stock_basic(
                exchange='',
                list_status='L',
                fields='ts_code,symbol,name,area,industry,list_date'
            )
            
            if df_stocks is None or df_stocks.empty:
                logger.error("未获取到股票列表")
                return []
            
            logger.info(f"共获取到 {len(df_stocks)} 只股票")
            
            all_stocks = []
            
            for idx, row in df_stocks.iterrows():
                ts_code = row.get('ts_code', '')
                name = row.get('name', '')
                list_date = row.get('list_date', '')
                
                # 提取代码部分（去掉后缀）
                if ts_code:
                    code = ts_code.split('.')[0] if '.' in ts_code else ts_code
                    
                    all_stocks.append({
                        'code': code,
                        'name': name,
                        'list_date': list_date if list_date else None
                    })
            
            return all_stocks
            
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []
    
    def fetch_weekly_data_for_stocks(
        self,
        stock_codes: List[str],
        end_date: str = None,
        weeks: int = 104,
        max_workers: int = 5
    ) -> Dict[str, pd.DataFrame]:
        """
        多线程并发获取多只股票的周K线数据
        
        Args:
            stock_codes: 股票代码列表
            end_date: 结束日期
            weeks: 获取周数
            max_workers: 最大线程数
            
        Returns:
            字典，键为股票代码，值为 DataFrame
        """
        if not self._check_available():
            raise DataFetchError(f"{self.name} 不可用")
        
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        start_date = (datetime.now() - timedelta(weeks=weeks)).strftime('%Y-%m-%d')
        
        logger.info(f"开始并发获取 {len(stock_codes)} 只股票的周K线数据（{max_workers}线程）")
        
        results = {}
        
        def fetch_single_stock(stock_code: str) -> Tuple[str, Optional[pd.DataFrame]]:
            """获取单只股票的周K线数据"""
            try:
                code = normalize_stock_code(stock_code)
                
                # 根据股票代码判断市场后缀
                if code.startswith('6'):
                    ts_code = f'{code}.SH'
                elif code.startswith('3') or code.startswith('0'):
                    ts_code = f'{code}.SZ'
                else:
                    ts_code = f'{code}.SZ'
                
                # 获取周K线数据
                df = self._api.pro_bar(
                    ts_code=ts_code,
                    adj='qfq',
                    freq='W',
                    start_date=start_date,
                    end_date=end_date
                )
                
                if df is not None and not df.empty and len(df) >= weeks:
                    return stock_code, df
                else:
                    return stock_code, None
                    
            except Exception as e:
                logger.debug(f"获取 {stock_code} 周K线数据失败: {e}")
                return stock_code, None
        
        # 使用线程池并发获取
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_code = {
                executor.submit(fetch_single_stock, code): code 
                for code in stock_codes
            }
            
            # 收集结果
            completed = 0
            for future in as_completed(future_to_code):
                code, df = future.result()
                if df is not None:
                    results[code] = df
                
                completed += 1
                if completed % 100 == 0:
                    logger.info(f"进度: {completed}/{len(stock_codes)} ({len(results)} 成功)")
        
        logger.info(f"并发获取完成: {len(results)}/{len(stock_codes)} 成功")
        return results


class BaostockWeeklyFetcher(BaseFetcher):
    """
    使用 Baostock 获取周K线数据（仅沪深主板）
    """
    
    name = "BaostockWeeklyFetcher"
    priority = 0
    version = "v1.0.1"
    last_updated = "2026-04-08"
    
    def __init__(self):
        self._available = None
        self._api = None
        logger.info(f"[{self.name}] 初始化数据源 | 版本: {self.version} | 更新时间: {self.last_updated} | 优先级: P{self.priority}")
    
    def _check_available(self) -> bool:
        """检查 Baostock 是否可用"""
        if self._available is not None:
            return self._available
        
        try:
            import baostock as bs
            self._api = bs
            self._available = True
            logger.info(f"{self.name} 可用")
            return True
        except ImportError:
            self._available = False
            logger.debug(f"{self.name} 依赖 baostock 未安装")
            return False
    
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从 Baostock 获取周K线原始数据"""
        if not self._check_available():
            raise DataFetchError(f"{self.name} 不可用")
        
        code = normalize_stock_code(stock_code)
        
        if code.startswith('6'):
            symbol = f'sh.{code}'
        elif code.startswith('3') or code.startswith('0'):
            symbol = f'sz.{code}'
        elif code.startswith('8') or code.startswith('4'):
            symbol = f'bj.{code}'
        else:
            symbol = f'sz.{code}'
        
        rs = self._api.query_history_k_data_plus(
            code=symbol,
            start_date=start_date,
            end_date=end_date,
            frequency="w",
            adjustflag="2"
        )
        
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(list(rs.get_row_data()))
        
        df = pd.DataFrame(
            data_list,
            columns=rs.fields
        )
        
        if df is None or df.empty:
            raise DataFetchError(f"未获取到 {stock_code} 的周K线数据")
        
        return df
    
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """标准化周K线数据列名"""
        normalized = df.copy()
        
        column_mapping = {
            'date': 'date',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume',
            'amount': 'amount',
            'pctChg': 'pct_chg',
        }
        
        for old_name, new_name in column_mapping.items():
            if old_name in normalized.columns and new_name not in normalized.columns:
                normalized = normalized.rename(columns={old_name: new_name})
        
        missing = [col for col in STANDARD_COLUMNS if col not in normalized.columns]
        if missing:
            raise DataFetchError(
                f"Baostock 周K线数据缺少必需列: {','.join(missing)}"
            )
        
        return normalized[STANDARD_COLUMNS]
    
    def get_all_stock_list(self) -> List[Dict[str, Any]]:
        """
        获取全市场股票列表（包含上市时间）
        
        Returns:
            List[Dict]: 股票列表，每个元素包含 'code', 'name', 'list_date'
        """
        if not self._check_available():
            raise DataFetchError(f"{self.name} 不可用")
        
        try:
            # 初始化 baostock
            lg = self._api.login()
            if lg.error_code != '0':
                logger.error(f"Baostock 登录失败: {lg.error_msg}")
                return []
            
            try:
                logger.info("正在获取所有A股股票列表（包含上市时间）...")
                
                # 获取所有A股股票列表
                rs = self._api.query_stock_basic()
                
                stock_list = []
                while (rs.error_code == '0') & rs.next():
                    stock_list.append(list(rs.get_row_data()))
                
                if not stock_list:
                    logger.error("未获取到股票列表")
                    return []
                
                df_basic = pd.DataFrame(
                    stock_list,
                    columns=rs.fields
                )
                
                logger.info(f"共获取到 {len(df_basic)} 只股票")
                
                all_stocks = []
                
                for idx, row in df_basic.iterrows():
                    code = row.get('code', '')
                    name = row.get('code_name', '')
                    list_date = row.get('ipoDate', '')  # Baostock 的上市日期字段
                    
                    if code:
                        all_stocks.append({
                            'code': code,
                            'name': name,
                            'list_date': list_date if list_date else None
                        })
                
                return all_stocks
                
            finally:
                self._api.logout()
                
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []
    
    def fetch_weekly_data_for_stocks(
        self,
        stock_codes: List[str],
        end_date: str = None,
        weeks: int = 104,
        max_workers: int = 5
    ) -> Dict[str, pd.DataFrame]:
        """
        多线程并发获取多只股票的周K线数据
        
        注意：Baostock 不支持多线程并发，会串行获取
        
        Args:
            stock_codes: 股票代码列表
            end_date: 结束日期
            weeks: 获取周数
            max_workers: 最大线程数（Baostock 会忽略此参数）
            
        Returns:
            字典，键为股票代码，值为 DataFrame
        """
        if not self._check_available():
            raise DataFetchError(f"{self.name} 不可用")
        
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        start_date = (datetime.now() - timedelta(weeks=weeks)).strftime('%Y-%m-%d')
        
        logger.info(f"开始获取 {len(stock_codes)} 只股票的周K线数据（Baostock 不支持多线程，将串行获取）")
        
        results = {}
        
        try:
            # 初始化 baostock
            lg = self._api.login()
            if lg.error_code != '0':
                logger.error(f"Baostock 登录失败: {lg.error_msg}")
                return results
            
            try:
                completed = 0
                for stock_code in stock_codes:
                    try:
                        code = normalize_stock_code(stock_code)
                        
                        # 根据股票代码判断市场
                        if code.startswith('6'):
                            symbol = f'sh.{code}'
                        elif code.startswith('3') or code.startswith('0'):
                            symbol = f'sz.{code}'
                        else:
                            symbol = f'sz.{code}'
                        
                        # 获取周K线数据
                        rs = self._api.query_history_k_data_plus(
                            code=symbol,
                            start_date=start_date,
                            end_date=end_date,
                            frequency="w",
                            adjustflag="2"
                        )
                        
                        data_list = []
                        while (rs.error_code == '0') & rs.next():
                            data_list.append(list(rs.get_row_data()))
                        
                        df = pd.DataFrame(
                            data_list,
                            columns=rs.fields
                        )
                        
                        if df is not None and not df.empty and len(df) >= weeks:
                            results[code] = df
                        
                        completed += 1
                        if completed % 100 == 0:
                            logger.info(f"进度: {completed}/{len(stock_codes)} ({len(results)} 成功)")
                            
                    except Exception as e:
                        logger.debug(f"获取 {stock_code} 周K线数据失败: {e}")
                        continue
                
            finally:
                self._api.logout()
                
        except Exception as e:
            logger.error(f"获取周K线数据失败: {e}")
        
        logger.info(f"获取完成: {len(results)}/{len(stock_codes)} 成功")
        return results


class PytdxWeeklyFetcher(BaseFetcher):
    """
    使用 Pytdx（通达信）获取周K线数据（仅沪深主板）
    """
    
    name = "PytdxWeeklyFetcher"
    priority = 2
    version = "v1.0.0"
    last_updated = "2026-04-08"
    
    def __init__(self):
        self._available = None
        self._api = None
        logger.info(f"[{self.name}] 初始化数据源 | 版本: {self.version} | 更新时间: {self.last_updated} | 优先级: P{self.priority}")
    
    def _check_available(self) -> bool:
        """检查 Pytdx 是否可用"""
        if self._available is not None:
            return self._available
        
        try:
            from pytdx.hq import TdxHq_API
            self._api = TdxHq_API()
            self._available = True
            logger.info(f"{self.name} 可用")
            return True
        except ImportError:
            self._available = False
            logger.debug(f"{self.name} 依赖 pytdx 未安装")
            return False
    
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从 Pytdx 获取周K线原始数据"""
        raise NotImplementedError("Pytdx 周K线数据获取尚未实现")
    
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """标准化周K线数据列名"""
        raise NotImplementedError("Pytdx 周K线数据标准化尚未实现")
    
    def get_all_stock_list(self) -> List[Dict[str, Any]]:
        """
        获取全市场股票列表（包含上市时间）
        
        注意：Pytdx 不提供上市时间信息
        
        Returns:
            List[Dict]: 股票列表，每个元素包含 'code', 'name', 'list_date'
        """
        if not self._check_available():
            raise DataFetchError(f"{self.name} 不可用")
        
        try:
            logger.info("正在获取所有A股股票列表...")
            
            from pytdx.hq import TdxHq_API
            
            api = TdxHq_API()
            
            with api.connect('119.147.212.81', 7709):
                # 获取沪市股票列表
                sh_stocks = []
                for market in [1]:  # 1=沪市
                    count = api.get_security_count(market)
                    for i in range(count):
                        stock = api.get_security_list(market, i)
                        if stock:
                            for s in stock:
                                code = s['code']
                                name = s['name']
                                sh_stocks.append({
                                    'code': code,
                                    'name': name,
                                    'list_date': None  # Pytdx 不提供上市时间
                                })
                
                # 获取深市股票列表
                sz_stocks = []
                for market in [0]:  # 0=深市
                    count = api.get_security_count(market)
                    for i in range(count):
                        stock = api.get_security_list(market, i)
                        if stock:
                            for s in stock:
                                code = s['code']
                                name = s['name']
                                sz_stocks.append({
                                    'code': code,
                                    'name': name,
                                    'list_date': None  # Pytdx 不提供上市时间
                                })
                
                all_stocks = sh_stocks + sz_stocks
                logger.info(f"共获取到 {len(all_stocks)} 只股票")
                return all_stocks
                
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []
    
    def fetch_weekly_data_for_stocks(
        self,
        stock_codes: List[str],
        end_date: str = None,
        weeks: int = 104,
        max_workers: int = 5
    ) -> Dict[str, pd.DataFrame]:
        """
        多线程并发获取多只股票的周K线数据
        
        注意：Pytdx 不支持多线程并发，会串行获取
        
        Args:
            stock_codes: 股票代码列表
            end_date: 结束日期
            weeks: 获取周数
            max_workers: 最大线程数（Pytdx 会忽略此参数）
            
        Returns:
            字典，键为股票代码，值为 DataFrame
        """
        if not self._check_available():
            raise DataFetchError(f"{self.name} 不可用")
        
        logger.info(f"开始获取 {len(stock_codes)} 只股票的周K线数据（Pytdx 不支持多线程，将串行获取）")
        
        logger.warning("Pytdx 周K线数据获取功能尚未完全实现，建议使用其他数据源")
        return {}


class YfinanceWeeklyFetcher(BaseFetcher):
    """
    使用 Yfinance（Yahoo Finance）获取周K线数据（仅沪深主板）
    """
    
    name = "YfinanceWeeklyFetcher"
    priority = 4
    version = "v1.0.0"
    last_updated = "2026-04-08"
    
    def __init__(self):
        self._available = None
        logger.info(f"[{self.name}] 初始化数据源 | 版本: {self.version} | 更新时间: {self.last_updated} | 优先级: P{self.priority}")
    
    def _check_available(self) -> bool:
        """检查 Yfinance 是否可用"""
        if self._available is not None:
            return self._available
        
        try:
            import yfinance
            self._available = True
            logger.info(f"{self.name} 可用")
            return True
        except ImportError:
            self._available = False
            logger.debug(f"{self.name} 依赖 yfinance 未安装")
            return False
    
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从 Yfinance 获取周K线原始数据"""
        import yfinance as yf
        
        code = normalize_stock_code(stock_code)
        
        # 转换为 yfinance 格式
        if code.startswith('6'):
            symbol = f'{code}.SS'
        elif code.startswith('3') or code.startswith('0'):
            symbol = f'{code}.SZ'
        elif code.startswith('8') or code.startswith('4'):
            symbol = f'{code}.BJ'
        else:
            symbol = f'{code}.SZ'
        
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date, interval='1wk', auto_adjust=True)
        
        if df is None or df.empty:
            raise DataFetchError(f"未获取到 {stock_code} 的周K线数据")
        
        return df
    
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """标准化周K线数据列名"""
        normalized = df.copy()
        
        normalized = normalized.reset_index()
        
        column_mapping = {
            'Date': 'date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume',
        }
        
        for old_name, new_name in column_mapping.items():
            if old_name in normalized.columns and new_name not in normalized.columns:
                normalized = normalized.rename(columns={old_name: new_name})
        
        # 添加缺失的列
        if 'amount' not in normalized.columns:
            normalized['amount'] = 0.0
        
        if 'pct_chg' not in normalized.columns:
            normalized['pct_chg'] = normalized['close'].pct_change() * 100
        
        missing = [col for col in STANDARD_COLUMNS if col not in normalized.columns]
        if missing:
            raise DataFetchError(
                f"Yfinance 周K线数据缺少必需列: {','.join(missing)}"
            )
        
        return normalized[STANDARD_COLUMNS]
    
    def get_all_stock_list(self) -> List[Dict[str, Any]]:
        """
        获取全市场股票列表（包含上市时间）
        
        注意：Yfinance 不提供A股完整股票列表
        
        Returns:
            List[Dict]: 股票列表，每个元素包含 'code', 'name', 'list_date'
        """
        if not self._check_available():
            raise DataFetchError(f"{self.name} 不可用")
        
        logger.warning("Yfinance 不提供A股完整股票列表，建议使用其他数据源")
        return []
    
    def fetch_weekly_data_for_stocks(
        self,
        stock_codes: List[str],
        end_date: str = None,
        weeks: int = 104,
        max_workers: int = 5
    ) -> Dict[str, pd.DataFrame]:
        """
        多线程并发获取多只股票的周K线数据
        
        Args:
            stock_codes: 股票代码列表
            end_date: 结束日期
            weeks: 获取周数
            max_workers: 最大线程数
            
        Returns:
            字典，键为股票代码，值为 DataFrame
        """
        import yfinance as yf
        
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        start_date = (datetime.now() - timedelta(weeks=weeks)).strftime('%Y-%m-%d')
        
        logger.info(f"开始并发获取 {len(stock_codes)} 只股票的周K线数据（{max_workers}线程）")
        
        results = {}
        
        def fetch_single_stock(stock_code: str) -> Tuple[str, Optional[pd.DataFrame]]:
            """获取单只股票的周K线数据"""
            try:
                code = normalize_stock_code(stock_code)
                
                # 转换为 yfinance 格式
                if code.startswith('6'):
                    symbol = f'{code}.SS'
                elif code.startswith('3') or code.startswith('0'):
                    symbol = f'{code}.SZ'
                else:
                    symbol = f'{code}.SZ'
                
                ticker = yf.Ticker(symbol)
                df = ticker.history(start=start_date, end=end_date, interval='1wk', auto_adjust=True)
                
                if df is not None and not df.empty and len(df) >= weeks:
                    return stock_code, df
                else:
                    return stock_code, None
                    
            except Exception as e:
                logger.debug(f"获取 {stock_code} 周K线数据失败: {e}")
                return stock_code, None
        
        # 使用线程池并发获取
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_code = {
                executor.submit(fetch_single_stock, code): code 
                for code in stock_codes
            }
            
            # 收集结果
            completed = 0
            for future in as_completed(future_to_code):
                code, df = future.result()
                if df is not None:
                    results[code] = df
                
                completed += 1
                if completed % 100 == 0:
                    logger.info(f"进度: {completed}/{len(stock_codes)} ({len(results)} 成功)")
        
        logger.info(f"并发获取完成: {len(results)}/{len(stock_codes)} 成功")
        return results

