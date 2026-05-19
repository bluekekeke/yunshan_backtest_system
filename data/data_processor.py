# -*- coding: utf-8 -*-
"""
数据导入层：读取CSV，全局路径由config统一管理
数据预处理：清洗、时间筛选、每日切片
"""
import os
from typing import Dict, Optional

import pandas as pd

from config.settings import (
    BENCHMARK_CSV_PATH,
    BENCHMARK_NAV_COLUMN,
    BENCHMARK_NAME,
    DATA_CSV_PATH,
    END_DATE,
    START_DATE,
)
from tools.data_utils import df_filter_by_date
from tools.run_log import RunLog

REQUIRED_MARKET_COLS = ("date", "symbol", "close")
_INVALID_SYMBOL_TOKENS = frozenset({"", "nan", "none", "null"})


def validate_market_df(df: pd.DataFrame) -> None:
    """校验行情表必要列与 symbol 有效性（须在 clean_raw_data 之前调用）。"""
    missing = [c for c in REQUIRED_MARKET_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            f"数据缺失必要列，需包含：{list(REQUIRED_MARKET_COLS)}，缺少：{missing}"
        )
    if df.empty:
        raise ValueError("回测数据为空")
    sym = df["symbol"].astype(str).str.strip()
    if sym.isna().all() or (sym == "").all():
        raise ValueError("symbol 列无有效标的代码")
    invalid = sym.str.lower().isin(_INVALID_SYMBOL_TOKENS)
    if invalid.any():
        raise ValueError(
            f"symbol 列存在 {int(invalid.sum())} 行空值或无效占位符，请检查原始数据"
        )


def load_pickle_data(file_path: str = DATA_CSV_PATH, verbose: bool = True) -> pd.DataFrame:
    """
    统一数据入口：读取CSV
    """
    try:
        df = pd.read_csv(file_path, encoding="utf-8")
        if verbose:
            print(f"读取 CSV 成功，路径：{file_path}，形状：{df.shape}")
        return df
    except FileNotFoundError:
        raise FileNotFoundError(f"文件不存在：{file_path}")
    except Exception as e:
        raise Exception(f"读取CSV失败：{e}")


def clean_raw_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    基础数据清洗：
    转日期、去空值、剔除价格异常
    约定字段：date, symbol, close
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "symbol", "close"])
    df = df[df["close"] > 0]
    df = df.sort_values(["date", "symbol"]).reset_index(drop=True)
    return df


def prepare_market_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    校验并清洗行情表（不含 config 时间区间筛选）。

    推荐通过 load_backtest_data() 完成读盘、列名统一与时间筛选；
    若直接向回测引擎传入 DataFrame，可先调用本函数或依赖引擎内部的同等处理。
    """
    validate_market_df(df)
    out = clean_raw_data(df)
    if out.empty:
        raise ValueError(
            "清洗后无有效行情数据（date/symbol/close 缺失或 close<=0），请检查原始 CSV"
        )
    return out


def build_symbol_name_map(df: pd.DataFrame) -> Dict[str, str]:
    """从行情表构建 symbol -> StockName 映射（用于 trades/signals/positions 日志）。"""
    if "StockName" not in df.columns or "symbol" not in df.columns:
        return {}
    names = (
        df[["symbol", "StockName"]]
        .dropna(subset=["symbol"])
        .drop_duplicates(subset=["symbol"], keep="first")
    )
    return dict(zip(names["symbol"].astype(str), names["StockName"].astype(str)))


def filter_data_by_time(df: pd.DataFrame) -> pd.DataFrame:
    """筛选起止时间内的数据"""
    return df_filter_by_date(df, START_DATE, END_DATE, date_col="date")


def load_backtest_data(
    file_path: str = DATA_CSV_PATH,
    log: Optional[RunLog] = None,
) -> pd.DataFrame:
    """加载 CSV → 列名统一 → 清洗 → 按 START_DATE/END_DATE 筛选。"""
    df = load_pickle_data(file_path, verbose=log is None)
    if "StockID" in df.columns:
        df = df.rename(columns={"StockID": "symbol"})
    df = prepare_market_df(df)
    before = len(df)
    df = filter_data_by_time(df)
    msg = (
        f"区间 {START_DATE.date()} ~ {END_DATE.date()}："
        f"筛选前 {before} 行 → 筛选后 {len(df)} 行"
    )
    if log:
        log.detail(msg)
        if not df.empty:
            log.detail(
                f"时间范围 {df['date'].min()} ~ {df['date'].max()}，"
                f"标的数 {df['symbol'].nunique()}"
            )
    else:
        print(msg)
    if df.empty:
        raise ValueError(
            f"区间 {START_DATE.date()} ~ {END_DATE.date()} 内无有效数据，请检查 config/settings.py"
        )
    return df


def get_daily_data_slice(df: pd.DataFrame, trade_date) -> pd.DataFrame:
    """截取单日全市场数据"""
    slice_df = df[df["date"] == pd.to_datetime(trade_date)].copy()
    return slice_df


def _detect_benchmark_nav_column(df: pd.DataFrame, nav_column: Optional[str] = None) -> str:
    if nav_column:
        if nav_column not in df.columns:
            raise ValueError(f"基准列 {nav_column!r} 不存在，当前列：{list(df.columns)}")
        return nav_column

    if BENCHMARK_NAV_COLUMN and str(BENCHMARK_NAV_COLUMN) in df.columns:
        return str(BENCHMARK_NAV_COLUMN)

    for name in ("benchmark_nav", "benchmark", "index_nav", "nav"):
        if name in df.columns:
            return name

    for col in df.columns:
        if col == "date":
            continue
        text = str(col)
        if "转债" in text or "中证" in text:
            return col

    skip = {"date", "cumulative", "strategy_nav", "fund_nav", "total_asset"}
    numeric = [
        c
        for c in df.columns
        if c not in skip and pd.api.types.is_numeric_dtype(df[c])
    ]
    if len(numeric) == 1:
        return numeric[0]
    if len(numeric) >= 2:
        for c in numeric:
            if "benchmark" in str(c).lower():
                return c
        return numeric[-1]

    raise ValueError(
        f"无法识别基准净值列，请使用列名 benchmark_nav 或在 settings 设置 BENCHMARK_NAV_COLUMN。当前列：{list(df.columns)}"
    )


def load_benchmark_nav(
    file_path: str = BENCHMARK_CSV_PATH,
    nav_column: Optional[str] = BENCHMARK_NAV_COLUMN,
    start_date=None,
    end_date=None,
    log: Optional[RunLog] = None,
) -> pd.Series:
    """
    加载日频基准净值（如中证转债指数），返回 DatetimeIndex + 累计净值（首日归一为 1.0）。

    CSV 约定：至少含 date 与一列净值（benchmark_nav，或列名含「转债」「中证」）。
  """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(
            f"基准文件不存在：{file_path}，请将 {BENCHMARK_NAME} 日频净值放入 data/benchmark/"
        )

    raw = pd.read_csv(file_path, encoding="utf-8-sig")
    if raw.empty:
        raise ValueError(f"基准 CSV 为空：{file_path}")

    nav_col = _detect_benchmark_nav_column(raw, nav_column)
    df = raw[["date", nav_col]].copy()
    df.columns = ["date", "nav"]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df = df.dropna(subset=["date", "nav"])
    df = df[df["nav"] > 0]
    df = df.drop_duplicates(subset=["date"], keep="last").sort_values("date")

    start = pd.Timestamp(start_date if start_date is not None else START_DATE).normalize()
    end = pd.Timestamp(end_date if end_date is not None else END_DATE).normalize()
    end_ts = end + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    df = df[(df["date"] >= start) & (df["date"] <= end_ts)]

    if df.empty:
        raise ValueError(
            f"基准 {BENCHMARK_NAME} 在 {start.date()} ~ {end.date()} 内无有效数据，请检查 {file_path}"
        )

    series = df.set_index("date")["nav"].astype(float)
    series.index = pd.to_datetime(series.index).normalize()
    base = float(series.iloc[0])
    if base > 0:
        series = series / base

    msg = (
        f"基准 {BENCHMARK_NAME}：{len(series)} 个交易日，"
        f"{series.index.min().date()} ~ {series.index.max().date()}"
    )
    if log:
        log.detail(msg)
    else:
        print(msg)

    return series.sort_index()

