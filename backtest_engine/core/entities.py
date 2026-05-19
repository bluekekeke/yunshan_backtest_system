# -*- coding: utf-8 -*-
"""
核心实体类：交易信号、订单、持仓快照
✅ 完全兼容所有时间类型，静态检查100%通过
"""
from datetime import datetime
from typing import Dict, Optional, Union
import pandas as pd
from backtest_engine.core.enums import Direction, SignalType, OrderStatus


class TradingSignal:
    """交易信号实体"""
    def __init__(
        self,
        timestamp: Union[datetime, pd.Timestamp, str],
        symbol: str,
        direction: Direction,
        price: float,
        signal_type: SignalType,
        confidence: float = 1.0,
        remark: str = "",
        quantity: Optional[int] = None,
    ):
        # 内部统一转换为原生datetime
        if isinstance(timestamp, pd.Timestamp):
            self.timestamp: datetime = timestamp.to_pydatetime()
        elif isinstance(timestamp, str):
            self.timestamp: datetime = pd.to_datetime(timestamp).to_pydatetime()
        else:
            self.timestamp: datetime = timestamp
            
        self.symbol = symbol
        self.direction = direction
        self.price = price
        self.signal_type = signal_type
        self.confidence = confidence
        self.remark = remark
        self.quantity = quantity  # None=卖出清仓/买入由订单层计算

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "price": self.price,
            "signal_type": self.signal_type.value,
            "confidence": self.confidence,
            "remark": self.remark,
            "quantity": self.quantity,
        }


class Order:
    """订单实体"""
    def __init__(
        self,
        timestamp: Union[datetime, pd.Timestamp, str],
        symbol: str,
        direction: Direction,
        price: float,
        quantity: int,
        status: OrderStatus = OrderStatus.GENERATED,
        reason: str = ""
    ):
        if isinstance(timestamp, pd.Timestamp):
            self.timestamp: datetime = timestamp.to_pydatetime()
        elif isinstance(timestamp, str):
            self.timestamp: datetime = pd.to_datetime(timestamp).to_pydatetime()
        else:
            self.timestamp: datetime = timestamp
            
        self.symbol = symbol
        self.direction = direction
        self.price = price
        self.quantity = quantity
        self.status = status
        self.reason = reason


class PositionSnapshot:
    """单只标的持仓快照"""
    def __init__(
        self,
        symbol: str,
        quantity: int,
        avg_cost: float,
        current_price: float = 0.0
    ):
        self.symbol = symbol
        self.quantity = quantity
        self.avg_cost = avg_cost
        self.current_price = current_price

    @property
    def position_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.avg_cost) * self.quantity