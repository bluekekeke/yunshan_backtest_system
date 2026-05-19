# -*- coding: utf-8 -*-
"""
回测日志系统：记录净值、每笔交易、信号、持仓
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import pandas as pd


class BacktestLogger:
    def __init__(self, symbol_names: Optional[Dict[str, str]] = None):
        self.symbol_names: Dict[str, str] = dict[str, str](symbol_names or {})
        self.equity_records = []
        self.trade_records = []
        self.signal_records = []
        self.position_log = []

    def set_symbol_names(self, symbol_names: Optional[Dict[str, str]]) -> None:
        self.symbol_names = dict(symbol_names or {})

    def _stock_name(self, symbol: str) -> str:
        return self.symbol_names.get(str(symbol), "")

    def log_equity(
        self,
        trade_date: Union[datetime, pd.Timestamp, str], 
        cash: float,
        total_asset: float,
        position_cnt: int
    ):
        """记录每日账户净值"""
        trade_date = self._convert_to_datetime(trade_date)
        
        self.equity_records.append({
            "date": trade_date,
            "cash": round(cash, 2),
            "total_asset": round(total_asset, 2),
            "position_count": position_cnt
        })

    def log_trade(
        self,
        trade_date: Union[datetime, pd.Timestamp, str],  # 修改1：支持3种时间类型
        symbol: str,
        direction: str,
        price: float,
        quantity: int,
        trade_value: float,
        comm: float,
    ):
        """记录每一笔成交"""
        trade_date = self._convert_to_datetime(trade_date)
        
        self.trade_records.append({
            "date": trade_date,
            "symbol": symbol,
            "StockName": self._stock_name(symbol),
            "direction": direction,
            "price": round(price, 2),
            "quantity": quantity,
            "trade_value": round(trade_value, 2),
            "comm": round(comm, 2),
        })

    def log_signal(
        self,
        timestamp: Union[datetime, pd.Timestamp, str], 
        symbol: str,
        direction: str,
        price: float,
        signal_type: str,
        remark: str
    ):
        """记录每一个交易信号"""
        timestamp = self._convert_to_datetime(timestamp)
        
        self.signal_records.append({
            "timestamp": timestamp,
            "symbol": symbol,
            "StockName": self._stock_name(symbol),
            "direction": direction,
            "price": round(price, 2),
            "signal_type": signal_type,
            "remark": remark,
        })

    def get_equity_df(self) -> pd.DataFrame:
        """转为净值DataFrame"""
        df = pd.DataFrame(self.equity_records)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
        return df

    def get_trade_df(self) -> pd.DataFrame:
        """转为交易记录DataFrame"""
        df = pd.DataFrame(self.trade_records)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
        return df

    def get_signal_df(self) -> pd.DataFrame:
        """转为信号记录DataFrame"""
        df = pd.DataFrame(self.signal_records)
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    
    def log_positions(
        self, 
        timestamp: Union[datetime, pd.Timestamp, str], 
        positions: List[Dict[str, Any]]
        ):
        """记录某一时刻的所有持仓"""
        timestamp = self._convert_to_datetime(timestamp)
        for pos in positions:
            symbol = pos.get("symbol", "")
            self.position_log.append({
                "timestamp": timestamp,
                "symbol": symbol,
                "StockName": self._stock_name(symbol),
                **{k: v for k, v in pos.items() if k != "symbol"},
            })

    def get_position_df(self) -> pd.DataFrame:
        """获取所有时刻的持仓数据DataFrame"""
        df = pd.DataFrame(self.position_log)
        if not df.empty:
            df = df.sort_values(["timestamp", "symbol"]).reset_index(drop=True)
        return df

    def _convert_to_datetime(self, time_val: Union[datetime, pd.Timestamp, str]) -> datetime:
        """
        统一将任意时间类型转换为Python原生datetime
        支持：datetime / pandas.Timestamp / 字符串（"%Y-%m-%d %H:%M:%S"格式）
        """
        if isinstance(time_val, pd.Timestamp):
            return time_val.to_pydatetime()
        elif isinstance(time_val, str):
            try:
                return datetime.strptime(time_val, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                # 兼容不带秒的格式
                try:
                    return datetime.strptime(time_val, "%Y-%m-%d %H:%M")
                except ValueError:
                    # 极端情况返回当前时间兜底，避免崩溃
                    return datetime.now()
        return time_val