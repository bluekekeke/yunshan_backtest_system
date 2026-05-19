# -*- coding: utf-8 -*-
"""
绩效指标子包（推荐从此处按模块引用）。

- `equity`：净值表预处理、收益、回撤细节、波动率、Calmar 辅助。
- `trade`：成交 FIFO、换手、笔数与胜率统计。
- `fund_analyzer`：日频净值 FundAnalyzer / `calc_nav_analysis`。
- `report`：`calc_performance` / `calc_metrics_table` / `calc_nav_analysis_table` 汇总入口。

兼容：仍可使用 `from backtest_engine.log.performance_metrics import calc_performance`。
"""
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
from .fund_analyzer import FundAnalyzer, calc_nav_analysis, equity_to_daily_nav
from .report import calc_metrics_table, calc_nav_analysis_table, calc_performance
from .trade import (
    calc_trade_counts,
    calc_trade_win_stats,
    calc_turnover_ratio,
    calendar_years_span,
    fifo_realized_pnls_gross,
)

__all__ = [
    "FundAnalyzer",
    "calc_nav_analysis",
    "calc_nav_analysis_table",
    "equity_to_daily_nav",
    "annualized_return_by_calendar",
    "annualized_return_by_observations",
    "calc_calmar_ratio",
    "calc_max_drawdown_detail",
    "calc_metrics_table",
    "calc_performance",
    "calc_total_return",
    "calc_trade_counts",
    "calc_trade_win_stats",
    "calc_turnover_ratio",
    "calc_volatility_annualized",
    "calendar_years_span",
    "daily_returns_from_equity",
    "equity_minute_returns",
    "fifo_realized_pnls_gross",
    "prepare_equity_df",
]
