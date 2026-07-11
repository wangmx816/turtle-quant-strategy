#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成海龟法则 Playground HTML 看板。"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_fetch import DATA_DIR, STOCKS, load_all

OUT_HTML = ROOT / "index.html"
OUT_PLAYGROUND = ROOT / "playground" / "index.html"
OUT_ASSETS = ROOT / "playground" / "assets"
REPO_URL = "https://github.com/wangmx816/turtle-quant-strategy"
PAGES_URL = "https://wangmx816.github.io/turtle-quant-strategy/"


def build_payload(stock_data: dict[str, pd.DataFrame]) -> dict:
    quotes = {}
    all_dates = []
    for symbol, df in stock_data.items():
        rows = [
            {
                "d": r["trade_date"].strftime("%Y-%m-%d"),
                "o": round(float(r["open"]), 4),
                "h": round(float(r["high"]), 4),
                "l": round(float(r["low"]), 4),
                "c": round(float(r["close"]), 4),
                "v": round(float(r["volume"]), 0),
            }
            for _, r in df.iterrows()
        ]
        all_dates.extend([x["d"] for x in rows])
        quotes[symbol] = {"name": STOCKS[symbol]["name"], "rows": rows}

    best_path = ROOT / "output" / "best_params.json"
    best_params = {}
    if best_path.exists():
        best_params = json.loads(best_path.read_text(encoding="utf-8"))

    return {
        "meta": {
            "updated_at": datetime.now().strftime("%Y-%m-%d"),
            "repo": REPO_URL,
            "pages": PAGES_URL,
            "data_range": {
                "start": min(all_dates) if all_dates else "",
                "end": max(all_dates) if all_dates else "",
            },
        },
        "stock_list": [
            {"symbol": s, "name": STOCKS[s]["name"], "ts_code": STOCKS[s]["ts_code"]}
            for s in STOCKS
        ],
        "quotes": quotes,
        "best_params": best_params,
    }


def render_html(payload: dict) -> str:
    data_json = json.dumps(payload, ensure_ascii=False)
    js_src = "playground/assets/turtle_backtest.js"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>海龟法则 Playground | Turtle Quant Strategy</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>
    :root {{
      --bg: #0f172a; --sidebar: #1e293b; --panel: #1e293b; --text: #f1f5f9;
      --muted: #94a3b8; --accent: #38bdf8; --green: #4ade80; --red: #f87171; --border: #334155;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: "Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background: var(--bg); color: var(--text); }}
    .layout {{ display: grid; grid-template-columns: 280px 1fr; min-height: 100vh; }}
    .sidebar {{ background: var(--sidebar); border-right: 1px solid var(--border); padding: 20px 16px; overflow-y: auto; }}
    .sidebar h1 {{ font-size: 1.05rem; margin-bottom: 4px; }}
    .sidebar .sub {{ color: var(--muted); font-size: .8rem; margin-bottom: 16px; }}
    .field {{ margin-bottom: 12px; }}
    .field label {{ display: block; font-size: .78rem; color: var(--muted); margin-bottom: 4px; }}
    .field select, .field input[type=number] {{ width: 100%; padding: 7px 10px; border: 1px solid var(--border); border-radius: 8px; background: #0f172a; color: var(--text); font-size: .88rem; }}
    .field input[type=range] {{ width: 100%; }}
    .range-val {{ float: right; color: var(--accent); font-weight: 600; }}
    .period-btns {{ display: flex; gap: 6px; flex-wrap: wrap; }}
    .period-btns button {{ flex: 1; min-width: 48px; padding: 6px 4px; border: 1px solid var(--border); border-radius: 8px; background: #0f172a; color: var(--muted); cursor: pointer; font-size: .78rem; }}
    .period-btns button.active {{ background: var(--accent); color: #0f172a; border-color: var(--accent); font-weight: 600; }}
    .toggle-row {{ display: flex; justify-content: space-between; align-items: center; font-size: .82rem; margin-bottom: 8px; color: var(--muted); }}
    .main {{ padding: 18px 22px 36px; overflow-x: hidden; }}
    .topbar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 8px; }}
    .topbar a {{ color: var(--accent); font-size: .8rem; text-decoration: none; }}
    .badge {{ font-size: .72rem; background: #14532d; color: #86efac; padding: 3px 8px; border-radius: 999px; }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(6,1fr); gap: 10px; margin-bottom: 14px; }}
    .kpi {{ background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px; }}
    .kpi .label {{ font-size: .72rem; color: var(--muted); }}
    .kpi .value {{ font-size: 1.25rem; font-weight: 700; margin-top: 2px; }}
    .pos {{ color: var(--red); }} .neg {{ color: var(--green); }}
    .panel {{ background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px; margin-bottom: 14px; }}
    .panel h2 {{ font-size: .92rem; margin-bottom: 10px; }}
    .chart-h {{ height: 280px; position: relative; }}
    .chart-m {{ height: 300px; position: relative; }}
    table {{ width: 100%; border-collapse: collapse; font-size: .78rem; }}
    th, td {{ border-bottom: 1px solid var(--border); padding: 6px 8px; text-align: left; }}
    th {{ color: var(--muted); font-weight: 500; }}
    .best-box {{ margin-top: 14px; padding: 10px; background: #0f172a; border-radius: 8px; font-size: .75rem; color: var(--muted); line-height: 1.6; }}
    @media (max-width: 1100px) {{ .layout {{ grid-template-columns: 1fr; }} .kpi-grid {{ grid-template-columns: repeat(3,1fr); }} }}
  </style>
</head>
<body>
<div class="layout">
  <aside class="sidebar">
    <h1>🐢 海龟法则 Playground</h1>
    <div class="sub">TASK4 · 交互式回测 <span class="badge">实时计算</span></div>
    <div class="field"><label>标的</label><select id="stockSel"></select></div>
    <div class="field"><label>时段</label><div class="period-btns" id="periodBtns">
      <button data-p="3m">3月</button><button data-p="6m">6月</button>
      <button data-p="1y" class="active">1年</button><button data-p="2y">2年</button>
    </div></div>
    <div class="field"><label>入场通道 N <span class="range-val" id="entryVal">20</span></label>
      <input type="range" id="entryPeriod" min="5" max="60" step="5" value="20" /></div>
    <div class="field"><label>离场通道 M <span class="range-val" id="exitVal">10</span></label>
      <input type="range" id="exitPeriod" min="5" max="30" step="5" value="10" /></div>
    <div class="field"><label>ATR 周期 <span class="range-val" id="atrVal">20</span></label>
      <input type="range" id="atrPeriod" min="10" max="30" step="2" value="20" /></div>
    <div class="field"><label>止损系数 xATR <span class="range-val" id="stopVal">2.0</span></label>
      <input type="range" id="stopAtrMult" min="0.5" max="3" step="0.5" value="2" /></div>
    <div class="toggle-row"><span>显示通道</span><input type="checkbox" id="showChannel" checked /></div>
    <div class="toggle-row"><span>显示买卖点</span><input type="checkbox" id="showSignals" checked /></div>
    <div class="best-box" id="bestBox">参数敏感性加载中...</div>
  </aside>
  <main class="main">
    <div class="topbar">
      <div>
        <a href="{REPO_URL}" target="_blank">GitHub 仓库</a> ·
        <a href="{PAGES_URL}" target="_blank">在线看板</a>
      </div>
      <div class="badge" id="dataBadge">数据更新中...</div>
    </div>
    <section class="kpi-grid" id="kpiGrid"></section>
    <section class="panel">
      <h2>📈 净值曲线</h2>
      <div class="chart-h"><canvas id="equityChart"></canvas></div>
    </section>
    <section class="panel">
      <h2>🔍 交易信号（唐奇安通道 + 买卖点）</h2>
      <div class="chart-m"><canvas id="signalChart"></canvas></div>
    </section>
    <section class="panel">
      <h2>📋 交易明细</h2>
      <div style="overflow-x:auto"><table id="tradeTable"><thead><tr>
        <th>入场日期</th><th>出场日期</th><th>入场价</th><th>出场价</th>
        <th>股数</th><th>收益率</th><th>持仓天</th><th>触发</th>
      </tr></thead><tbody></tbody></table></div>
    </section>
  </main>
</div>
<script>const PAYLOAD = {data_json};</script>
<script src="{js_src}?v=20260711"></script>
<script>
const charts = {{}};
let debounceTimer = null;
let currentPeriod = '1y';

function fmtPct(v, digits=2) {{
  const s = (v >= 0 ? '+' : '') + v.toFixed(digits) + '%';
  return `<span class="${{v >= 0 ? 'pos' : 'neg'}}">${{s}}</span>`;
}}

function getCfg() {{
  return {{
    entryPeriod: +document.getElementById('entryPeriod').value,
    exitPeriod: +document.getElementById('exitPeriod').value,
    atrPeriod: +document.getElementById('atrPeriod').value,
    stopAtrMult: +document.getElementById('stopAtrMult').value,
    capital: 100000,
    commission: 0.0003,
    slippage: 0.0001,
    positionRatio: 1.0,
  }};
}}

function getRows() {{
  const sym = document.getElementById('stockSel').value;
  const all = PAYLOAD.quotes[sym].rows;
  return TurtleBacktest.filterRowsByPeriod(all, currentPeriod);
}}

function renderKpi(m) {{
  document.getElementById('kpiGrid').innerHTML = `
    <div class="kpi"><div class="label">年化收益</div><div class="value">${{fmtPct(m.annualized_return)}}</div></div>
    <div class="kpi"><div class="label">夏普比率</div><div class="value">${{m.sharpe_ratio.toFixed(2)}}</div></div>
    <div class="kpi"><div class="label">最大回撤</div><div class="value neg">${{m.max_drawdown.toFixed(2)}}%</div></div>
    <div class="kpi"><div class="label">胜率</div><div class="value">${{m.win_rate.toFixed(1)}}%</div></div>
    <div class="kpi"><div class="label">交易笔数</div><div class="value">${{m.trade_count}}</div></div>
    <div class="kpi"><div class="label">止损次数</div><div class="value">${{m.stop_loss_count}}</div></div>`;
}}

function upsertChart(id, config) {{
  const ctx = document.getElementById(id).getContext('2d');
  if (charts[id]) {{ charts[id].destroy(); }}
  charts[id] = new Chart(ctx, config);
}}

function renderEquity(res) {{
  upsertChart('equityChart', {{
    type: 'line',
    data: {{
      labels: res.dates,
      datasets: [
        {{ label: '策略净值', data: res.strategyNv, borderColor: '#f87171', backgroundColor: 'transparent', tension: 0.1, pointRadius: 0, borderWidth: 1.5 }},
        {{ label: '买入持有', data: res.benchmarkNv, borderColor: '#38bdf8', backgroundColor: 'transparent', tension: 0.1, pointRadius: 0, borderWidth: 1.2 }},
      ],
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }},
      scales: {{
        x: {{ ticks: {{ color: '#64748b', maxTicksLimit: 8 }}, grid: {{ color: '#1e293b' }} }},
        y: {{ ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e293b' }} }},
      }},
    }},
  }});
}}

function renderSignals(res) {{
  const showCh = document.getElementById('showChannel').checked;
  const showSig = document.getElementById('showSignals').checked;
  const datasets = [
    {{ label: '收盘价', data: res.close, borderColor: '#cbd5e1', pointRadius: 0, borderWidth: 1.2 }},
  ];
  if (showCh) {{
    datasets.push({{ label: '入场上轨', data: res.entryHigh, borderColor: '#f87171', borderDash: [4,4], pointRadius: 0, borderWidth: 1 }});
    datasets.push({{ label: '离场上轨', data: res.exitLow, borderColor: '#4ade80', borderDash: [4,4], pointRadius: 0, borderWidth: 1 }});
  }}
  if (showSig && res.buyDates.length) {{
    datasets.push({{ label: '买入', data: res.dates.map((d,i) => res.buyDates.includes(d) ? res.close[i] : null), pointStyle: 'triangle', pointRadius: 6, showLine: false, borderColor: '#4ade80', backgroundColor: '#4ade80' }});
    datasets.push({{ label: '卖出', data: res.dates.map((d,i) => res.sellDates.includes(d) ? res.close[i] : null), pointStyle: 'triangle', rotation: 180, pointRadius: 6, showLine: false, borderColor: '#f87171', backgroundColor: '#f87171' }});
  }}
  upsertChart('signalChart', {{
    type: 'line',
    data: {{ labels: res.dates, datasets }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }},
      scales: {{
        x: {{ ticks: {{ color: '#64748b', maxTicksLimit: 8 }}, grid: {{ color: '#1e293b' }} }},
        y: {{ ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e293b' }} }},
      }},
    }},
  }});
}}

function renderTable(details) {{
  const tbody = document.querySelector('#tradeTable tbody');
  tbody.innerHTML = details.slice().reverse().map(t => `
    <tr>
      <td>${{t.entryDate}}</td><td>${{t.exitDate}}</td>
      <td>${{t.entryPrice.toFixed(2)}}</td><td>${{t.exitPrice.toFixed(2)}}</td>
      <td>${{t.qty}}</td>
      <td class="${{t.returnPct >= 0 ? 'pos' : 'neg'}}">${{t.returnPct.toFixed(2)}}%</td>
      <td>${{t.holdDays}}</td><td>${{t.trigger}}</td>
    </tr>`).join('');
}}

function renderBest(sym) {{
  const bp = PAYLOAD.best_params && PAYLOAD.best_params[sym];
  const el = document.getElementById('bestBox');
  if (!bp || !bp.best_entry) {{
    el.textContent = '运行 dashboard/build_dashboard.py 后可显示参数敏感性最优组合。';
    return;
  }}
  el.innerHTML = `<strong>参数敏感性（热力图最优）</strong><br>
    entry=${{bp.best_entry}}, exit=${{bp.best_exit}}<br>
    Sharpe=${{bp.sharpe_ratio}}, 年化=${{bp.annualized_return}}%`;
}}

function recalc() {{
  const rows = getRows();
  const cfg = getCfg();
  const res = TurtleBacktest.runBacktest(rows, cfg);
  renderKpi(res.metrics);
  renderEquity(res);
  renderSignals(res);
  renderTable(res.tradeDetails);
  document.getElementById('dataBadge').textContent =
    `数据更新：${{PAYLOAD.meta.updated_at}}（${{rows.length}} 个交易日）`;
}}

function scheduleRecalc() {{
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(recalc, 300);
}}

function init() {{
  const sel = document.getElementById('stockSel');
  PAYLOAD.stock_list.forEach(s => {{
    const o = document.createElement('option');
    o.value = s.symbol; o.textContent = `${{s.name}} (${{s.ts_code}})`;
    sel.appendChild(o);
  }});

  ['entryPeriod','exitPeriod','atrPeriod','stopAtrMult'].forEach(id => {{
    const el = document.getElementById(id);
    const valEl = document.getElementById(id.replace('Period','').replace('stopAtrMult','stop').replace('entry','entry').replace('exit','exit').replace('atr','atr'));
    const map = {{entryPeriod:'entryVal', exitPeriod:'exitVal', atrPeriod:'atrVal', stopAtrMult:'stopVal'}};
    el.addEventListener('input', () => {{
      document.getElementById(map[id]).textContent = el.value;
      scheduleRecalc();
    }});
  }});

  document.getElementById('stockSel').addEventListener('change', () => {{
    renderBest(document.getElementById('stockSel').value);
    scheduleRecalc();
  }});
  document.getElementById('showChannel').addEventListener('change', recalc);
  document.getElementById('showSignals').addEventListener('change', recalc);

  document.querySelectorAll('#periodBtns button').forEach(btn => {{
    btn.addEventListener('click', () => {{
      document.querySelectorAll('#periodBtns button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentPeriod = btn.dataset.p;
      scheduleRecalc();
    }});
  }});

  renderBest(sel.value);
  recalc();
}}
document.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>"""


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stock_data = load_all()
    payload = build_payload(stock_data)
    html = render_html(payload)
    OUT_HTML.write_text(html, encoding="utf-8")
    OUT_PLAYGROUND.parent.mkdir(parents=True, exist_ok=True)
    OUT_PLAYGROUND.write_text(html, encoding="utf-8")
    OUT_ASSETS.mkdir(parents=True, exist_ok=True)
    print(f"html={OUT_HTML}")
    print(f"pages={PAGES_URL}")


if __name__ == "__main__":
    main()
