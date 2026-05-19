# -*- coding: utf-8 -*-
"""
策略基类：所有策略必须继承并实现 generate_signals
"""
from abc import ABC, abstractmethod
from typing import List
import pandas as pd
from backtest_engine.core.entities import TradingSignal

class BaseStrategy(ABC):
    def __init__(self):
        self.name = "BaseStrategy"

    @abstractmethod
    def generate_signals(self, daily_data: pd.DataFrame, account_info: dict) -> List[TradingSignal]:
        """
        每日数据 → 生成交易信号
        :param daily_data: 单日全市场数据
        :param account_info: 账户信息
        :return: 信号列表
        """
        pass
