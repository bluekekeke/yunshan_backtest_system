# -*- coding: utf-8 -*-
"""
组合管理模块

"""
from typing import List, Optional
from config.settings import TOP_N, MIN_TRADE_QTY
from backtest_engine.core.entities import TradingSignal


class PortfolioManager:
    def __init__(self, max_positions: int = TOP_N):
        self.max_positions = max_positions
        self.black_list = set()  # 永久黑名单（如退市、停牌股票）

    def add_to_blacklist(self, symbol: str):
        self.black_list.add(symbol)

    def remove_from_blacklist(self, symbol: str):
        self.black_list.discard(symbol)

    def filter_signals(self, signals: List[TradingSignal]) -> List[TradingSignal]:
        """
        分钟级调仓信号过滤：仅剔除黑名单标的
        """
        if not signals:
            return []
        
        # 仅过滤黑名单，其他全部放行
        filtered_signals = [s for s in signals if s.symbol not in self.black_list]
        return filtered_signals

    def calculate_position_size(
        self,
        deployable_cash: float,
        buy_count: int,
        signal_price: float,
        min_qty: int = MIN_TRADE_QTY,
    ) -> int:
        """
        等额分仓：将可部署资金平均分配到本次买入标的。
        deployable_cash = 账户可用现金 + 本批卖出预计回笼（扣费后）。
        """
        if buy_count <= 0 or signal_price <= 0 or deployable_cash <= 0:
            return 0
        per_stock_cash = deployable_cash / buy_count
        qty = int(per_stock_cash // signal_price)
        return (qty // min_qty) * min_qty

    def calculate_position_size_initial(
        self,
        total_cash: float,
        signal_price: float,
        min_qty: int = MIN_TRADE_QTY,
        buy_count: Optional[int] = None,
    ) -> int:
        """首次建仓：默认按 max_positions 均分；传入 buy_count 时按实际买入只数均分。"""
        slots = buy_count if buy_count and buy_count > 0 else self.max_positions
        return self.calculate_position_size(total_cash, slots, signal_price, min_qty)