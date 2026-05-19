# -*- coding: utf-8 -*-
"""
账户管理器：负责现金、持仓、交易、扣费、资产计算 + 日志对接

"""
from typing import Dict, Optional, Union
from datetime import datetime
import pandas as pd  # 导入Timestamp类型用于注解
from typing import List, Dict, Any, Optional, Union
from backtest_engine.core.enums import Direction
from backtest_engine.core.entities import PositionSnapshot
from config.settings import COMMISSION_RATE, MIN_TRADE_QTY
from tools.calc_utils import round_to_min_trade_qty


class AccountManager:
    def __init__(self, initial_capital: float, logger=None):
        # 初始资金
        self.initial_capital = initial_capital
        # 可用现金
        self.cash = initial_capital
        # 持仓字典：key = symbol, value = PositionSnapshot
        self.positions: Dict[str, PositionSnapshot] = {}
        # 日志器
        self.logger = logger

    @property
    def total_assets(self) -> float:
        """
        总资产 = 现金 + 所有持仓市值
        """
        position_value = sum(pos.position_value for pos in self.positions.values())
        return self.cash + position_value

    def update_price(self, symbol: str, price: float):
        """
        更新股票最新价格（用于每日计算持仓市值）
        """
        if symbol in self.positions:
            self.positions[symbol].current_price = price

    def execute_trade(
        self,
        symbol: str,
        direction: Direction,
        price: float,
        quantity: int,
        timestamp: Optional[Union[datetime, pd.Timestamp]] = None
    ) -> bool:
        """
        执行交易：买/卖
        自动扣手续费、更新现金、更新持仓、记录交易日志
        """
        if timestamp is not None:
            if isinstance(timestamp, pd.Timestamp):
                timestamp = timestamp.to_pydatetime()
            # 额外保护：如果是字符串类型也尝试转换（兜底）
            elif isinstance(timestamp, str):
                try:
                    timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    timestamp = None

        # 数量取整为最小交易单位的整数倍
        quantity = round_to_min_trade_qty(quantity)
        if quantity <= 0:
            return False

        # 交易金额
        trade_amount = price * quantity
        # 手续费
        commission = trade_amount * COMMISSION_RATE

        # ==================== 买入逻辑 ====================
        if direction == Direction.BUY:
            total_cost = trade_amount + commission
            # 钱不够 → 不买
            if self.cash < total_cost:
                return False
            # 扣钱
            self.cash -= total_cost
            # 更新持仓
            if symbol in self.positions:
                pos = self.positions[symbol]
                new_shares = pos.quantity + quantity
                new_cost = (pos.avg_cost * pos.quantity + price * quantity) / new_shares
                pos.quantity = new_shares
                pos.avg_cost = new_cost
                pos.current_price = price
            else:
                self.positions[symbol] = PositionSnapshot(
                    symbol=symbol, quantity=quantity, avg_cost=price, current_price=price
                )

        # ==================== 卖出逻辑 ====================
        elif direction == Direction.SELL:
            if symbol not in self.positions or self.positions[symbol].quantity < quantity:
                return False
            pos = self.positions[symbol]
            total_receive = trade_amount - commission
            self.cash += total_receive
            pos.quantity -= quantity
            pos.current_price = price
            if pos.quantity <= 0:
                del self.positions[symbol]

        # ==================== 记录交易日志 ====================
        if self.logger and timestamp:
            self.logger.log_trade(
                trade_date=timestamp,
                symbol=symbol,
                direction=direction.value,
                price=price,
                quantity=quantity,
                trade_value=trade_amount,
                comm=commission,
            )

        return True

    def get_account_info(self) -> dict:
        """
        获取账户汇总信息
        """
        return {
            "initial_capital": self.initial_capital,
            "cash": self.cash,
            "total_assets": self.total_assets,
            "position_count": len(self.positions),
            "positions": self.positions  # 返回完整持仓，给策略/风控使用
        }
    
    def get_full_positions_snapshot(self) -> List[Dict[str, Any]]:
        """
        获取当前所有持仓的完整快照
        返回：[{symbol, quantity, avg_cost, current_price, position_value, unrealized_pnl}, ...]
        """
        snapshot = []
        for symbol, pos in self.positions.items():
            snapshot.append({
                "symbol": symbol,
                "quantity": pos.quantity,
                "avg_cost": round(pos.avg_cost, 4),
                "current_price": round(pos.current_price, 4),
                "position_value": round(pos.position_value, 2),
                "unrealized_pnl": round(pos.unrealized_pnl, 2)
            })
        return snapshot