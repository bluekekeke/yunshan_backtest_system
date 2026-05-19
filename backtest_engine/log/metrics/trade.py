# -*- coding: utf-8 -*-
"""成交侧：FIFO 已实现盈亏、换手、笔数与胜率统计。"""
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .equity import prepare_equity_df


def fifo_realized_pnls_gross(
    trade_df: pd.DataFrame,
    commission_rate: float = 0.0,
) -> List[float]:
    """
    按时间顺序 FIFO 配对每笔卖出相对已买成本的**毛已实现盈亏**（可近似扣双边费率）。

    - 买入成本按 (1+commission_rate)*price 计每单位成本；
    - 卖出收入按 (1-commission_rate)*price 计每单位收入；
    """
    if trade_df is None or trade_df.empty:
        return []
    need = {"date", "symbol", "direction", "quantity", "price"}
    if not need.issubset(trade_df.columns):
        raise ValueError(f"trade_df 需包含列: {need}")
    df = trade_df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    stacks: Dict[str, List[List[float]]] = {}
    pnls: List[float] = []

    for _, row in df.iterrows():
        sym = str(row["symbol"])
        direction = str(row["direction"]).upper()
        qty = int(row["quantity"])
        price = float(row["price"])
        if qty <= 0:
            continue
        stacks.setdefault(sym, [])

        if direction == "BUY":
            unit_cost = price * (1.0 + commission_rate)
            stacks[sym].append([float(qty), unit_cost])
        elif direction == "SELL":
            unit_px = price * (1.0 - commission_rate)
            sell_left = qty
            while sell_left > 0 and stacks[sym]:
                lot_qty, lot_cost = stacks[sym][0]
                take = min(sell_left, int(lot_qty))
                pnls.append((unit_px - lot_cost) * take)
                lot_qty -= take
                sell_left -= take
                if lot_qty <= 0:
                    stacks[sym].pop(0)
                else:
                    stacks[sym][0][0] = lot_qty
        else:
            continue

    return pnls


def calendar_years_span(dates: pd.Series) -> float:
    """首末时间戳之间的日历年数（用于换手年化分母）。"""
    if dates.empty or len(dates) < 2:
        return 0.0
    start = pd.Timestamp(dates.iloc[0])
    end = pd.Timestamp(dates.iloc[-1])
    sec = (end - start).total_seconds()
    if sec <= 0:
        return 0.0
    return sec / (365.25 * 24 * 3600)


def calc_turnover_ratio(
    trade_df: pd.DataFrame,
    equity_df: pd.DataFrame,
    trade_value_column: str = "trade_value",
    nav_column: str = "total_asset",
) -> float:
    """
    近似年化换手：区间内 sum(|trade_value|) / mean(净值)，再按日历跨度年化。
    """
    if trade_df is None or trade_df.empty or equity_df is None or equity_df.empty:
        return 0.0
    if trade_value_column not in trade_df.columns:
        return 0.0
    nav = prepare_equity_df(equity_df)[nav_column].astype(float)
    mean_nav = float(nav.mean())
    if mean_nav <= 0:
        return 0.0
    turnover = float(trade_df[trade_value_column].abs().sum() / mean_nav)
    df_e = prepare_equity_df(equity_df)
    years = calendar_years_span(df_e["date"])
    if years <= 0:
        years = 1.0
    return float(turnover / years)


def calc_trade_win_stats(
    trade_df: pd.DataFrame,
    commission_rate: float = 0.0,
) -> Dict[str, Any]:
    """基于 FIFO 已实现盈亏统计：笔数、胜率、盈亏比、均值等。"""
    pnls = fifo_realized_pnls_gross(trade_df, commission_rate=commission_rate)
    if not pnls:
        return {
            "round_trip_count": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "gross_profit_sum": 0.0,
            "gross_loss_sum": 0.0,
        }
    arr = np.array(pnls, dtype=float)
    wins = arr[arr > 0]
    losses = arr[arr < 0]
    gross_profit = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(abs(losses.sum())) if len(losses) else 0.0
    profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else (np.inf if gross_profit > 0 else 0.0)
    if np.isinf(profit_factor):
        profit_factor = 999999.0
    return {
        "round_trip_count": int(len(pnls)),
        "win_rate": float((arr > 0).mean()),
        "profit_factor": float(profit_factor),
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
        "gross_profit_sum": gross_profit,
        "gross_loss_sum": gross_loss,
    }


def calc_trade_counts(trade_df: pd.DataFrame) -> Dict[str, int]:
    """买卖笔数（按成交记录条数）。"""
    if trade_df is None or trade_df.empty or "direction" not in trade_df.columns:
        return {"buy_count": 0, "sell_count": 0, "trade_rows": 0}
    d = trade_df["direction"].astype(str).str.upper()
    return {
        "buy_count": int((d == "BUY").sum()),
        "sell_count": int((d == "SELL").sum()),
        "trade_rows": int(len(trade_df)),
    }
