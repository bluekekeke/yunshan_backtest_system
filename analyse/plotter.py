# -*- coding: utf-8 -*-
"""
回测结果可视化工具
功能：净值曲线绘制、结果保存（文件名带时间戳，避免覆盖）
适配：分钟级/日级回测数据，自动解决横轴时间格式问题
"""
import os
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import NullLocator
from tools.output_paths import make_run_stamp
import pandas as pd

# 解决中文乱码问题（必须加，否则图表中文会变成方块）
plt.rcParams["font.sans-serif"] = ["SimHei", "WenQuanYi Zen Hei", "Heiti TC"]
plt.rcParams["axes.unicode_minus"] = False


class BacktestPlotter:
    def __init__(self, save_dir="results/equity", dpi=300, figsize=(12, 6), file_prefix="equity_curve"):
        """
        初始化可视化工具
        :param save_dir: 图片保存路径（默认和你的results结构对应）
        :param dpi: 图片分辨率（默认300，适合报告使用）
        :param figsize: 图表默认尺寸
        :param file_prefix: 输出图片文件名前缀（后缀自动加时间戳）
        """
        self.save_dir = save_dir
        self.dpi = dpi
        self.figsize = figsize
        self.file_prefix = file_prefix
        
        # 自动创建保存文件夹（不存在则新建）
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
            print(f"✅ 已创建图片保存目录：{self.save_dir}")

    def _build_save_path(self, filename=None, run_stamp=None):
        """生成不重复的图片保存路径；未指定 filename 时用前缀 + 时间戳。"""
        if filename is None:
            stamp = run_stamp or make_run_stamp()
            filename = f"{self.file_prefix}_{stamp}.png"
        elif not filename.lower().endswith(".png"):
            filename = f"{filename}.png"
        return os.path.join(self.save_dir, filename)

    def plot_equity_curve(self, equity_df, title="策略净值曲线", save=True, show=True, filename=None, run_stamp=None):
        """
        绘制净值曲线（解决分钟级数据横轴问题）
        :param equity_df: 净值数据，需包含 date、total_asset 列
        :param title: 图表标题
        :param save: 是否保存图片
        :param show: 是否显示图表
        :param filename: 保存文件名（可选）；默认用 file_prefix + 时间戳，避免覆盖
        :param run_stamp: 与 CSV 日志共用的时间戳（可选）
        """
        # 1. 数据预处理（关键！解决时间轴问题）
        df = equity_df.copy()
        df["date"] = pd.to_datetime(df["date"])  # 强制转为datetime类型
        df = df.sort_values("date").reset_index(drop=True)  # 按时间排序
        
        # 2. 创建画布
        fig, ax = plt.subplots(figsize=self.figsize)
        
        # 3. 绘制净值曲线
        ax.plot(
            df["date"], 
            df["total_asset"], 
            label="策略净值", 
            color="#1f77b4",  # 专业蓝色，和你的原图风格统一
            linewidth=2
        )
        
        # 4. 横轴仅显示日期（分钟级数据按自然日刻度，不显示时分）
        ax.xaxis.set_major_locator(mdates.DayLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.xaxis.set_minor_locator(NullLocator())
        plt.xticks(rotation=45, ha="right")
        
        # 5. 美化图表
        ax.set_title(title, fontsize=14, pad=20)
        ax.set_xlabel("日期", fontsize=12)
        ax.set_ylabel("总资产", fontsize=12)
        ax.legend(fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.7)  # 柔和网格线，不遮挡曲线
        
        # 自动调整布局，避免标签被截断
        plt.tight_layout()
        
        # 6. 保存图片
        if save:
            save_path = self._build_save_path(filename, run_stamp=run_stamp)
            plt.savefig(save_path, dpi=self.dpi, bbox_inches="tight")
            print(f"✅ 净值曲线已保存：{save_path}")
        
        # 7. 显示图表
        if show:
            plt.show()
        else:
            plt.close()