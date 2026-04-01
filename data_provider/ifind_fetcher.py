# -*- coding: utf-8 -*-
"""
===================================
IFindFetcher - TongHuaShun professional data adapter
===================================

Wraps the shared iFinD service behind the existing fetcher interfaces so the
manager can prefer TongHuaShun market data when the capability is available.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.ifind.service import IFindService

from .base import BaseFetcher, DataSourceUnavailableError, STANDARD_COLUMNS
from .realtime_types import RealtimeSource, UnifiedRealtimeQuote, safe_float


class IFindFetcher(BaseFetcher):
    """TongHuaShun-backed fetcher that adapts iFinD service outputs."""

    name = "IFindFetcher"
    priority = -1

    def __init__(self, service: IFindService):
        self.service = service

    def supports_daily_data(self) -> bool:
        return self.service.supports_daily_data()

    def supports_realtime_quote(self) -> bool:
        return self.service.supports_realtime_quote()

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        payload = self.service.get_daily_data(stock_code, start_date, end_date)
        if payload is None:
            raise DataSourceUnavailableError("TongHuaShun daily data unavailable")

        if isinstance(payload, pd.DataFrame):
            return payload.copy()

        if isinstance(payload, dict):
            rows = payload.get("rows")
            if isinstance(rows, list):
                return pd.DataFrame(rows)

        raise DataSourceUnavailableError("TongHuaShun daily data payload unsupported")

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        normalized = df.copy()
        missing = [col for col in STANDARD_COLUMNS if col not in normalized.columns]
        if missing:
            raise DataSourceUnavailableError(
                f"TongHuaShun daily data missing required columns: {','.join(missing)}"
            )
        return normalized[STANDARD_COLUMNS]

    def get_realtime_quote(self, stock_code: str) -> UnifiedRealtimeQuote:
        payload = self.service.get_realtime_quote(stock_code)
        if payload is None:
            raise DataSourceUnavailableError("TongHuaShun realtime quote unavailable")

        if isinstance(payload, UnifiedRealtimeQuote):
            return payload

        if isinstance(payload, dict):
            return UnifiedRealtimeQuote(
                code=str(payload.get("stock_code") or stock_code),
                name=str(payload.get("name") or ""),
                source=RealtimeSource.FALLBACK,
                price=safe_float(payload.get("price")),
                change_pct=safe_float(payload.get("change_pct")),
                change_amount=safe_float(payload.get("change_amount")),
                volume=payload.get("volume"),
                amount=safe_float(payload.get("amount")),
                volume_ratio=safe_float(payload.get("volume_ratio")),
                turnover_rate=safe_float(payload.get("turnover_rate")),
                amplitude=safe_float(payload.get("amplitude")),
                open_price=safe_float(payload.get("open_price")),
                high=safe_float(payload.get("high")),
                low=safe_float(payload.get("low")),
                pre_close=safe_float(payload.get("pre_close")),
                pe_ratio=safe_float(payload.get("pe_ratio")),
                pb_ratio=safe_float(payload.get("pb_ratio")),
                total_mv=safe_float(payload.get("total_mv")),
                circ_mv=safe_float(payload.get("circ_mv")),
            )

        raise DataSourceUnavailableError("TongHuaShun realtime quote payload unsupported")
