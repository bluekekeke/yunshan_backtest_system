# -*- coding: utf-8 -*-
"""
回测总引擎 核心功能：按时间顺序驱动所有模块，保证严格的时序逻辑，是整个系统的唯一调度中心
1.按时间周期遍历行情数据，驱动主循环（周期粒度由数据 date 列决定，可为 tick/分钟/日等）
2.每个周期更新所有持仓的最新价格
3.触发事中风控（止盈止损检查）
4.按调仓周期触发策略信号生成
5.合并所有信号，执行信号过滤
6.计算卖出回笼资金，生成订单
7.调用账户管理执行交易
8.记录日志，计算最终绩效指标
"""
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from tqdm import tqdm

from backtest_engine.core.entities import TradingSignal
from backtest_engine.log.backtest_logger import BacktestLogger
from backtest_engine.log.performance_metrics import calc_nav_analysis_table, calc_performance
from backtest_engine.module.account_manager import AccountManager
from config.settings import (
    BENCHMARK_NAME,
    REBALANCE_BARS,
    REBALANCE_INTERVAL,
    REBALANCE_MODE,
    RISK_FREE_RATE,
)
from data.data_processor import build_symbol_name_map, load_benchmark_nav, prepare_market_df
from tools.execution_utils import (
    estimate_batch_sell_proceeds,
    merge_sell_signals_for_execution,
)
from tools.run_log import RunLog


class BacktestEngine:
    def __init__(
        self,
        strategy,
        portfolio_manager,
        risk_manager,
        order_generator,
        initial_capital: float = 1000000.0
    ):
        """
        初始化回测引擎
        Args:
            strategy: 策略实例（需实现generate_signals方法）
            portfolio_manager: 组合管理实例（需实现filter_signals方法）
            risk_manager: 风控实例（需实现filter_signals和check_stop_loss_take_profit方法）
            order_generator: 订单生成器实例（需实现generate_orders方法）
            initial_capital: 初始资金，默认1000万
        """
        # 参数校验
        if initial_capital <= 0:
            raise ValueError(f"warning:初始资金必须大于0，当前值：{initial_capital}")
        
        # 核心组件
        self.strategy = strategy
        self.pm = portfolio_manager
        self.rm = risk_manager
        self.og = order_generator

        # 日志与账户
        self.logger = BacktestLogger()
        self.account = AccountManager(initial_capital, logger=self.logger)

    def run(
        self,
        df: pd.DataFrame,
        run_log: Optional[RunLog] = None,
        benchmark_nav: Optional[pd.Series] = None,
    ) -> Dict[str, Any]:
        def _info(msg: str) -> None:
            if run_log:
                run_log.detail(msg)
            else:
                print(f"  {msg}")

        df = prepare_market_df(df)
        self.logger.set_symbol_names(build_symbol_name_map(df))

        rebalance_mode = str(REBALANCE_MODE).strip().lower()
        if rebalance_mode not in ("time", "bar"):
            raise ValueError(f"REBALANCE_MODE 须为 'time' 或 'bar'，当前为 {REBALANCE_MODE!r}")
        if rebalance_mode == "bar" and int(REBALANCE_BARS) < 1:
            raise ValueError("REBALANCE_MODE='bar' 时 REBALANCE_BARS 须为 >= 1 的整数")

        period_groups = df.groupby("date", sort=True)
        n_periods = len(period_groups)
        if rebalance_mode == "bar":
            _info(f"调仓：按 bar，每 {REBALANCE_BARS} 根K线")
        else:
            _info(f"调仓：按时间，间隔 {REBALANCE_INTERVAL} 分钟")
        _info(f"周期数 {n_periods}，行情行数 {len(df)}，标的 {df['symbol'].nunique()}")

        # 时序缓存：上一周期截面（T-1 决策，T 成交）
        last_period_data: pd.DataFrame | None = None

        # 记录上一次调仓时间（仅 REBALANCE_MODE=time 使用）
        last_rebalance_time: datetime | None = None

        # 记录上一次策略调仓所在的 bar 序号（仅 REBALANCE_MODE=bar 使用；与 groupby 迭代顺序一致）
        last_rebalance_bar: int | None = None
        bar_index = -1

        t_loop = time.perf_counter()
        for current_time_raw, current_period_data in tqdm(
            period_groups,
            total=n_periods,
            desc="回测进度",
            unit="bar",
        ):
            bar_index += 1
            current_time: datetime = pd.Timestamp(current_time_raw).to_pydatetime() 

            # ==================== 每个周期都执行 ====================
            # 步骤1：更新当前周期所有标的最新价格
            for _, row in current_period_data.iterrows():
                self.account.update_price(row["symbol"], row["close"])
            account_info = self.account.get_account_info()

            # 步骤2：事中风控（单票仓位上限 + 止盈止损）
            signals: List[TradingSignal] = []
            limit_signals = self.rm.generate_position_limit_sells(
                current_time, current_period_data, account_info
            )
            signals.extend(limit_signals)
            signals.extend(
                self.rm.generate_stop_loss_take_profit_sells(
                    current_time, current_period_data, account_info
                )
            )

            # ==================== 判断是否到了调仓时间 ====================
            is_rebalance_time = False
            if rebalance_mode == "bar":
                if last_rebalance_bar is None:
                    # 与 time 模式一致：在首次成功策略调仓前，每个 bar 都允许触发（无 last_period_data 的第一根仍会跳过）
                    is_rebalance_time = True
                else:
                    is_rebalance_time = (bar_index - last_rebalance_bar) >= int(REBALANCE_BARS)
            else:
                if last_rebalance_time is None:
                    is_rebalance_time = True
                else:
                    time_diff = (current_time - last_rebalance_time).total_seconds() / 60
                    if time_diff >= REBALANCE_INTERVAL:
                        is_rebalance_time = True

            # ==================== 只有调仓时间才执行策略调仓 ====================
            if is_rebalance_time and last_period_data is not None:
                # T 周期调仓：用 T-1 截面(last_period_data) 决策 + T 截面(current_period_data) 成交
                strategy_signals = self.strategy.generate_signals(last_period_data, current_period_data, account_info)
                signals.extend(strategy_signals)
                
                if rebalance_mode == "bar":
                    last_rebalance_bar = bar_index
                else:
                    last_rebalance_time = current_time

            # ==================== 信号处理和交易执行 ====================
            if signals:
                # 记录信号日志
                for sig in signals:
                    self.logger.log_signal(
                        timestamp=sig.timestamp,
                        symbol=sig.symbol,
                        direction=sig.direction.value,
                        price=sig.price,
                        signal_type=sig.signal_type.value,
                        remark=sig.remark
                    )

                # 组合过滤 → 合并同标的卖信号 → 估算回笼 → 买入风控 → 下单（口径统一）
                signals = self.pm.filter_signals(signals)
                positions = account_info["positions"]
                exec_signals = merge_sell_signals_for_execution(signals, positions)
                sell_cash = estimate_batch_sell_proceeds(exec_signals, positions)
                exec_signals = self.rm.filter_signals(
                    exec_signals, account_info, sell_cash=sell_cash
                )

                orders = self.og.generate_orders(exec_signals, sell_cash, account_info)
                for order in orders:
                    self.account.execute_trade(
                        symbol=order.symbol,
                        direction=order.direction,
                        price=order.price,
                        quantity=order.quantity,
                        timestamp=current_time
                    )

            # 步骤3：每周期记录净值
            acc_info = self.account.get_account_info()
            self.logger.log_equity(
                trade_date=current_time,
                cash=acc_info["cash"],
                total_asset=acc_info["total_assets"],
                position_cnt=acc_info["position_count"]
            )

            self.logger.log_positions(
                timestamp=current_time,
                positions=self.account.get_full_positions_snapshot()
            )
            
            last_period_data = current_period_data.copy()

        loop_sec = time.perf_counter() - t_loop
        equity_df = self.logger.get_equity_df()
        trade_df = self.logger.get_trade_df()
        signal_df = self.logger.get_signal_df()
        if run_log:
            run_log.step(
                "遍历行情周期",
                loop_sec,
                extra=(
                    f"{n_periods} 周期，成交 {len(trade_df)} 笔，"
                    f"信号 {len(signal_df)} 条"
                ),
            )
        else:
            print(f"\n 回测主循环完成，耗时 {loop_sec:.2f}s")

        t_perf = time.perf_counter()
        if benchmark_nav is None:
            benchmark_nav = load_benchmark_nav(log=run_log)
        performance = calc_performance(
            equity_df,
            trade_df=trade_df,
            market_df=df,
            benchmark=benchmark_nav,
            nav_risk_free_rate=RISK_FREE_RATE,
        )
        nav_analysis_df = calc_nav_analysis_table(
            equity_df,
            benchmark=benchmark_nav,
            risk_free_rate=RISK_FREE_RATE,
        )
        perf_sec = time.perf_counter() - t_perf
        if run_log:
            run_log.step("绩效与净值分析", perf_sec)
        else:
            print(f"  绩效计算耗时 {perf_sec:.2f}s")

        def _emit(title: str, lines: List[str]) -> None:
            if run_log:
                run_log.info(title)
                for line in lines:
                    run_log.detail(line)
            else:
                print(f"\n{title}")
                for line in lines:
                    print(f"  {line}")

        core_lines = [
            f"总收益率：{performance['总收益率']:.2%}",
            f"年化收益率：{performance['年化收益率']:.2%}",
            f"最大回撤：{performance['最大回撤']:.2%}",
            f"夏普比率：{performance['夏普比率']:.2f}",
            f"索提诺比率：{performance.get('索提诺比率', 0):.2f}",
            f"实际交易日：{performance.get('实际交易日', 0)}",
            f"总回测分钟数：{performance.get('总回测分钟数', 0)}",
        ]
        if trade_df is not None and not trade_df.empty:
            core_lines.append(f"成交笔数：买 {performance.get('成交笔数_买', 0)} / 卖 {performance.get('成交笔数_卖', 0)}")
        _emit("核心绩效指标", core_lines)

        nav_lines: List[str] = []
        for key in (
            "净值_年化收益率",
            "净值_累计收益率",
            "净值_最大回撤",
            "净值_夏普比率",
            "净值_索提诺比率",
            "净值_卡玛比率",
            "净值_累计超额收益",
            "净值_Beta",
        ):
            if key not in performance:
                continue
            val = performance[key]
            if val is None:
                continue
            if key in ("净值_年化收益率", "净值_累计收益率", "净值_最大回撤", "净值_累计超额收益"):
                nav_lines.append(f"{key}：{val:.2%}")
            else:
                nav_lines.append(f"{key}：{val:.4f}")
        if nav_lines:
            _emit(f"净值分析（日频，基准={BENCHMARK_NAME}）", nav_lines)

        return {
            "equity_df": equity_df,
            "trade_df": trade_df,
            "signal_df": signal_df,
            "position_df": self.logger.get_position_df(),
            "performance": performance,
            "nav_analysis_df": nav_analysis_df,
            "benchmark_nav": benchmark_nav,
            "benchmark_name": BENCHMARK_NAME,
        }