# -*- coding: utf-8 -*-
"""
全局枚举类：统一魔法字符串，避免硬编码
"""
from enum import Enum

class Direction(Enum):
    """交易方向"""
    BUY = "BUY"
    SELL = "SELL"

class SignalType(Enum):
    """信号类型"""
    # 策略信号
    STRATEGY_BUY = "STRATEGY_BUY"
    STRATEGY_SELL = "STRATEGY_SELL"
    # 风控信号
    RISK_STOP_LOSS = "RISK_STOP_LOSS"
    RISK_TAKE_PROFIT = "RISK_TAKE_PROFIT"
    RISK_POS_LIMIT = "RISK_POS_LIMIT"

class OrderStatus(Enum):
    """订单状态"""
    GENERATED = "GENERATED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"

