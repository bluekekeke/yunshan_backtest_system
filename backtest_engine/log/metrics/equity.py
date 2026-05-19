# -*- coding: utf-8 -*-
"""净值序列：预处理、收益、回撤细节、波动与 Calmar 分子分母工具。"""
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd


def prepare_equity_df(equity_df: pd.DataFrame) -> pd.DataFrame:
    """排序并校验列；返回含 date、total_asset 的副本。"""
    if equity_df.empty:
        return equity_df.copy()
    need = {"date", "total_asset"}
    if not need.issubset(set(equity_df.columns)):
        raise ValueError(f"equity_df 需包含列: {need}")
    df = equity_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "total_asset"]).sort_values("date").reset_index(drop=True)
    return df


def equity_minute_returns(equity_df: pd.DataFrame, column: str = "total_asset") -> pd.Series:
    """相邻观测净值收益率（与 bar 频率一致，未必是日历分钟）。"""
    df = prepare_equity_df(equity_df) if "date" in equity_df.columns else equity_df.copy()
    s = df[column].astype(float)
    return s.pct_change().fillna(0.0)


def daily_returns_from_equity(equity_df: pd.DataFrame, column: str = "total_asset") -> pd.Series:
    """按自然日取当日最后一条净值，计算日收益率（适合非均匀分钟 bar 时算夏普/波动）。"""
    df = prepare_equity_df(equity_df)
    if df.empty:
        return pd.Series(dtype=float)
    daily = df.groupby(df["date"].dt.normalize(), sort=True)[column].last()
    return daily.pct_change().dropna()


def calc_total_return(equity_series: pd.Series) -> float:
    """总收益率：末/初 - 1。"""
    if equity_series.empty or equity_series.iloc[0] == 0:
        return 0.0
    return float(equity_series.iloc[-1] / equity_series.iloc[0] - 1.0)


def annualized_return_by_observations(
    total_return: float,
    n_observations: int,
    annual_days: int = 252,
    minutes_per_trading_day: int = 240,
) -> float:
    """
    按「观测条数」外推年化（与原回测汇总口径一致）：假设 n_obs 条对应
    `n_obs / (annual_days * minutes_per_trading_day)` 个「年单位」。
    """
    if n_observations <= 0:
        return 0.0
    denom = annual_days * minutes_per_trading_day
    if denom <= 0:
        return 0.0
    exp = denom / float(n_observations)
    return float((1.0 + total_return) ** exp - 1.0)


def annualized_return_by_calendar(
    equity_df: pd.DataFrame,
    total_return: Optional[float] = None,
    column: str = "total_asset",
) -> float:
    """
    按首末 `date` 的日历时间跨度做 CAGR：`(1+R)^(1/years)-1`。
    若跨度非正，返回 0。
    """
    df = prepare_equity_df(equity_df)
    if df.empty or len(df) < 2:
        return 0.0
    if total_return is None:
        total_return = calc_total_return(df[column])
    start = pd.Timestamp(df["date"].iloc[0])
    end = pd.Timestamp(df["date"].iloc[-1])
    seconds = (end - start).total_seconds()
    if seconds <= 0:
        return 0.0
    years = seconds / (365.25 * 24 * 3600)
    if years <= 0:
        return 0.0
    return float((1.0 + total_return) ** (1.0 / years) - 1.0)


def calc_max_drawdown_detail(equity_series: pd.Series) -> Dict[str, Any]:
    """
    最大回撤及简单历时（按观测索引）：从「最后一次创新高」到「回撤谷底」的 bar 数。
    """
    eq = equity_series.astype(float).reset_index(drop=True)
    if eq.empty:
        return {
            "max_drawdown": 0.0,
            "peak_index": None,
            "trough_index": None,
            "duration_bars": 0,
            "peak_value": None,
            "trough_value": None,
        }
    roll_max = eq.cummax()
    dd = (eq - roll_max) / roll_max
    trough_i = int(dd.values.argmin())
    prefix = eq.iloc[: trough_i + 1]
    rmax_prefix = roll_max.iloc[: trough_i + 1]
    same_peak = np.isclose(prefix.values, rmax_prefix.values)
    peak_indices = np.where(same_peak)[0]
    peak_i = int(peak_indices[-1]) if len(peak_indices) else 0
    return {
        "max_drawdown": float(dd.min()),
        "peak_index": peak_i,
        "trough_index": trough_i,
        "duration_bars": int(trough_i - peak_i),
        "peak_value": float(eq.iloc[peak_i]) if len(eq) else None,
        "trough_value": float(eq.iloc[trough_i]) if len(eq) else None,
    }


def calc_volatility_annualized(
    return_series: pd.Series,
    freq: str = "minute",
) -> float:
    """收益率序列的年化波动率（简单缩放）。"""
    r = return_series.dropna()
    if len(r) < 2:
        return 0.0
    if freq == "minute":
        factor = np.sqrt(252 * 240)
    else:
        factor = np.sqrt(252)
    return float(r.std() * factor)


def calc_calmar_ratio(
    annualized_return: float,
    max_drawdown: float,
) -> float:
    """
    Calmar = 年化收益 / |最大回撤|。最大回撤应为负数（如 -0.2）。
    """
    if max_drawdown >= 0 or annualized_return == 0:
        return 0.0
    return float(annualized_return / abs(max_drawdown))
