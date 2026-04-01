from types import SimpleNamespace

import pandas as pd

from data_provider.base import BaseFetcher, DataFetcherManager, DataSourceUnavailableError
from data_provider.realtime_types import RealtimeSource, UnifiedRealtimeQuote


def _sample_daily_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-03-28",
                "open": 100.0,
                "high": 102.0,
                "low": 99.0,
                "close": 101.0,
                "volume": 100000,
                "amount": 10100000.0,
                "pct_chg": 1.0,
            },
            {
                "date": "2026-03-31",
                "open": 101.0,
                "high": 103.0,
                "low": 100.5,
                "close": 102.5,
                "volume": 120000,
                "amount": 12300000.0,
                "pct_chg": 1.49,
            },
        ]
    )


class _DummyDailyFetcher(BaseFetcher):
    def __init__(self, name: str, calls: list[str], df: pd.DataFrame | None = None, err: Exception | None = None):
        self.name = name
        self.priority = 1
        self._calls = calls
        self._df = df
        self._err = err

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        return pd.DataFrame()

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        return df

    def get_daily_data(self, stock_code: str, start_date: str | None = None, end_date: str | None = None, days: int = 30):
        self._calls.append(self.name)
        if self._err is not None:
            raise self._err
        return self._df


class _DummyRealtimeFetcher(_DummyDailyFetcher):
    def __init__(self, name: str, calls: list[str], quote: UnifiedRealtimeQuote | None = None, err: Exception | None = None):
        super().__init__(name=name, calls=calls, err=err)
        self._quote = quote

    def get_realtime_quote(self, stock_code: str, source: str | None = None):
        self._calls.append(self.name if source is None else f"{self.name}:{source}")
        if self._err is not None:
            raise self._err
        return self._quote


class _DummyIFindFetcher(_DummyDailyFetcher):
    name = "IFindFetcher"

    def __init__(
        self,
        calls: list[str],
        daily_df: pd.DataFrame | None = None,
        realtime_quote: UnifiedRealtimeQuote | None = None,
        daily_error: Exception | None = None,
        realtime_error: Exception | None = None,
        supports_daily: bool = True,
        supports_realtime: bool = True,
    ):
        super().__init__(name="IFindFetcher", calls=calls, df=daily_df, err=daily_error)
        self.priority = -1
        self._realtime_quote = realtime_quote
        self._realtime_error = realtime_error
        self._supports_daily = supports_daily
        self._supports_realtime = supports_realtime

    def supports_daily_data(self) -> bool:
        return self._supports_daily

    def supports_realtime_quote(self) -> bool:
        return self._supports_realtime

    def get_realtime_quote(self, stock_code: str):
        self._calls.append(self.name)
        if self._realtime_error is not None:
            raise self._realtime_error
        return self._realtime_quote


def test_daily_data_prefers_ifind_fetcher_when_ths_mode_enabled(monkeypatch):
    calls: list[str] = []
    ifind = _DummyIFindFetcher(calls=calls, daily_df=_sample_daily_df())
    fallback = _DummyDailyFetcher(name="EfinanceFetcher", calls=calls, df=_sample_daily_df())
    manager = DataFetcherManager(fetchers=[fallback], ifind_fetcher=ifind)

    monkeypatch.setattr(
        "src.config.get_config",
        lambda: SimpleNamespace(enable_ths_pro_data=True, enable_ifind=False),
    )

    df, source = manager.get_daily_data("600519", start_date="2026-03-01", end_date="2026-03-31")

    assert source == "IFindFetcher"
    assert list(df["close"]) == [101.0, 102.5]
    assert calls == ["IFindFetcher"]


def test_realtime_quote_falls_back_when_ifind_fetcher_unavailable(monkeypatch):
    calls: list[str] = []
    ifind = _DummyIFindFetcher(
        calls=calls,
        supports_realtime=True,
        realtime_error=DataSourceUnavailableError("not entitled"),
    )
    fallback = _DummyRealtimeFetcher(
        name="EfinanceFetcher",
        calls=calls,
        quote=UnifiedRealtimeQuote(
            code="600519",
            source=RealtimeSource.EFINANCE,
            price=123.45,
        ),
    )
    manager = DataFetcherManager(fetchers=[fallback], ifind_fetcher=ifind)

    monkeypatch.setattr(
        "src.config.get_config",
        lambda: SimpleNamespace(
            enable_ths_pro_data=True,
            enable_ifind=False,
            enable_realtime_quote=True,
            realtime_source_priority="efinance",
        ),
    )

    quote = manager.get_realtime_quote("600519")

    assert quote is not None
    assert quote.source == RealtimeSource.EFINANCE
    assert quote.price == 123.45
    assert calls == ["IFindFetcher", "EfinanceFetcher"]
