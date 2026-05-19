# -*- coding: utf-8 -*-
"""净值分析（FundAnalyzer）：收益、风险、风险收益比与相对基准超额指标。"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
import pandas as pd

from .equity import prepare_equity_df


def equity_to_daily_nav(equity_df: pd.DataFrame, column: str = "total_asset") -> pd.Series:
    """将分钟级净值表聚合为日频净值序列（DatetimeIndex）。"""
    df = prepare_equity_df(equity_df)
    if df.empty:
        return pd.Series(dtype=float)
    daily = df.groupby(df["date"].dt.normalize(), sort=True)[column].last()
    daily.index = pd.to_datetime(daily.index)
    return daily.sort_index()


def build_equal_weight_benchmark(market_df: pd.DataFrame, price_col: str = "close") -> pd.Series:
    """
    由行情宽表构造等权市场基准净值（日频，起点归一为后续 analyze 处理）。
    market_df 需含 date、symbol、close。
    """
    need = {"date", "symbol", price_col}
    if not need.issubset(market_df.columns):
        raise ValueError(f"market_df 需包含列: {need}")
    df = market_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", price_col])
    df["day"] = df["date"].dt.normalize()
    daily = df.groupby(["day", "symbol"], sort=True)[price_col].last().unstack()
    ret = daily.pct_change().mean(axis=1, skipna=True).fillna(0.0)
    nav = (1.0 + ret).cumprod()
    if len(nav) > 0:
        nav.iloc[0] = 1.0
    nav.index = pd.to_datetime(nav.index)
    return nav.sort_index()


class FundAnalyzer:
    """日频净值相对基准的完整分析（逻辑来自净值分析 notebook）。"""

    def __init__(
        self,
        fund_net_value: pd.Series,
        benchmark: pd.Series,
        start_date: Optional[Union[str, pd.Timestamp]] = None,
        end_date: Optional[Union[str, pd.Timestamp]] = None,
        risk_free_rate: float = 0.02,
    ):
        fund_net_value = fund_net_value.sort_index()
        benchmark = benchmark.sort_index()
        if start_date is None:
            start_date = fund_net_value.index.min()
        if end_date is None:
            end_date = fund_net_value.index.max()
        start_date = pd.Timestamp(start_date)
        end_date = pd.Timestamp(end_date)

        self.fund_net_value_0 = fund_net_value.loc[start_date:end_date]
        if self.fund_net_value_0.empty:
            raise ValueError("净值序列在指定日期区间内为空")
        base = float(self.fund_net_value_0.iloc[0])
        if base == 0:
            raise ValueError("区间起点净值不能为 0")
        self.fund_net_value = self.fund_net_value_0 / base
        self.benchmark = benchmark.reindex(self.fund_net_value.index).ffill().bfill()
        if self.benchmark.isna().all():
            self.benchmark = pd.Series(1.0, index=self.fund_net_value.index)
        b0 = float(self.benchmark.iloc[0]) or 1.0
        self.benchmark = self.benchmark / b0
        returns_df = pd.concat(
            [
                self.fund_net_value.pct_change().rename("fund"),
                self.benchmark.pct_change().rename("benchmark"),
            ],
            axis=1,
        ).dropna()
        self.fund_returns = returns_df["fund"]
        self.benchmark_returns = returns_df["benchmark"]
        self.start_date = start_date
        self.end_date = end_date
        self.risk_free_rate = risk_free_rate
        self.analysis_results: Optional[Dict[str, Any]] = None

    def analyze(self) -> pd.DataFrame:
        n = len(self.fund_net_value)
        if n < 2 or len(self.fund_returns) < 1:
            raise ValueError("净值分析至少需要 2 个交易日观测")
        rf_daily = self.risk_free_rate / 252

        annualized_return = (self.fund_net_value.iloc[-1] / self.fund_net_value.iloc[0]) ** (
            250 / n
        ) - 1
        cumulated_return = (
            self.fund_net_value.iloc[-1] - self.fund_net_value.iloc[0]
        ) / self.fund_net_value.iloc[0]

        bench_up = self.benchmark_returns[self.benchmark_returns > 0]
        fund_up = self.fund_returns[self.benchmark_returns > 0]
        up_capture = (
            fund_up.mean() / bench_up.mean()
            if len(bench_up) > 0 and bench_up.mean() != 0
            else np.nan
        )

        annualized_volatility = float(np.std(self.fund_returns) * np.sqrt(252))
        downside_deviation = float(
            np.sqrt(np.mean(np.minimum(self.fund_returns - rf_daily, 0) ** 2)) * np.sqrt(252)
        )
        bench_down = self.benchmark_returns[self.benchmark_returns < 0]
        fund_down = self.fund_returns[self.benchmark_returns < 0]
        down_capture = (
            fund_down.mean() / bench_down.mean()
            if len(bench_down) > 0 and bench_down.mean() != 0
            else np.nan
        )

        peak = np.maximum.accumulate(self.fund_net_value)
        rel = self.fund_net_value / peak - 1
        trough_idx = int(np.argmin(rel.values))
        max_drawdown = float(
            (peak.iloc[trough_idx] - self.fund_net_value.iloc[trough_idx]) / peak.iloc[trough_idx]
        )
        peak_idx = int(np.argmax(self.fund_net_value.iloc[: trough_idx + 1].values))
        max_drawdown_days = trough_idx - peak_idx
        recovery_slice = self.fund_net_value.iloc[trough_idx:]
        recovery_idx = np.where(recovery_slice.values >= peak.iloc[trough_idx])[0]
        max_drawdown_recovery_days = (
            int(recovery_idx[0]) if len(recovery_idx) > 0 else None
        )

        excess_rf = self.fund_returns - rf_daily
        sharpe_ratio = (
            float(np.sqrt(252) * excess_rf.mean() / self.fund_returns.std())
            if self.fund_returns.std() > 0
            else 0.0
        )
        down_std = np.sqrt(np.mean(np.minimum(self.fund_returns - rf_daily, 0) ** 2))
        sortino_ratio = (
            float(np.sqrt(252) * excess_rf.mean() / down_std) if down_std > 0 else 0.0
        )
        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0.0
        win_rate = float(len(self.fund_returns[self.fund_returns > 0]) / len(self.fund_returns))

        merge_returns = pd.concat(
            [
                self.benchmark_returns.rename("benchmark_returns"),
                self.fund_returns.rename("fund_returns"),
            ],
            axis=1,
            join="inner",
        )
        merge_returns["excess_returns"] = (
            merge_returns["fund_returns"] - merge_returns["benchmark_returns"]
        )
        up_returns = merge_returns[merge_returns["benchmark_returns"] > 0]
        down_returns = merge_returns[merge_returns["benchmark_returns"] < 0]
        up_win_rate = (
            len(up_returns[up_returns["fund_returns"] > 0]) / len(up_returns)
            if len(up_returns) > 0
            else np.nan
        )
        down_win_rate = (
            len(down_returns[down_returns["fund_returns"] > 0]) / len(down_returns)
            if len(down_returns) > 0
            else np.nan
        )
        fund_neg = self.fund_returns[self.fund_returns < 0]
        odds = (
            self.fund_returns[self.fund_returns > 0].mean() / abs(fund_neg.mean())
            if len(fund_neg) > 0 and fund_neg.mean() != 0
            else np.nan
        )
        new_high_ratio = float(
            np.sum(self.fund_net_value.iloc[1:].values > peak[:-1].values) / (n - 1)
        )

        benchmark_return = (
            self.benchmark.iloc[-1] - self.benchmark.iloc[0]
        ) / self.benchmark.iloc[0]
        excess_return = cumulated_return - benchmark_return
        annualized_excess_return = (excess_return + 1) ** (252 / n) - 1

        aligned_bench = self.benchmark_returns.reindex(self.fund_returns.index).dropna()
        aligned_fund = self.fund_returns.reindex(aligned_bench.index).dropna()
        if len(aligned_bench) > 1 and np.var(aligned_bench, ddof=1) > 0:
            beta = float(
                np.cov(aligned_fund, aligned_bench, ddof=1)[0, 1]
                / np.var(aligned_bench, ddof=1)
            )
        else:
            beta = np.nan

        gap_data = self.fund_returns - self.benchmark_returns.reindex(self.fund_returns.index)
        gap_data = gap_data.dropna()
        excess_win_rate = float(np.sum(gap_data > 0) / len(gap_data)) if len(gap_data) else 0.0
        up_excess_win_rate = (
            len(up_returns[up_returns["excess_returns"] > 0]) / len(up_returns)
            if len(up_returns) > 0
            else np.nan
        )
        down_excess_win_rate = (
            len(down_returns[down_returns["excess_returns"] > 0]) / len(down_returns)
            if len(down_returns) > 0
            else np.nan
        )
        gap_pos = gap_data[gap_data > 0]
        gap_neg = gap_data[gap_data < 0]
        excess_odds = (
            gap_pos.mean() / abs(gap_neg.mean())
            if len(gap_neg) > 0 and gap_neg.mean() != 0
            else np.nan
        )

        excess_returns = gap_data
        excess_net_value = (1 + excess_returns).cumprod()
        if len(excess_net_value) > 0:
            excess_net_value.iloc[0] = 1.0
        exc_peak = np.maximum.accumulate(excess_net_value)
        portfolio_drawdown = (exc_peak - excess_net_value) / exc_peak
        excess_max_drawdown = float(np.max(portfolio_drawdown)) if len(portfolio_drawdown) else 0.0
        excess_calmar_ratio = (
            annualized_excess_return / excess_max_drawdown
            if excess_max_drawdown > 0
            else 0.0
        )
        excess_sharpe_ratio = (
            float(np.sqrt(252) * (gap_data - rf_daily).mean() / gap_data.std())
            if gap_data.std() > 0
            else 0.0
        )

        self.analysis_results = {
            "start_date": self.start_date,
            "end_date": self.end_date,
            "backtesting_length": n,
            "annualized_return": annualized_return,
            "cumulated_return": cumulated_return,
            "up_capture": up_capture,
            "annualized_volatility": annualized_volatility,
            "downside_deviation": downside_deviation,
            "down_capture": down_capture,
            "max_drawdown": max_drawdown,
            "max_drawdown_days": max_drawdown_days,
            "max_drawdown_recovery_days": max_drawdown_recovery_days,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "calmar_ratio": calmar_ratio,
            "win_rate": win_rate,
            "up_win_rate": up_win_rate,
            "down_win_rate": down_win_rate,
            "odds": odds,
            "new_high_ratio": new_high_ratio,
            "excess_return": excess_return,
            "annualized_excess_return": annualized_excess_return,
            "beta": beta,
            "excess_win_rate": excess_win_rate,
            "up_excess_win_rate": up_excess_win_rate,
            "down_excess_win_rate": down_excess_win_rate,
            "excess_odds": excess_odds,
            "excess_max_drawdown": excess_max_drawdown,
            "excess_calmar_ratio": excess_calmar_ratio,
            "excess_sharpe_ratio": excess_sharpe_ratio,
        }
        report_nav = pd.DataFrame(self.analysis_results, index=[0]).T
        report_nav.columns = ["分析结果"]
        return report_nav


def calc_nav_analysis(
    equity_df: pd.DataFrame,
    market_df: Optional[pd.DataFrame] = None,
    benchmark: Optional[pd.Series] = None,
    start_date: Optional[Union[str, pd.Timestamp]] = None,
    end_date: Optional[Union[str, pd.Timestamp]] = None,
    risk_free_rate: float = 0.02,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    从回测净值表生成日频净值分析报表。
    :param benchmark: 已处理好的基准日频净值；为空且提供 market_df 时用等权市场基准。
  """
    fund_nav = equity_to_daily_nav(equity_df)
    if fund_nav.empty:
        return pd.DataFrame(columns=["分析结果"]), {}

    if benchmark is None:
        if market_df is not None and not market_df.empty:
            benchmark = build_equal_weight_benchmark(market_df)
        else:
            benchmark = pd.Series(1.0, index=fund_nav.index)

    common_idx = fund_nav.index.intersection(benchmark.index)
    if len(common_idx) < 2:
        benchmark = benchmark.reindex(fund_nav.index).ffill().fillna(1.0)

    if start_date is None:
        start_date = fund_nav.index.min()
    if end_date is None:
        end_date = fund_nav.index.max()

    analyzer = FundAnalyzer(
        fund_net_value=fund_nav,
        benchmark=benchmark,
        start_date=start_date,
        end_date=end_date,
        risk_free_rate=risk_free_rate,
    )
    report_df = analyzer.analyze()
    return report_df, dict(analyzer.analysis_results or {})
