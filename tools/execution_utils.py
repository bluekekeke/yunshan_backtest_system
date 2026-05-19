# -*- coding: utf-8 -*-
"""
执行层工具：卖出数量解析、同标的卖信号合并、批次卖出回笼估算。

订单生成与风控资金预估共用此处逻辑，避免重复计入或卖超。
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from backtest_engine.core.entities import TradingSignal
from backtest_engine.core.enums import Direction, SignalType

# 数值越小优先级越高（合并时保留该类型的元数据）
SELL_SIGNAL_PRIORITY: Dict[SignalType, int] = {
    SignalType.RISK_STOP_LOSS: 0,
    SignalType.RISK_TAKE_PROFIT: 1,
    SignalType.RISK_POS_LIMIT: 2,
    SignalType.STRATEGY_SELL: 3,
}


def resolve_sell_quantity(signal: TradingSignal, position_qty: int) -> int:
    """将信号转为计划卖出股数（不超过当前持仓）。"""
    if position_qty <= 0:
        return 0
    if signal.quantity is not None and signal.quantity > 0:
        return min(int(signal.quantity), position_qty)
    return position_qty


def _merge_sell_remarks(sym_sells: List[TradingSignal]) -> str:
    """合并同标的多条卖信号的 remark（去重，按风控优先级顺序排列）。"""
    parts: List[str] = []
    for sig in sorted(
        sym_sells,
        key=lambda s: SELL_SIGNAL_PRIORITY.get(s.signal_type, 999),
    ):
        text = (sig.remark or "").strip()
        if text and text not in parts:
            parts.append(text)
    return " | ".join(parts)


def _signal_with_quantity(
    signal: TradingSignal,
    quantity: int,
    remark: str | None = None,
) -> TradingSignal:
    return TradingSignal(
        timestamp=signal.timestamp,
        symbol=signal.symbol,
        direction=signal.direction,
        price=signal.price,
        signal_type=signal.signal_type,
        confidence=signal.confidence,
        remark=remark if remark is not None else signal.remark,
        quantity=quantity,
    )


def merge_sell_signals_for_execution(
    signals: List[TradingSignal],
    positions: Dict,
) -> List[TradingSignal]:
    """
    合并同一标的、同一批次的多条卖出信号：
    - 计划卖出量 = 各条 resolve 后的最大值（再 cap 持仓）
    - signal_type = 优先级最高的一条（止损 > 止盈 > 仓位超限 > 策略）
    - remark = 各条信号真实 remark 去重后用「 | 」拼接
    买入信号原样保留。
    """
    buys = [s for s in signals if s.direction == Direction.BUY]
    sells_by_symbol: Dict[str, List[TradingSignal]] = defaultdict(list)
    for sig in signals:
        if sig.direction == Direction.SELL:
            sells_by_symbol[sig.symbol].append(sig)

    merged_sells: List[TradingSignal] = []
    for symbol, sym_sells in sells_by_symbol.items():
        pos = positions.get(symbol)
        pos_qty = int(pos.quantity) if pos and pos.quantity > 0 else 0
        if pos_qty <= 0:
            continue

        merged_qty = max(resolve_sell_quantity(s, pos_qty) for s in sym_sells)
        merged_qty = min(merged_qty, pos_qty)
        if merged_qty <= 0:
            continue

        best = min(
            sym_sells,
            key=lambda s: SELL_SIGNAL_PRIORITY.get(s.signal_type, 999),
        )
        merged_sells.append(
            _signal_with_quantity(best, merged_qty, remark=_merge_sell_remarks(sym_sells))
        )

    return merged_sells + buys


def estimate_batch_sell_proceeds(
    signals: List[TradingSignal],
    positions: Dict,
) -> float:
    """
    估算本批卖出回笼金额（按 signal.price × 计划卖出股数）。
    应对已合并后的信号列表调用；若传入未合并列表，请先 merge_sell_signals_for_execution。
    """
    total = 0.0
    for sig in signals:
        if sig.direction != Direction.SELL:
            continue
        pos = positions.get(sig.symbol)
        if not pos or pos.quantity <= 0:
            continue
        qty = resolve_sell_quantity(sig, int(pos.quantity))
        if qty <= 0 or sig.price <= 0:
            continue
        total += qty * float(sig.price)
    return total
