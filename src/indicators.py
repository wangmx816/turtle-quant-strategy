#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""唐奇安通道与 ATR 指标计算。"""

from __future__ import annotations

import pandas as pd


def _wilder_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def compute_donchian(
    df: pd.DataFrame,
    entry_period: int,
    exit_period: int,
) -> pd.DataFrame:
    """计算入场/离场唐奇安通道（不含当日，避免前视偏差）。"""
    out = df.copy()
    high = out["high"].astype(float)
    low = out["low"].astype(float)
    out["entry_high"] = high.shift(1).rolling(entry_period, min_periods=entry_period).max()
    out["entry_low"] = low.shift(1).rolling(entry_period, min_periods=entry_period).min()
    out["exit_high"] = high.shift(1).rolling(exit_period, min_periods=exit_period).max()
    out["exit_low"] = low.shift(1).rolling(exit_period, min_periods=exit_period).min()
    return out


def compute_atr(
    df: pd.DataFrame,
    period: int = 20,
) -> pd.Series:
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return _wilder_ema(tr, period)
