# -*- coding: utf-8 -*-
"""
订单生成器 - 等额分仓版（区分建仓/调仓，复用仓位计算）
"""
from typing import List
from backtest_engine.core.entities import TradingSignal, Order
from backtest_engine.core.enums import Direction
from config.settings import COMMISSION_RATE, MAX_SINGLE_POS_RATIO
from backtest_engine.module.portfolio_manager import PortfolioManager
from tools.calc_utils import cap_buy_quantity
from tools.execution_utils import resolve_sell_quantity

class OrderGenerator:
    def __init__(self, portfolio_manager: PortfolioManager):
        self.pm = portfolio_manager  # 持有组合管理器，调用仓位计算函数

    def generate_orders(self, signals: List[TradingSignal], sell_cash: float, account_info: dict) -> List[Order]:
        orders = []
        cash = account_info["cash"]
        positions = account_info["positions"]
        
        # 拆分买卖信号
        buy_signals = [s for s in signals if s.direction == Direction.BUY]
        sell_signals = [s for s in signals if s.direction == Direction.SELL]

        # ===================== 1. 先处理卖出（严格先卖后买） =====================
        for signal in sell_signals:
            pos = positions.get(signal.symbol)
            if pos and pos.quantity > 0:
                sell_qty = resolve_sell_quantity(signal, int(pos.quantity))
                if sell_qty <= 0:
                    continue
                orders.append(Order(
                    symbol=signal.symbol,
                    direction=signal.direction,
                    price=signal.price,
                    quantity=sell_qty,
                    timestamp=signal.timestamp
                ))

        # ===================== 2. 后处理买入（先卖后买：可用现金 + 本批卖出回笼） =====================
        if buy_signals:
            num_buy = len(buy_signals)
            # 卖出按市值估算，扣除预估手续费后与当前现金合并为可部署资金
            sell_net = sell_cash * (1.0 - COMMISSION_RATE)
            deployable_cash = cash + sell_net

            for signal in buy_signals:
                price = signal.price
                if price <= 0:
                    continue

                qty = self.pm.calculate_position_size(
                    deployable_cash=deployable_cash,
                    buy_count=num_buy,
                    signal_price=price,
                )
                existing = positions.get(signal.symbol)
                existing_qty = existing.quantity if existing else 0
                qty = cap_buy_quantity(
                    qty,
                    price,
                    account_info["total_assets"],
                    MAX_SINGLE_POS_RATIO,
                    existing_qty,
                )

                if qty > 0:
                    orders.append(Order(
                        symbol=signal.symbol,
                        direction=signal.direction,
                        price=price,
                        quantity=qty,
                        timestamp=signal.timestamp
                    ))

        return orders