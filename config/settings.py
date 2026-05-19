# -*- coding: utf-8 -*-
"""
全局配置文件：所有固定参数、路径、回测常量统一放这里
"""

import os
from datetime import datetime

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# ===================== 回测基础参数 =====================
INITIAL_CAPITAL = 10000000.0       # 初始资金
COMMISSION_RATE = 0.0002           # 交易手续费率
RISK_FREE_RATE = 0.02              # 无风险利率（净值分析夏普/索提诺等）
SLIPPAGE_RATE = 0.0001             # 滑点
MIN_TRADE_QTY = 10                 # 最小交易数量（10股整数倍）

# 调仓触发方式：time=按相邻两次调仓之间「日历分钟差」；bar=按主循环已推进的 K 线根数（每个不同 date 算 1 根）
REBALANCE_MODE = "bar"            # "time" | "bar"
REBALANCE_INTERVAL = 10            # REBALANCE_MODE=time 时：两次策略调仓之间的最小间隔（分钟）
REBALANCE_BARS = 10                # REBALANCE_MODE=bar 时：距上一次策略调仓至少再经过多少根 K 线

# ===================== 策略参数 =====================
TOP_N = 10                       # 核心持仓数量
REDUNDANCY_N = 10                  # 冗余备选标的数量

# ===================== 风控参数 =====================
MAX_SINGLE_POS_RATIO = 0.13        # 单只股票最大仓位占比
TAKE_PROFIT_RATIO = 0.03           # 止盈比例
STOP_LOSS_RATIO = 0.05             # 止损比例

# ===================== 路径配置 =====================
DATA_CSV_PATH = os.path.join(_ROOT, "data", "market_data", "data0518.csv")
BENCHMARK_CSV_PATH = os.path.join(_ROOT, "data", "benchmark", "csi_convertible_bond.csv")
BENCHMARK_NAME = "中证转债"
# 基准 CSV 净值列名；None 时自动识别（benchmark_nav / 含「转债」「中证」的列等）
BENCHMARK_NAV_COLUMN = None
RESULTS_SAVE_PATH = os.path.join(_ROOT, "results")

# ===================== 回测时间范围 =====================
START_DATE = datetime(2020, 1, 1)
END_DATE = datetime(2024, 12, 31)

