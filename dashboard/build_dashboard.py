#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""海龟策略分析看板：参数网格、热力图、信号图、净值曲线。"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtest import run_backtest, run_param_grid
from src.data_fetch import STOCKS, load_all
from src.signals import TurtleConfig

OUT_DIR = ROOT / "output"

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


@dataclass
class GridConfig:
    entry_periods: list[int] | None = None
    exit_periods: list[int] | None = None
    atr_period: int = 20
    stop_atr_mult: float = 2.0

    def __post_init__(self) -> None:
        self.entry_periods = self.entry_periods or [10, 20, 30, 40, 55, 60]
        self.exit_periods = self.exit_periods or [5, 10, 15, 20]


def run_grid_search(symbol: str, df: pd.DataFrame, grid: GridConfig) -> pd.DataFrame:
    return run_param_grid(
        df,
        grid.entry_periods,
        grid.exit_periods,
        atr_period=grid.atr_period,
        stop_atr_mult=grid.stop_atr_mult,
    )


def plot_heatmap(
    grid_df: pd.DataFrame,
    name_zh: str,
    out_path: Path,
    title: str | None = None,
) -> plt.Figure:
    pivot = grid_df.pivot(index="entry_period", columns="exit_period", values="sharpe_ratio")
    fig, ax = plt.subplots(figsize=(10, 7))
    sns.heatmap(
        pivot,
        annot=True,
        fmt=".3f",
        cmap="RdYlGn",
        center=0.5,
        linewidths=0.5,
        ax=ax,
        cbar_kws={"label": "Sharpe Ratio"},
    )
    ax.set_xlabel("退出通道周期 (exit_period)")
    ax.set_ylabel("入场通道周期 (entry_period)")
    ax.set_title(title or f"图2 {name_zh} 入场/出场通道 Sharpe 比率敏感性分析")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    return fig


def plot_signals(
    result: dict,
    name_zh: str,
    out_path: Path,
    cfg: TurtleConfig,
) -> plt.Figure:
    data = result["data"]
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [3, 1]})

    ax1 = axes[0]
    ax1.plot(data["trade_date"], data["close"], label="收盘价", color="#334155", lw=1.2)
    ax1.plot(
        data["trade_date"],
        data["entry_high"],
        "--",
        color="#ef4444",
        alpha=0.8,
        label=f"入场上轨 N={cfg.entry_period}",
    )
    ax1.plot(
        data["trade_date"],
        data["exit_low"],
        "--",
        color="#22c55e",
        alpha=0.8,
        label=f"离场上轨 M={cfg.exit_period}",
    )

    buys = data[data["buy_signal"] == 1]
    sells = data[data["sell_signal"] == 1]
    ax1.scatter(
        buys["trade_date"],
        buys["close"],
        marker="^",
        color="#16a34a",
        s=80,
        zorder=5,
        label="买入",
    )
    ax1.scatter(
        sells["trade_date"],
        sells["close"],
        marker="v",
        color="#dc2626",
        s=80,
        zorder=5,
        label="卖出",
    )
    ax1.set_title(f"图1 {name_zh} 海龟策略 — 价格、唐奇安通道与交易信号")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(alpha=0.3)

    ax2 = axes[1]
    ax2.plot(data["trade_date"], data["atr"], color="#8b5cf6", label=f"ATR({cfg.atr_period})")
    held = data[data["position"] == 1]
    if not held.empty and held["stop_price"].notna().any():
        ax2.plot(
            held["trade_date"],
            held["stop_price"],
            "--",
            color="#f97316",
            alpha=0.7,
            label="止损线",
        )
    ax2.set_title("ATR 与止损线")
    ax2.legend(loc="upper left", fontsize=8)
    ax2.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    return fig


def plot_equity(result: dict, name_zh: str, out_path: Path) -> plt.Figure:
    equity = result["equity"]
    data = result["data"]
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(
        equity["trade_date"],
        equity["net_value"],
        color="#dc2626",
        lw=1.5,
        label="策略净值",
    )
    ax.plot(
        data["trade_date"],
        data["benchmark_nv"],
        color="#2563eb",
        lw=1.2,
        alpha=0.85,
        label="买入持有",
    )
    ax.set_title(f"图3 {name_zh} 策略净值 vs 买入持有基准")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    return fig


def best_from_grid(grid_df: pd.DataFrame) -> dict:
    if grid_df.empty:
        return {}
    best = grid_df.loc[grid_df["sharpe_ratio"].idxmax()]
    return {
        "best_entry": int(best["entry_period"]),
        "best_exit": int(best["exit_period"]),
        "sharpe_ratio": float(best["sharpe_ratio"]),
        "annualized_return": float(best["annualized_return"]),
        "max_drawdown": float(best["max_drawdown"]),
    }


def build_for_symbol(
    symbol: str,
    df: pd.DataFrame,
    grid: GridConfig,
    default_cfg: TurtleConfig,
) -> dict:
    name = STOCKS[symbol]["name"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    grid_df = run_grid_search(symbol, df, grid)
    grid_df.to_csv(OUT_DIR / f"param_grid_{symbol}.csv", index=False, encoding="utf-8-sig")

    if not grid_df.empty:
        plot_heatmap(grid_df, name, OUT_DIR / f"heatmap_sharpe_{symbol}.png")

    result = run_backtest(df, default_cfg)
    plot_signals(result, name, OUT_DIR / f"signals_{symbol}.png", default_cfg)
    plot_equity(result, name, OUT_DIR / f"equity_curve_{symbol}.png")

    summary = {
        "symbol": symbol,
        "name": name,
        "default_metrics": result["metrics"],
        "best_params": best_from_grid(grid_df),
    }
    with open(OUT_DIR / f"summary_{symbol}.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    plt.close("all")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--entry", default="10,20,30,40,55,60")
    parser.add_argument("--exit", default="5,10,15,20")
    parser.add_argument("--json-only", action="store_true")
    args = parser.parse_args()

    entry_periods = [int(x) for x in args.entry.split(",")]
    exit_periods = [int(x) for x in args.exit.split(",")]
    grid = GridConfig(entry_periods=entry_periods, exit_periods=exit_periods)
    default_cfg = TurtleConfig()

    stock_data = load_all()
    symbols = [args.symbol] if args.symbol else list(STOCKS.keys())

    all_best: dict = {}
    comparison_rows = []

    for symbol in symbols:
        if symbol not in stock_data:
            continue
        print(f"分析 {STOCKS[symbol]['name']} ({symbol})...")
        summary = build_for_symbol(symbol, stock_data[symbol], grid, default_cfg)
        all_best[symbol] = summary["best_params"]
        dm = summary["default_metrics"]
        bp = summary["best_params"]
        comparison_rows.append(
            {
                "标的": STOCKS[symbol]["name"],
                "默认Sharpe": dm["sharpe_ratio"],
                "最优Sharpe": bp.get("sharpe_ratio", ""),
                "最优entry/exit": f"{bp.get('best_entry','')}/{bp.get('best_exit','')}",
                "默认年化%": dm["annualized_return"],
                "最优年化%": bp.get("annualized_return", ""),
                "最大回撤%": dm["max_drawdown"],
            }
        )

    with open(OUT_DIR / "best_params.json", "w", encoding="utf-8") as f:
        json.dump(all_best, f, ensure_ascii=False, indent=2)

    if comparison_rows:
        pd.DataFrame(comparison_rows).to_csv(
            OUT_DIR / "comparison.csv", index=False, encoding="utf-8-sig"
        )
        print(pd.DataFrame(comparison_rows).to_string(index=False))

    if not args.json_only:
        print(f"输出目录: {OUT_DIR}")


if __name__ == "__main__":
    main()
