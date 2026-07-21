#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A 股日线取数。

优先级（DATA_SOURCE=auto 时）：
  1) akshare（免费，CI 推荐）
  2) tushare（需 Token 且有 daily 权限）
  3) eastmoney（本地兜底，GitHub Runner 上常失败）
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

END_DATE = datetime.now()
START_DATE = END_DATE - timedelta(days=730)

STOCKS = {
    "002202": {"ts_code": "002202.SZ", "name": "金风科技", "market": 0},
    "600031": {"ts_code": "600031.SH", "name": "三一重工", "market": 1},
    "000425": {"ts_code": "000425.SZ", "name": "徐工机械", "market": 0},
    "600207": {"ts_code": "600207.SH", "name": "安彩高科", "market": 1},
    "000816": {"ts_code": "000816.SZ", "name": "智慧农业", "market": 0},
}

ADJUST_MAP = {"none": 0, "qfq": 1, "hfq": 2}


def _normalize(df: pd.DataFrame, symbol: str, adjust: str, source: str) -> pd.DataFrame:
    info = STOCKS[symbol]
    out = df.copy()
    out = out.rename(columns={"vol": "volume", "pct_change": "pct_chg"})
    for col in ["trade_date", "open", "high", "low", "close"]:
        if col not in out.columns:
            raise RuntimeError(f"{symbol} 缺少字段: {col}")
    if "volume" not in out.columns:
        out["volume"] = 0.0
    if "amount" not in out.columns:
        out["amount"] = 0.0
    if "pct_chg" not in out.columns:
        out["pct_chg"] = out["close"].pct_change() * 100

    out["ts_code"] = info["ts_code"]
    out["trade_date"] = pd.to_datetime(out["trade_date"].astype(str))
    for col in ["open", "high", "low", "close", "volume", "amount", "pct_chg"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out["adjust_type"] = adjust
    out["data_source"] = source
    out = out[
        [
            "ts_code",
            "trade_date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "pct_chg",
            "adjust_type",
            "data_source",
        ]
    ]
    out = out.dropna(subset=["close"]).sort_values("trade_date").reset_index(drop=True)
    if out.empty:
        raise RuntimeError(f"{symbol} 未获取到数据")
    return out


def _get_tushare_token() -> str | None:
    token = os.environ.get("TUSHARE_TOKEN") or os.environ.get("TUSHARE_PRO_TOKEN")
    return token.strip() if token else None


# ---------------------------------------------------------------------------
# AkShare（CI 主源）
# ---------------------------------------------------------------------------

def fetch_via_akshare(symbol: str, adjust: str = "qfq") -> pd.DataFrame:
    import akshare as ak

    adj = "" if adjust == "none" else adjust
    start = START_DATE.strftime("%Y%m%d")
    end = END_DATE.strftime("%Y%m%d")
    raw = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start,
        end_date=end,
        adjust=adj,
    )
    if raw is None or raw.empty:
        raise RuntimeError(f"akshare 无数据: {symbol}")

    colmap = {
        "日期": "trade_date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
        "涨跌幅": "pct_chg",
    }
    df = raw.rename(columns=colmap)
    keep = [c for c in colmap.values() if c in df.columns]
    return _normalize(df[keep], symbol, adjust, "akshare")


# ---------------------------------------------------------------------------
# Tushare（需积分权限）
# ---------------------------------------------------------------------------

def fetch_via_tushare(symbol: str, adjust: str = "qfq") -> pd.DataFrame:
    token = _get_tushare_token()
    if not token:
        raise RuntimeError("未设置 TUSHARE_TOKEN")

    import tushare as ts

    ts_code = STOCKS[symbol]["ts_code"]
    start = START_DATE.strftime("%Y%m%d")
    end = END_DATE.strftime("%Y%m%d")
    adj = None if adjust == "none" else adjust

    df = None
    try:
        df = ts.pro_bar(
            ts_code=ts_code,
            api=ts.pro_api(token),
            start_date=start,
            end_date=end,
            adj=adj,
            freq="D",
        )
    except Exception as exc:
        print(f"  [warn] pro_bar 失败 ({symbol}): {exc}")

    if df is None or df.empty:
        pro = ts.pro_api(token)
        df = pro.daily(ts_code=ts_code, start_date=start, end_date=end)
        if adj in ("qfq", "hfq") and df is not None and not df.empty:
            try:
                factors = pro.adj_factor(ts_code=ts_code, start_date=start, end_date=end)
                if factors is not None and not factors.empty:
                    merged = df.merge(
                        factors[["trade_date", "adj_factor"]],
                        on="trade_date",
                        how="left",
                    ).sort_values("trade_date")
                    merged["adj_factor"] = merged["adj_factor"].ffill().bfill()
                    latest = float(merged["adj_factor"].iloc[-1])
                    ratio = merged["adj_factor"] / latest
                    for col in ["open", "high", "low", "close"]:
                        merged[col] = merged[col] * ratio
                    df = merged
            except Exception as exc:
                print(f"  [warn] adj_factor 失败: {exc}")

    if df is None or df.empty:
        raise RuntimeError(f"Tushare 未返回数据: {ts_code}")
    return _normalize(df, symbol, adjust, "tushare")


# ---------------------------------------------------------------------------
# 东方财富（本地兜底）
# ---------------------------------------------------------------------------

def _eastmoney_url(symbol: str, market: int, adjust: str = "qfq") -> str:
    fqt = ADJUST_MAP.get(adjust, 1)
    return (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?fields1=f1,f2,f3,f4,f5,f6"
        f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
        f"&ut=7eea3edcaed734bea9cbfc24409ed989"
        f"&klt=101&fqt={fqt}&secid={market}.{symbol}"
        f"&beg={START_DATE.strftime('%Y%m%d')}&end={END_DATE.strftime('%Y%m%d')}"
    )


def _parse_klines(payload: dict, symbol: str, adjust: str) -> pd.DataFrame:
    klines = payload.get("data", {}).get("klines") or []
    rows = []
    for line in klines:
        p = line.split(",")
        rows.append(
            {
                "trade_date": p[0],
                "open": float(p[1]),
                "close": float(p[2]),
                "high": float(p[3]),
                "low": float(p[4]),
                "volume": float(p[5]),
                "amount": float(p[6]),
                "pct_chg": float(p[8]) if len(p) > 8 else None,
            }
        )
    return _normalize(pd.DataFrame(rows), symbol, adjust, "eastmoney")


def fetch_via_eastmoney(symbol: str, adjust: str = "qfq") -> pd.DataFrame:
    info = STOCKS[symbol]
    url = _eastmoney_url(symbol, info["market"], adjust)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Referer": "https://quote.eastmoney.com/",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=60)
        resp.raise_for_status()
        return _parse_klines(resp.json(), symbol, adjust)
    except Exception:
        raw_path = DATA_DIR / f"_raw_{symbol}_{adjust}.json"
        cmd = (
            f'Invoke-WebRequest -Uri "{url}" -UseBasicParsing '
            f'| Select-Object -ExpandProperty Content '
            f'| Out-File -FilePath "{raw_path}" -Encoding utf8'
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(raw_path.read_text(encoding="utf-8-sig"))
        return _parse_klines(payload, symbol, adjust)


FETCHERS = {
    "akshare": fetch_via_akshare,
    "tushare": fetch_via_tushare,
    "eastmoney": fetch_via_eastmoney,
}


def resolve_source_chain(preferred: str | None = None) -> list[str]:
    source = (preferred or os.environ.get("DATA_SOURCE") or "auto").lower()
    if source == "auto":
        # CI 默认优先 akshare；有可用 tushare 权限时也可手动指定
        return ["akshare", "tushare", "eastmoney"]
    if source not in FETCHERS:
        raise ValueError(f"未知 DATA_SOURCE: {source}")
    # 指定主源后仍保留兜底，提高 CI 成功率
    rest = [s for s in ("akshare", "tushare", "eastmoney") if s != source]
    return [source, *rest]


def fetch_stock(symbol: str, adjust: str = "qfq", source: str | None = None) -> pd.DataFrame:
    chain = resolve_source_chain(source)
    errors: list[str] = []
    for src in chain:
        if src == "tushare" and not _get_tushare_token():
            errors.append("tushare: 无 Token，跳过")
            continue
        try:
            df = FETCHERS[src](symbol, adjust)
            print(f"  [ok] {symbol} via {src}")
            return df
        except Exception as exc:
            errors.append(f"{src}: {exc}")
            print(f"  [fail] {symbol} via {src}: {exc}")
    raise RuntimeError(f"{symbol} 全部数据源失败:\n" + "\n".join(errors))


def fetch_all(adjust: str = "qfq", source: str | None = None) -> dict[str, pd.DataFrame]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    chain = resolve_source_chain(source)
    print(f"数据源链: {' -> '.join(chain)}")

    result: dict[str, pd.DataFrame] = {}
    errors: list[str] = []
    for i, symbol in enumerate(STOCKS):
        try:
            df = fetch_stock(symbol, adjust, source)
            out = DATA_DIR / f"{symbol}_daily.csv"
            save_cols = [
                "ts_code",
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "amount",
                "pct_chg",
            ]
            df[save_cols].to_csv(
                out, index=False, encoding="utf-8-sig", date_format="%Y-%m-%d"
            )
            result[symbol] = df
            print(f"  {STOCKS[symbol]['name']}({symbol}): {len(df)} 行 -> {out.name}")
        except Exception as exc:
            errors.append(f"{symbol}: {exc}")
            print(f"  [error] {symbol}: {exc}")
        if i < len(STOCKS) - 1:
            time.sleep(0.4)

    if not result:
        raise RuntimeError("全部标的取数失败:\n" + "\n".join(errors))
    if errors:
        print("部分失败:\n" + "\n".join(errors))
    return result


def load_all() -> dict[str, pd.DataFrame]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data: dict[str, pd.DataFrame] = {}
    for symbol in STOCKS:
        path = DATA_DIR / f"{symbol}_daily.csv"
        if not path.exists():
            return fetch_all("qfq")
        data[symbol] = (
            pd.read_csv(path, parse_dates=["trade_date"])
            .sort_values("trade_date")
            .reset_index(drop=True)
        )
    return data


if __name__ == "__main__":
    print("拉取前复权日线数据...")
    fetch_all("qfq")
