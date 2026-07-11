#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成海龟策略 Jupyter Notebook。"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "notebooks" / "turtle_strategy_backtest.ipynb"


def cell(cell_type: str, source: str) -> dict:
    return {
        "cell_type": cell_type,
        "metadata": {},
        "source": [line + "\n" for line in source.splitlines()],
        **({"outputs": [], "execution_count": None} if cell_type == "code" else {}),
    }


def build() -> None:
    nb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11.0"},
        },
        "cells": [
            cell("markdown", "# 海龟交易法则回测分析（TASK4）\n\n本 Notebook 展示：数据加载 → 唐奇安通道 → ATR → 信号 → 回测 → 参数热力图。"),
            cell("code", """import sys
from pathlib import Path
ROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()
sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import pandas as pd

from src.data_fetch import STOCKS, load_all
from src.signals import TurtleConfig
from src.backtest import run_backtest, run_param_grid
from dashboard.build_dashboard import plot_heatmap, plot_signals, plot_equity, GridConfig

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

SYMBOL = '002202'
CFG = TurtleConfig(entry_period=20, exit_period=10, atr_period=20, stop_atr_mult=2.0)
"""),
            cell("markdown", "## 1. 加载股价数据"),
            cell("code", """stock_data = load_all()
df = stock_data[SYMBOL]
print(f"{STOCKS[SYMBOL]['name']} 共 {len(df)} 行")
df.tail()"""),
            cell("markdown", "## 2. 唐奇安通道与 ATR"),
            cell("code", """result = run_backtest(df, CFG)
data = result['data']
data[['trade_date','close','entry_high','exit_low','atr','stop_price']].dropna().tail(10)"""),
            cell("markdown", "## 3. 交易信号与回测指标"),
            cell("code", """metrics = result['metrics']
pd.Series(metrics)"""),
            cell("markdown", "## 4. 图1 价格、通道与买卖点"),
            cell("code", """name = STOCKS[SYMBOL]['name']
plot_signals(result, name, ROOT / 'output' / f'signals_{SYMBOL}.png', CFG)
plt.show()"""),
            cell("markdown", "## 5. 图3 净值曲线"),
            cell("code", """plot_equity(result, name, ROOT / 'output' / f'equity_curve_{SYMBOL}.png')
plt.show()"""),
            cell("markdown", "## 6. 图2 参数敏感性热力图"),
            cell("code", """grid = GridConfig()
grid_df = run_param_grid(df, grid.entry_periods, grid.exit_periods)
best = grid_df.loc[grid_df['sharpe_ratio'].idxmax()]
print(f"最优参数: entry={int(best.entry_period)}, exit={int(best.exit_period)}")
print(f"最优 Sharpe: {best.sharpe_ratio:.4f}, 年化收益: {best.annualized_return:.2f}%")
plot_heatmap(grid_df, name, ROOT / 'output' / f'heatmap_sharpe_{SYMBOL}.png')
plt.show()"""),
            cell("markdown", "## 7. 五股对比"),
            cell("code", """rows = []
for sym, sdf in stock_data.items():
    r = run_backtest(sdf, CFG)
    m = r['metrics']
    rows.append({'标的': STOCKS[sym]['name'], '年化%': m['annualized_return'], 'Sharpe': m['sharpe_ratio'], '最大回撤%': m['max_drawdown'], '胜率%': m['win_rate'], '交易笔数': m['trade_count']})
pd.DataFrame(rows)"""),
            cell("markdown", "## 8. 心得\n\n- **趋势性强的周期股**（如工程机械）更适合较长入场周期；\n- **震荡市**应缩短出场周期或收紧 ATR 止损；\n- 热力图最优参数随标的差异明显，不宜一刀切。"),
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(nb, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"notebook={OUT}")


if __name__ == "__main__":
    build()
