#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""海龟策略模拟交易与回测指标。"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .signals import TurtleConfig, compute_turtle_signals


def run_backtest(df: pd.DataFrame, cfg: TurtleConfig | None = None) -> dict[str, Any]:
    cfg = cfg or TurtleConfig()
    data = compute_turtle_signals(df, cfg)
    valid = data.dropna(subset=["entry_high", "exit_low", "atr"]).reset_index(drop=True)
    if valid.empty:
        raise ValueError("有效数据不足，无法回测")

    cash = cfg.initial_capital
    shares = 0.0
    trades: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []
    open_trade: dict[str, Any] | None = None

    buy_cost = 1 + cfg.commission + cfg.slippage
    sell_cost = 1 - cfg.commission - cfg.slippage

    for _, row in valid.iterrows():
        price = float(row["close"])
        pos = int(row["position"])

        if int(row["buy_signal"]) == 1 and shares == 0:
            budget = cash * cfg.position_ratio
            exec_price = price * buy_cost
            qty = int(budget // exec_price)
            if qty > 0:
                cost = qty * exec_price
                cash -= cost
                shares = qty
                open_trade = {
                    "entry_date": row["trade_date"],
                    "entry_price": round(price, 4),
                    "exec_entry": round(exec_price, 4),
                    "qty": qty,
                    "trigger": row["trigger"] or "BREAKOUT",
                }
                trades.append(
                    {
                        "trade_date": row["trade_date"],
                        "action": "BUY",
                        "price": round(price, 4),
                        "exec_price": round(exec_price, 4),
                        "qty": qty,
                        "trigger": row["trigger"] or "BREAKOUT",
                    }
                )
        elif int(row["sell_signal"]) == 1 and shares > 0:
            exec_price = price * sell_cost
            proceeds = shares * exec_price
            exit_trigger = row["trigger"] or "CHANNEL_EXIT"
            if open_trade:
                hold_days = (row["trade_date"] - open_trade["entry_date"]).days
                ret_pct = (exec_price - open_trade["exec_entry"]) / open_trade["exec_entry"] * 100
                trades.append(
                    {
                        "trade_date": row["trade_date"],
                        "action": "SELL",
                        "price": round(price, 4),
                        "exec_price": round(exec_price, 4),
                        "qty": shares,
                        "trigger": exit_trigger,
                        "entry_date": open_trade["entry_date"],
                        "entry_price": open_trade["entry_price"],
                        "return_pct": round(ret_pct, 2),
                        "hold_days": hold_days,
                    }
                )
                open_trade = None
            else:
                trades.append(
                    {
                        "trade_date": row["trade_date"],
                        "action": "SELL",
                        "price": round(price, 4),
                        "exec_price": round(exec_price, 4),
                        "qty": shares,
                        "trigger": exit_trigger,
                    }
                )
            cash += proceeds
            shares = 0.0

        equity = cash + shares * price
        equity_rows.append(
            {
                "trade_date": row["trade_date"],
                "equity": equity,
                "cash": cash,
                "shares": shares,
                "close": price,
                "position": pos,
            }
        )

    if shares > 0:
        last = valid.iloc[-1]
        exec_price = float(last["close"]) * sell_cost
        cash += shares * exec_price
        if open_trade:
            hold_days = (last["trade_date"] - open_trade["entry_date"]).days
            ret_pct = (exec_price - open_trade["exec_entry"]) / open_trade["exec_entry"] * 100
            trades.append(
                {
                    "trade_date": last["trade_date"],
                    "action": "SELL",
                    "price": round(float(last["close"]), 4),
                    "exec_price": round(exec_price, 4),
                    "qty": shares,
                    "trigger": "END_CLOSE",
                    "entry_date": open_trade["entry_date"],
                    "entry_price": open_trade["entry_price"],
                    "return_pct": round(ret_pct, 2),
                    "hold_days": hold_days,
                }
            )
        equity_rows[-1]["equity"] = cash
        equity_rows[-1]["cash"] = cash
        equity_rows[-1]["shares"] = 0

    equity_df = pd.DataFrame(equity_rows)
    equity_df["net_value"] = equity_df["equity"] / cfg.initial_capital
    equity_df["drawdown"] = equity_df["net_value"] / equity_df["net_value"].cummax() - 1

    first_close = float(valid.iloc[0]["close"])
    valid = valid.copy()
    valid["benchmark_nv"] = valid["close"] / first_close

    metrics = compute_metrics(equity_df, trades, valid, cfg)
    trade_details = build_trade_details(trades)

    return {
        "data": valid,
        "equity": equity_df,
        "trades": pd.DataFrame(trades),
        "trade_details": trade_details,
        "metrics": metrics,
        "config": cfg,
    }


def build_trade_details(trades: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for t in trades:
        if t["action"] == "SELL" and "entry_date" in t:
            rows.append(
                {
                    "entry_date": t["entry_date"].strftime("%Y-%m-%d")
                    if hasattr(t["entry_date"], "strftime")
                    else t["entry_date"],
                    "exit_date": t["trade_date"].strftime("%Y-%m-%d")
                    if hasattr(t["trade_date"], "strftime")
                    else t["trade_date"],
                    "entry_price": t.get("entry_price", t["price"]),
                    "exit_price": t["price"],
                    "qty": t["qty"],
                    "return_pct": t.get("return_pct", 0),
                    "hold_days": t.get("hold_days", 0),
                    "trigger": t.get("trigger", ""),
                }
            )
    return pd.DataFrame(rows)


def compute_metrics(
    equity_df: pd.DataFrame,
    trades: list[dict[str, Any]],
    price_df: pd.DataFrame,
    cfg: TurtleConfig,
) -> dict[str, float | int | str]:
    nv = equity_df["net_value"]
    daily_ret = nv.pct_change().fillna(0)
    n_days = len(equity_df)
    years = max(n_days / 252, 1 / 252)

    cum_return = (nv.iloc[-1] - 1) * 100
    ann_return = ((nv.iloc[-1]) ** (1 / years) - 1) * 100 if nv.iloc[-1] > 0 else -100.0
    max_dd = float(equity_df["drawdown"].min() * 100)

    rf = 0.02 / 252
    excess = daily_ret - rf
    sharpe = float(excess.mean() / excess.std() * np.sqrt(252)) if excess.std() > 0 else 0.0

    bench_nv = price_df["benchmark_nv"]
    bench_cum = (bench_nv.iloc[-1] - 1) * 100
    bench_ann = ((bench_nv.iloc[-1]) ** (1 / years) - 1) * 100 if bench_nv.iloc[-1] > 0 else -100.0

    sell_trades = [t for t in trades if t["action"] == "SELL" and "return_pct" in t]
    wins = [t["return_pct"] for t in sell_trades if t["return_pct"] >= 0]
    losses = [abs(t["return_pct"]) for t in sell_trades if t["return_pct"] < 0]
    win_rate = len(wins) / len(sell_trades) * 100 if sell_trades else 0.0
    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(np.mean(losses)) if losses else 0.0
    profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0
    stop_loss_count = sum(1 for t in sell_trades if t.get("trigger") == "STOP_LOSS")

    dd_end_idx = equity_df["drawdown"].idxmin()
    dd_start_idx = int(nv.iloc[: dd_end_idx + 1].idxmax()) if dd_end_idx >= 0 else 0

    return {
        "cumulative_return": round(cum_return, 2),
        "annualized_return": round(ann_return, 2),
        "max_drawdown": round(max_dd, 2),
        "sharpe_ratio": round(sharpe, 3),
        "win_rate": round(win_rate, 1),
        "trade_count": len(sell_trades),
        "stop_loss_count": stop_loss_count,
        "profit_loss_ratio": round(profit_loss_ratio, 2),
        "benchmark_cumulative": round(bench_cum, 2),
        "benchmark_annualized": round(bench_ann, 2),
        "excess_return": round(cum_return - bench_cum, 2),
        "final_net_value": round(float(nv.iloc[-1]), 4),
        "max_dd_start": equity_df.iloc[dd_start_idx]["trade_date"].strftime("%Y-%m-%d"),
        "max_dd_end": equity_df.iloc[dd_end_idx]["trade_date"].strftime("%Y-%m-%d"),
    }


def run_param_grid(
    df: pd.DataFrame,
    entry_periods: list[int],
    exit_periods: list[int],
    atr_period: int = 20,
    stop_atr_mult: float = 2.0,
) -> pd.DataFrame:
    rows = []
    base = TurtleConfig(atr_period=atr_period, stop_atr_mult=stop_atr_mult)
    for entry in entry_periods:
        for exit_p in exit_periods:
            if exit_p >= entry:
                continue
            cfg = TurtleConfig(
                entry_period=entry,
                exit_period=exit_p,
                atr_period=base.atr_period,
                stop_atr_mult=base.stop_atr_mult,
                initial_capital=base.initial_capital,
                commission=base.commission,
                slippage=base.slippage,
                position_ratio=base.position_ratio,
            )
            try:
                res = run_backtest(df, cfg)
                m = res["metrics"]
                rows.append(
                    {
                        "entry_period": entry,
                        "exit_period": exit_p,
                        "sharpe_ratio": m["sharpe_ratio"],
                        "annualized_return": m["annualized_return"],
                        "max_drawdown": m["max_drawdown"],
                        "win_rate": m["win_rate"],
                        "trade_count": m["trade_count"],
                        "stop_loss_count": m["stop_loss_count"],
                    }
                )
            except Exception:
                continue
    return pd.DataFrame(rows)
