# -*- coding: utf-8 -*-
"""
绩效指标 — 兼容入口（实现位于 `logger_system.metrics` 子包）。

推荐新代码：
    from backtest_engine.log.metrics import calc_performance, prepare_equity_df

旧代码无需修改：
    from backtest_engine.log.performance_metrics import calc_performance
"""
from backtest_engine.log.metrics import *  # noqa: F403
from backtest_engine.log.metrics import __all__ as __all__
