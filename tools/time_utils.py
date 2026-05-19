# -*- coding: utf-8 -*-
"""
时间日期通用工具
"""
from datetime import datetime
import pandas as pd


def str_to_datetime(date_str: str, fmt: str = "%Y-%m-%d") -> datetime:
    """字符串转datetime"""
    return datetime.strptime(date_str, fmt)


def datetime_to_str(dt: datetime, fmt: str = "%Y-%m-%d") -> str:
    """datetime转字符串"""
    return dt.strftime(fmt)


def get_trade_date_range(df: pd.DataFrame, date_col: str = "date") -> tuple[datetime, datetime]:
    """获取数据起止时间"""
    df[date_col] = pd.to_datetime(df[date_col])
    start_dt = df[date_col].min()
    end_dt = df[date_col].max()
    return start_dt, end_dt


def is_same_day(dt1: datetime, dt2: datetime) -> bool:
    """判断两个时间是否同一天"""
    return dt1.year == dt2.year and dt1.month == dt2.month and dt1.day == dt2.day

