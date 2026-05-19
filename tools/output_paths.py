# -*- coding: utf-8 -*-
"""回测输出文件命名：统一时间戳，避免多次运行互相覆盖。"""
import os
from datetime import datetime


def make_run_stamp() -> str:
    """生成单次回测运行的时间戳（同一轮结果共用）。"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def build_output_path(directory: str, prefix: str, stamp: str, ext: str = ".csv") -> str:
    """
    拼接带时间戳的输出路径，并确保目录存在。
    :return: 例如 results/trades/trades_20260518_143052.csv
    """
    if not ext.startswith("."):
        ext = f".{ext}"
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, f"{prefix}_{stamp}{ext}")
