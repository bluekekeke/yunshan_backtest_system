# -*- coding: utf-8 -*-
"""
风控模块：
1. 保留单票最大仓位限制和现金充足性检查
2. 止盈止损逻辑
"""
from typing import Dict, List, Optional
import pandas as pd
from backtest_engine.core.entities import TradingSignal
from backtest_engine.core.enums import Direction, SignalType
from tools.calc_utils import max_shares_for_position_limit, trim_sell_quantity_for_limit
from tools.execution_utils import (
    estimate_batch_sell_proceeds,
    merge_sell_signals_for_execution,
)
from config.settings import (
    MAX_SINGLE_POS_RATIO,
    TAKE_PROFIT_RATIO,
    STOP_LOSS_RATIO,
    MIN_TRADE_QTY,
    COMMISSION_RATE,
)


class RiskManager:
    def __init__(self):
        self.max_single_ratio = MAX_SINGLE_POS_RATIO  # 单票最大仓位（总资产占比）
        self.tp_ratio = TAKE_PROFIT_RATIO  # 止盈比例
        self.sl_ratio = STOP_LOSS_RATIO  # 止损比例

    @staticmethod
    def estimate_batch_sell_cash(signals: List[TradingSignal], positions: Dict) -> float:
        """本批卖出预估回笼（合并同标的卖信号后，按 plan_qty × price 估算）。"""
        exec_signals = merge_sell_signals_for_execution(signals, positions)
        return estimate_batch_sell_proceeds(exec_signals, positions)

    def filter_signals(
        self,
        signals: List[TradingSignal],
        account_info: dict,
        sell_cash: Optional[float] = None,
    ) -> List[TradingSignal]:
        """总风控入口：仅过滤买入信号，卖出信号全部放行。"""
        if not signals:
            return []

        positions = account_info["positions"]
        if sell_cash is None:
            sell_cash = self.estimate_batch_sell_cash(signals, positions)
        # 先卖后买：可用资金 = 当前现金 + 本批卖出预估回笼（扣费）
        available_cash = account_info["cash"] + sell_cash * (1.0 - COMMISSION_RATE)

        filtered = []
        for sig in signals:
            if sig.direction == Direction.BUY:
                if self._check_buy_risk(sig, account_info, available_cash):
                    filtered.append(sig)
            else:
                filtered.append(sig)

        return filtered

    def _check_buy_risk(
        self,
        signal: TradingSignal,
        account_info: dict,
        available_cash: float,
    ) -> bool:
        """买入风险检查：现金充足，且买入后单票持仓不超过 MAX_SINGLE_POS_RATIO。"""
        signal_price = signal.price
        if signal_price <= 0:
            return False

        total_assets = account_info["total_assets"]
        positions = account_info["positions"]
        existing_qty = (
            positions[signal.symbol].quantity if signal.symbol in positions else 0
        )

        max_qty = max_shares_for_position_limit(
            total_assets, self.max_single_ratio, signal_price, MIN_TRADE_QTY
        )
        if existing_qty >= max_qty:
            return False
        if existing_qty + MIN_TRADE_QTY > max_qty:
            return False

        min_trade_cost = signal_price * MIN_TRADE_QTY * 1.0002
        if available_cash < min_trade_cost:
            return False

        return True

    def generate_position_limit_sells(
        self,
        current_time,
        current_period_data: pd.DataFrame,
        account_info: dict,
    ) -> List[TradingSignal]:
        """持仓过程中市值超过单票上限时，减持至阈值内（否则清仓）。"""
        signals: List[TradingSignal] = []
        total_assets = account_info["total_assets"]
        if total_assets <= 0:
            return signals

        for symbol, pos in account_info["positions"].items():
            if pos.quantity <= 0:
                continue
            price_row = current_period_data[current_period_data["symbol"] == symbol]
            if price_row.empty:
                continue
            current_price = float(price_row["close"].iloc[0])
            if current_price <= 0:
                continue

            sell_qty = trim_sell_quantity_for_limit(
                pos.quantity,
                current_price,
                total_assets,
                self.max_single_ratio,
                MIN_TRADE_QTY,
            )
            if sell_qty <= 0:
                continue

            ratio = pos.position_value / total_assets
            signals.append(
                TradingSignal(
                    timestamp=current_time,
                    symbol=symbol,
                    direction=Direction.SELL,
                    price=current_price,
                    signal_type=SignalType.RISK_POS_LIMIT,
                    quantity=sell_qty,
                    remark=(
                        f"单票仓位超限减持(市值占比{ratio:.2%}"
                        f">上限{self.max_single_ratio:.2%})"
                    ),
                )
            )
        return signals

    def check_stop_loss_take_profit(self, symbol, pos, current_price):
        """检查单只持仓是否触发止盈止损"""
        cost = pos.avg_cost
        if cost <= 0:
            return None, None

        pnl_ratio = (current_price - cost) / cost
        if pnl_ratio >= self.tp_ratio:
            return "SELL", "止盈"
        if pnl_ratio <= -self.sl_ratio:
            return "SELL", "止损"

        return None, None

    def generate_stop_loss_take_profit_sells(
        self,
        current_time,
        current_period_data: pd.DataFrame,
        account_info: dict,
    ) -> List[TradingSignal]:
        """持仓过程中按当前周期价格检查止盈止损，生成卖出信号。"""
        signals: List[TradingSignal] = []
        for symbol, pos in account_info["positions"].items():
            if pos.quantity <= 0:
                continue
            price_row = current_period_data[current_period_data["symbol"] == symbol]
            if price_row.empty:
                continue
            current_price = float(price_row["close"].iloc[0])
            if current_price <= 0:
                continue

            direction, reason = self.check_stop_loss_take_profit(symbol, pos, current_price)
            if direction != "SELL":
                continue

            signal_type = (
                SignalType.RISK_STOP_LOSS if reason == "止损" else SignalType.RISK_TAKE_PROFIT
            )
            signals.append(
                TradingSignal(
                    timestamp=current_time,
                    symbol=symbol,
                    direction=Direction.SELL,
                    price=current_price,
                    signal_type=signal_type,
                    remark=reason,
                )
            )
        return signals