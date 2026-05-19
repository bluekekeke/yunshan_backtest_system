# -*- coding: utf-8 -*-
"""
DataFrame、实体与表格转换工具
"""
import pandas as pd
from typing import List
from backtest_engine.core.entities import TradingSignal


def signals_to_df(signals: List[TradingSignal]) -> pd.DataFrame:
    """交易信号列表转DataFrame"""
    if not signals:
        return pd.DataFrame(columns=[
            "timestamp", "symbol", "direction", "price",
            "signal_type", "confidence", "remark"
        ])
    data = [sig.to_dict() for sig in signals]
    df = pd.DataFrame(data)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def drop_duplicate_df(df: pd.DataFrame, subset: list) -> pd.DataFrame:
    """按指定列去重，保留第一条"""
    return df.drop_duplicates(subset=subset, keep="first")


def df_filter_by_date(df: pd.DataFrame, start_dt, end_dt, date_col: str = "date") -> pd.DataFrame:
    """
    按时间范围筛选 DataFrame（闭区间，含起止自然日全天）。
    分钟级 date 带时分秒时，end_dt 会扩展到当日 23:59:59，避免只匹配 0 点导致截断。
    """
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
    start_ts = pd.Timestamp(start_dt).normalize()
    end_ts = pd.Timestamp(end_dt).normalize() + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    mask = (out[date_col] >= start_ts) & (out[date_col] <= end_ts)
    return out.loc[mask].copy()
