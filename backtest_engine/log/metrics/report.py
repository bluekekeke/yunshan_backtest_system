# -*- coding: utf-8 -*-
"""绩效汇总：组装净值侧与可选成交侧指标（`calc_performance` 唯一实现处）。"""
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from config.settings import COMMISSION_RATE
from tools.calc_utils import calc_max_drawdown, calc_sharpe_ratio, calc_sortino_ratio

from .equity import (
    annualized_return_by_calendar,
    annualized_return_by_observations,
    calc_calmar_ratio,
    calc_max_drawdown_detail,
    calc_total_return,
    calc_volatility_annualized,
    daily_returns_from_equity,
    equity_minute_returns,
    prepare_equity_df,
)
from .trade import calc_trade_counts, calc_trade_win_stats, calc_turnover_ratio
from .fund_analyzer import calc_nav_analysis


def calc_performance(
    equity_df: pd.DataFrame,
    annual_days: int = 252,
    trade_df: Optional[pd.DataFrame] = None,
    market_df: Optional[pd.DataFrame] = None,
    benchmark: Optional[pd.Series] = None,
    minutes_per_trading_day: int = 240,
    return_freq_for_risk: str = "minute",
    risk_free_rate: float = 0.0,
    nav_risk_free_rate: float = 0.02,
    use_commission_in_fifo: bool = True,
    include_nav_analysis: bool = True,
) -> Dict[str, Any]:
    """
    回测绩效汇总（与拆分前 `performance_metrics.calc_performance` 行为一致）。

    净值侧实现见 `metrics.equity`；成交侧见 `metrics.trade`。
    """
    df = prepare_equity_df(equity_df)
    if df.empty:
        return {
            "总收益率": 0.0,
            "年化收益率": 0.0,
            "年化收益率_日历CAGR": 0.0,
            "最大回撤": 0.0,
            "夏普比率": 0.0,
            "实际交易日": 0,
            "总回测分钟数": 0,
        }

    equity_series = df["total_asset"].astype(float)
    total_return = calc_total_return(equity_series)
    total_minutes = len(df)
    annual_return_bar = annualized_return_by_observations(
        total_return,
        total_minutes,
        annual_days=annual_days,
        minutes_per_trading_day=minutes_per_trading_day,
    )
    annual_return_cal = annualized_return_by_calendar(df, total_return=total_return)
    max_dd = calc_max_drawdown(equity_series)

    if return_freq_for_risk == "day":
        r_series = daily_returns_from_equity(df)
        sharpe = calc_sharpe_ratio(r_series, risk_free_rate=risk_free_rate, freq="day")
        sortino = calc_sortino_ratio(r_series, risk_free_rate=risk_free_rate, freq="day")
        vol = calc_volatility_annualized(r_series, freq="day")
    else:
        r_series = equity_minute_returns(df)
        sharpe = calc_sharpe_ratio(r_series, risk_free_rate=risk_free_rate, freq="minute")
        sortino = calc_sortino_ratio(r_series, risk_free_rate=risk_free_rate, freq="minute")
        vol = calc_volatility_annualized(r_series, freq="minute")

    calmar_bar = calc_calmar_ratio(annual_return_bar, max_dd)
    calmar_cal = calc_calmar_ratio(annual_return_cal, max_dd)
    dd_detail = calc_max_drawdown_detail(equity_series)
    real_trade_days = int(df["date"].dt.date.nunique())

    out: Dict[str, Any] = {
        "总收益率": round(total_return, 6),
        "年化收益率": round(annual_return_bar, 6),
        "年化收益率_日历CAGR": round(annual_return_cal, 6),
        "最大回撤": round(max_dd, 6),
        "夏普比率": round(float(sharpe), 6),
        "索提诺比率": round(float(sortino), 6),
        "年化波动率": round(vol, 6),
        "Calmar_按观测年化": round(float(calmar_bar), 6),
        "Calmar_按日历年化": round(float(calmar_cal), 6),
        "最大回撤持续bar数": dd_detail["duration_bars"],
        "实际交易日": real_trade_days,
        "总回测分钟数": total_minutes,
    }

    if trade_df is not None and not trade_df.empty:
        cr = float(COMMISSION_RATE) if use_commission_in_fifo else 0.0
        tw = calc_trade_win_stats(trade_df, commission_rate=cr)
        tc = calc_trade_counts(trade_df)
        to = calc_turnover_ratio(trade_df, df)
        out.update(
            {
                "换手_近似年化": round(to, 6),
                "成交笔数_买": tc["buy_count"],
                "成交笔数_卖": tc["sell_count"],
                "FIFO配对笔数": tw["round_trip_count"],
                "胜率_FIFO毛盈亏": round(tw["win_rate"], 6),
                "盈亏比_FIFO毛": round(float(tw["profit_factor"]), 6),
            }
        )

    if include_nav_analysis and not df.empty:
        try:
            _, nav_dict = calc_nav_analysis(
                equity_df,
                market_df=market_df if benchmark is None else None,
                benchmark=benchmark,
                risk_free_rate=nav_risk_free_rate,
            )
            out.update(_nav_metrics_to_chinese(nav_dict))
        except Exception as exc:
            out["净值分析错误"] = str(exc)

    return out


def calc_nav_analysis_table(
    equity_df: pd.DataFrame,
    market_df: Optional[pd.DataFrame] = None,
    benchmark: Optional[pd.Series] = None,
    risk_free_rate: float = 0.02,
    **kwargs: Any,
) -> pd.DataFrame:
    """净值分析完整报表（单列「分析结果」，便于导出 CSV）。"""
    report_df, _ = calc_nav_analysis(
        equity_df,
        market_df=market_df if benchmark is None else None,
        benchmark=benchmark,
        risk_free_rate=risk_free_rate,
        **kwargs,
    )
    return report_df


def _nav_metrics_to_chinese(nav: Dict[str, Any]) -> Dict[str, Any]:
    """将 FundAnalyzer 英文字段映射为绩效 dict 中的中文键（供打印与汇总）。"""
    mapping = {
        "annualized_return": "净值_年化收益率",
        "cumulated_return": "净值_累计收益率",
        "annualized_volatility": "净值_年化波动率",
        "downside_deviation": "净值_下行风险",
        "max_drawdown": "净值_最大回撤",
        "max_drawdown_days": "净值_最大回撤持续天数",
        "max_drawdown_recovery_days": "净值_最大回撤恢复天数",
        "sharpe_ratio": "净值_夏普比率",
        "sortino_ratio": "净值_索提诺比率",
        "calmar_ratio": "净值_卡玛比率",
        "win_rate": "净值_胜率",
        "up_capture": "净值_上行捕获",
        "down_capture": "净值_下行捕获",
        "odds": "净值_赔率",
        "new_high_ratio": "净值_创新高比例",
        "excess_return": "净值_累计超额收益",
        "annualized_excess_return": "净值_年化超额收益",
        "beta": "净值_Beta",
        "excess_win_rate": "净值_超额胜率",
        "excess_max_drawdown": "净值_最大超额回撤",
        "excess_sharpe_ratio": "净值_超额夏普",
    }
    out: Dict[str, Any] = {}
    for en_key, cn_key in mapping.items():
        if en_key not in nav:
            continue
        val = nav[en_key]
        if isinstance(val, (float, np.floating)):
            if np.isnan(val):
                out[cn_key] = None
            else:
                out[cn_key] = round(float(val), 6)
        else:
            out[cn_key] = val
    return out


def calc_metrics_table(
    equity_df: pd.DataFrame,
    trade_df: Optional[pd.DataFrame] = None,
    **kwargs: Any,
) -> pd.DataFrame:
    """将 `calc_performance` 结果转为单列 DataFrame，便于导出。"""
    perf = calc_performance(equity_df, trade_df=trade_df, **kwargs)
    return pd.DataFrame({"value": perf})
