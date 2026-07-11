#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""海龟策略买卖信号状态机。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .indicators import compute_atr, compute_donchian


@dataclass
class TurtleConfig:
    entry_period: int = 20
    exit_period: int = 10
    atr_period: int = 20
    stop_atr_mult: float = 2.0
    initial_capital: float = 100_000.0
    commission: float = 0.0003
    slippage: float = 0.0001
    position_ratio: float = 1.0


def compute_turtle_signals(df: pd.DataFrame, cfg: TurtleConfig) -> pd.DataFrame:
    out = compute_donchian(df, cfg.entry_period, cfg.exit_period)
    out["atr"] = compute_atr(out, cfg.atr_period)
    out = out.sort_values("trade_date").reset_index(drop=True)

    n = len(out)
    position = [0] * n
    buy_signal = [0] * n
    sell_signal = [0] * n
    stop_price = [float("nan")] * n
    trigger = [""] * n

    pos = 0
    highest_since_entry = 0.0

    for i in range(n):
        close = float(out.at[i, "close"])
        entry_high = out.at[i, "entry_high"]
        exit_low = out.at[i, "exit_low"]
        atr = out.at[i, "atr"]

        if pd.isna(entry_high) or pd.isna(exit_low) or pd.isna(atr):
            position[i] = pos
            continue

        entry_high = float(entry_high)
        exit_low = float(exit_low)
        atr = float(atr)

        if pos == 0:
            if close > entry_high:
                pos = 1
                highest_since_entry = close
                buy_signal[i] = 1
                trigger[i] = "BREAKOUT"
                stop_price[i] = highest_since_entry - cfg.stop_atr_mult * atr
        else:
            highest_since_entry = max(highest_since_entry, close)
            stop = highest_since_entry - cfg.stop_atr_mult * atr
            stop_price[i] = stop
            if close < stop:
                pos = 0
                sell_signal[i] = 1
                trigger[i] = "STOP_LOSS"
            elif close < exit_low:
                pos = 0
                sell_signal[i] = 1
                trigger[i] = "CHANNEL_EXIT"

        position[i] = pos

    out["position"] = position
    out["buy_signal"] = buy_signal
    out["sell_signal"] = sell_signal
    out["stop_price"] = stop_price
    out["trigger"] = trigger
    return out
