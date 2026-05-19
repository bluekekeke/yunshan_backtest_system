# -*- coding: utf-8 -*-
"""回测运行终端日志：时间戳、分阶段耗时、汇总。"""
from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional, Tuple


def _fmt_seconds(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{int(minutes)}m {sec:.1f}s"
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours)}h {int(minutes)}m {sec:.0f}s"


class RunLog:
    """结构化终端输出，记录各阶段耗时。"""

    def __init__(self, title: str = "回测任务"):
        self.title = title
        self._started_at = datetime.now()
        self._t0 = time.perf_counter()
        self._sections: List[Tuple[str, float]] = []

    def _ts(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def banner(self, **meta: object) -> None:
        line = "=" * 56
        print(f"\n{line}")
        print(f"  {self.title}")
        print(f"  开始时间: {self._started_at:%Y-%m-%d %H:%M:%S}")
        for key, val in meta.items():
            print(f"  {key}: {val}")
        print(line)

    def info(self, msg: str) -> None:
        print(f"[{self._ts()}] {msg}")

    def detail(self, msg: str, indent: int = 2) -> None:
        print(f"[{self._ts()}] {' ' * indent}{msg}")

    @contextmanager
    def section(self, name: str):
        self.info(f"▶ {name} ...")
        t0 = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - t0
            self._sections.append((name, elapsed))
            self.info(f"✓ {name} 完成，耗时 {_fmt_seconds(elapsed)}")

    def step(self, name: str, elapsed: float, extra: str = "") -> None:
        """记录已在块内计时的步骤（不嵌套 section）。"""
        self._sections.append((name, elapsed))
        suffix = f" | {extra}" if extra else ""
        self.info(f"✓ {name} 耗时 {_fmt_seconds(elapsed)}{suffix}")

    def summary(self) -> float:
        total = time.perf_counter() - self._t0
        line = "-" * 56
        print(f"\n{line}")
        print("  耗时汇总")
        print(line)
        for name, sec in self._sections:
            pct = (sec / total * 100) if total > 0 else 0
            print(f"  {name:<20} {_fmt_seconds(sec):>10}  ({pct:5.1f}%)")
        print(line)
        print(f"  总耗时: {_fmt_seconds(total)}")
        print(f"  结束时间: {datetime.now():%Y-%m-%d %H:%M:%S}")
        print(f"{line}\n")
        return total
