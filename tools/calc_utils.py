# -*- coding: utf-8 -*-
"""
数值计算、仓位取整、绩效指标工具
"""
import pandas as pd
import numpy as np
from config.settings import MIN_TRADE_QTY


def round_to_min_trade_qty(quantity: int, min_qty: int = MIN_TRADE_QTY) -> int:
    """数量向下取整到最小交易单位整数倍"""
    if quantity <= 0:
        return 0
    return (quantity // min_qty) * min_qty


def max_shares_for_position_limit(
    total_assets: float,
    max_ratio: float,
    price: float,
    min_qty: int = MIN_TRADE_QTY,
) -> int:
    """单票市值上限对应的最大持仓股数（最小交易单位整数倍）。"""
    if total_assets <= 0 or price <= 0 or max_ratio <= 0:
        return 0
    max_value = total_assets * max_ratio
    return round_to_min_trade_qty(int(max_value // price), min_qty)


def cap_buy_quantity(
    qty: int,
    price: float,
    total_assets: float,
    max_ratio: float,
    existing_qty: int = 0,
    min_qty: int = MIN_TRADE_QTY,
) -> int:
    """将买入数量限制在「单票总持仓 ≤ 总资产×max_ratio」以内。"""
    cap_total = max_shares_for_position_limit(total_assets, max_ratio, price, min_qty)
    allowed = max(0, cap_total - existing_qty)
    return round_to_min_trade_qty(min(qty, allowed), min_qty)


def trim_sell_quantity_for_limit(
    current_qty: int,
    price: float,
    total_assets: float,
    max_ratio: float,
    min_qty: int = MIN_TRADE_QTY,
) -> int:
    """持仓市值超限时，返回应卖出的股数；无法减持到阈值内则清仓。"""
    if current_qty <= 0 or price <= 0 or total_assets <= 0:
        return 0
    max_value = total_assets * max_ratio
    if current_qty * price <= max_value:
        return 0
    target_qty = max_shares_for_position_limit(total_assets, max_ratio, price, min_qty)
    sell_qty = current_qty - target_qty
    if sell_qty < min_qty:
        return current_qty
    return round_to_min_trade_qty(sell_qty, min_qty)


def calc_max_drawdown(equity_series: pd.Series) -> float:
    """计算最大回撤"""
    roll_max = equity_series.cummax()
    drawdown = (equity_series - roll_max) / roll_max
    return drawdown.min()


def calc_sharpe_ratio_day(return_series: pd.Series, annual_days: int = 252, risk_free: float = 0.02) -> float:
    """计算夏普比率"""
    if len(return_series) < 2:
        return 0.0
    daily_mean = return_series.mean()
    daily_std = return_series.std()
    if daily_std == 0:
        return 0.0
    annual_return = daily_mean * annual_days
    annual_vol = daily_std * np.sqrt(annual_days)
    sharpe = (annual_return - risk_free) / annual_vol
    return sharpe

def calc_sharpe_ratio(return_series, risk_free_rate: float = 0.0, freq: str = "minute"):
    """
    夏普比率计算（支持分钟/日级别）
    """
    mean_ret = return_series.mean() - risk_free_rate
    std_ret = return_series.std()
    
    if std_ret == 0:
        return 0
    
    # 分钟级：年化 = 均值 / 标准差 * sqrt(240*252)
    if freq == "minute":
        annual_factor = (252 * 240) ** 0.5
    # 日级（保留兼容）
    else:
        annual_factor = 252 ** 0.5
        
    return mean_ret / std_ret * annual_factor


def calc_sortino_ratio(
    return_series: pd.Series,
    risk_free_rate: float = 0.0,
    freq: str = "minute",
    mar: float = 0.0,
) -> float:
    """
    索提诺比率：下行波动率分母为低于目标收益 mar 的收益率平方均值的平方根（全样本作分母）。
    """
    r = return_series.dropna()
    if len(r) < 2:
        return 0.0
    excess = r - risk_free_rate
    downside = np.minimum(0.0, excess - mar)
    downside_var = np.mean(downside**2)
    downside_std = np.sqrt(downside_var) if downside_var > 0 else 0.0
    if downside_std == 0:
        return 0.0
    if freq == "minute":
        annual_factor = (252 * 240) ** 0.5
    else:
        annual_factor = 252 ** 0.5
    return excess.mean() / downside_std * annual_factor