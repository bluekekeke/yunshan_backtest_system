# -*- coding: utf-8 -*-
"""
低价轮动策略（按行情周期驱动，周期粒度由数据 date 列决定）
核心逻辑：
1. 输入：上一周期全市场截面数据
2. 按收盘价升序排序，选出价格最低的TOP_N只
3. 调仓规则：卖出所有不在目标池的持仓，买入所有在目标池且未持仓的
4. 时序：T-1 周期截面决策 → T 周期截面成交
"""
import pandas as pd
from typing import List
from config.settings import TOP_N
from backtest_engine.core.enums import Direction, SignalType
from backtest_engine.core.entities import TradingSignal
from strategy.strategy_base import BaseStrategy


class LowPriceMinuteStrategy(BaseStrategy):
    def __init__(self, top_n: int = TOP_N):
        super().__init__()
        self.name = "LowPrice_Minute_Rotation"
        self.top_n = top_n  # 每次持有最便宜的N只可转债

    def generate_signals(
        self,
        last_period_data: pd.DataFrame,
        current_period_data: pd.DataFrame,
        account_info: dict,
    ) -> List[TradingSignal]:
        """
        每个调仓周期被回测引擎调用一次。
        Args:
            last_period_data: 上一周期全市场截面（决策选股用）
            current_period_data: 当前周期全市场截面（真实成交用）
            account_info: 当前账户信息
        """
        signals = []
        if last_period_data.empty or current_period_data.empty:
            return signals

        # ==================== 步骤1：数据清洗 + 低价排序 ====================
        df_clean = last_period_data[last_period_data["close"] > 0].drop_duplicates("symbol")
        if len(df_clean) < self.top_n:
            return signals  # 数据不足时不调仓

        # 按收盘价升序排序，选出最便宜的TOP_N只
        df_sorted = df_clean.sort_values("close", ascending=True)
        target_symbols = set(df_sorted.head(self.top_n)["symbol"].tolist())

        # ==================== 步骤2：获取当前持仓 ====================
        positions = account_info.get("positions", {})
        holding_symbols = set(positions.keys())

        # ==================== 步骤3：生成卖出信号（不在目标池的全部卖出） ====================
        sell_symbols = holding_symbols - target_symbols
        for symbol in sell_symbols:
            price_row = last_period_data[last_period_data["symbol"] == symbol]
            if price_row.empty:
                continue

            current_price_row = current_period_data[current_period_data["symbol"] == symbol]
            if current_price_row.empty:
                continue
            execution_price = current_price_row["close"].iloc[0]

            signals.append(TradingSignal(
                timestamp=current_period_data["date"].iloc[0],
                symbol=symbol,
                direction=Direction.SELL,
                price=execution_price,
                signal_type=SignalType.STRATEGY_SELL,
                remark="调出目标池"
            ))

        # ==================== 步骤4：生成买入信号 ====================
        buy_symbols = target_symbols - holding_symbols
        for symbol in buy_symbols:
            price_row = last_period_data[last_period_data["symbol"] == symbol]
            if price_row.empty:
                continue

            current_price_row = current_period_data[current_period_data["symbol"] == symbol]
            if current_price_row.empty:
                continue
            execution_price = current_price_row["close"].iloc[0]

            signals.append(TradingSignal(
                timestamp=current_period_data["date"].iloc[0],
                symbol=symbol,
                direction=Direction.BUY,
                price=execution_price,
                signal_type=SignalType.STRATEGY_BUY,
                remark="调入目标池"
            ))

        return signals