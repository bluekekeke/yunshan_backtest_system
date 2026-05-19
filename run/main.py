# -*- coding: utf-8 -*-
"""
回测启动脚本
"""
import sys

ROOT_PATH = r"E:\云杉树实习\backtest_system"
sys.path.append(ROOT_PATH)

import pandas as pd

from config.settings import (
    BENCHMARK_CSV_PATH,
    BENCHMARK_NAME,
    DATA_CSV_PATH,
    INITIAL_CAPITAL,
    START_DATE,
    END_DATE,
    TOP_N,
    REBALANCE_INTERVAL,
    REBALANCE_MODE,
    REBALANCE_BARS,
)
from data.data_processor import load_backtest_data, load_benchmark_nav
from strategy.strategy_low_price import LowPriceMinuteStrategy
from backtest_engine.module.portfolio_manager import PortfolioManager
from risk_manager.risk_manager import RiskManager
from backtest_engine.module.order_generator import OrderGenerator
from backtest_engine.backtest_engine import BacktestEngine
from analyse.plotter import BacktestPlotter
from tools.output_paths import make_run_stamp, build_output_path
from tools.run_log import RunLog


def _rebalance_chart_caption() -> str:
    if str(REBALANCE_MODE).strip().lower() == "bar":
        return f"每{REBALANCE_BARS}根K线调仓"
    return f"{REBALANCE_INTERVAL}分钟调仓"


def main():
    log = RunLog("策略回测")
    log.banner(
        数据路径=DATA_CSV_PATH,
        基准路径=f"{BENCHMARK_CSV_PATH}（{BENCHMARK_NAME}）",
        回测区间=f"{START_DATE.date()} ~ {END_DATE.date()}",
        初始资金=f"{INITIAL_CAPITAL:,.0f}",
        持仓数量=TOP_N,
        调仓模式=REBALANCE_MODE,
    )

    with log.section("加载数据"):
        df = load_backtest_data(log=log)
        benchmark_nav = load_benchmark_nav(log=log)

    with log.section("初始化组件"):
        strategy = LowPriceMinuteStrategy(top_n=TOP_N)
        pm = PortfolioManager(max_positions=TOP_N)
        rm = RiskManager()
        og = OrderGenerator(portfolio_manager=pm)
        engine = BacktestEngine(
            strategy=strategy,
            portfolio_manager=pm,
            risk_manager=rm,
            order_generator=og,
            initial_capital=INITIAL_CAPITAL,
        )
        log.detail("策略 / 组合 / 风控 / 订单 / 引擎 就绪")

    with log.section("回测主循环"):
        result = engine.run(df, run_log=log, benchmark_nav=benchmark_nav)

    run_stamp = make_run_stamp()
    with log.section("保存结果"):
        equity_path = build_output_path("results/equity", "equity_curve", run_stamp)
        trades_path = build_output_path("results/trades", "trades", run_stamp)
        signals_path = build_output_path("results/signals", "signals", run_stamp)
        positions_path = build_output_path("results/positions", "positions", run_stamp)
        nav_analysis_path = build_output_path("results/equity", "nav_analysis", run_stamp)

        result["equity_df"].to_csv(equity_path, index=False)
        result["trade_df"].to_csv(trades_path, index=False)
        result["signal_df"].to_csv(signals_path, index=False)
        result["position_df"].to_csv(positions_path, index=False)
        if not result.get("nav_analysis_df", pd.DataFrame()).empty:
            result["nav_analysis_df"].to_csv(nav_analysis_path, encoding="utf-8-sig")

        log.detail(f"run_stamp = {run_stamp}")
        log.detail(f"净值 → {equity_path}")
        log.detail(f"成交 → {trades_path}")
        log.detail(f"信号 → {signals_path}")
        log.detail(f"持仓 → {positions_path}")
        if not result.get("nav_analysis_df", pd.DataFrame()).empty:
            log.detail(f"净值分析 → {nav_analysis_path}")

    with log.section("生成图表"):
        plotter = BacktestPlotter(
            save_dir="results/equity",
            dpi=300,
            figsize=(14, 7),
            file_prefix="low_price_equity",
        )
        plotter.plot_equity_curve(
            equity_df=result["equity_df"],
            title=f"低价轮动策略净值曲线（{_rebalance_chart_caption()}）",
            save=True,
            show=True,
            run_stamp=run_stamp,
        )

    log.summary()


if __name__ == "__main__":
    main()
