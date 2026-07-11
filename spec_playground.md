# 海龟法则 Playground Spec（spec_playground.md）

> **版本**：1.0.0  
> **最后更新**：2026-07-11  
> **父 Spec**：`spec_turtle_strategy.md`  
> **参考样例**：[waanng/turtle-strategy-playground](https://waanng.github.io/turtle-strategy-playground/)（截图 1）  
> **部署目标**：https://wangmx816.github.io/turtle-quant-strategy/

---

## 1. 目的

构建**浏览器端交互式回测 Playground**，用户无需安装 Python 即可：

1. 选择不同标的（五只股票）
2. 选择回测时段（3月 / 6月 / 1年 / 2年）
3. 调节海龟策略参数（滑块实时回测）
4. 查看 KPI、净值曲线、交易信号图、交易明细表
5. 使用 GitHub Actions **每日自动更新**行情数据

---

## 2. 页面布局（对齐截图 1）

```
┌─────────────────────────────────────────────────────────────┐
│  🐢 海龟法则 Playground                    [数据更新: YYYY-MM-DD] │
├──────────┬──────────────────────────────────────────────────┤
│ 侧栏控件  │  KPI 条：年化收益 | 夏普 | 最大回撤 | 胜率 | 笔数 | 止损 │
│          ├──────────────────────────────────────────────────┤
│ 标的选择  │  📈 净值曲线（策略 vs 基准）                        │
│ 时段选择  ├──────────────────────────────────────────────────┤
│ 策略参数  │  🔍 交易信号（唐奇安通道 + 买卖点）                  │
│  ─ N     │     [显示通道] [显示买卖点]                         │
│  ─ M     ├──────────────────────────────────────────────────┤
│  ─ ATR   │  📋 交易明细表                                     │
│  ─ xATR  │                                                  │
│  ─ 最大单位│                                                  │
└──────────┴──────────────────────────────────────────────────┘
```

### 2.1 侧栏控件

| 控件 | ID | 类型 | 范围/选项 | 默认值 |
|------|-----|------|-----------|--------|
| 标的 | `stockSelect` | `<select>` | 五只股票 | 002202 金风科技 |
| 时段 | `periodBtns` | 按钮组 | 3月/6月/1年/2年 | 1年 |
| 入场通道 N | `entryPeriod` | range | 5–60, step 5 | 20 |
| 离场通道 M | `exitPeriod` | range | 5–30, step 5 | 10 |
| ATR 周期 | `atrPeriod` | range | 10–30, step 2 | 20 |
| 止损系数 xATR | `stopAtrMult` | range | 0.5–3.0, step 0.5 | 2.0 |
| 最大单位数 | `maxUnits` | range | 1–4 | 1（TASK4 简化为单仓） |
| 显示通道 | `showChannel` | checkbox | — | true |
| 显示买卖点 | `showSignals` | checkbox | — | true |

参数变更后 **300ms 防抖** 触发重算（无需点击按钮）。

### 2.2 KPI 条

| 标签 | 字段 | 格式 | 配色 |
|------|------|------|------|
| 年化收益 | `annualized_return` | `+X.XX%` | 正红负绿 |
| 夏普比率 | `sharpe_ratio` | `X.XX` | 默认 |
| 最大回撤 | `max_drawdown` | `-X.XX%` | 绿（回撤为负） |
| 胜率 | `win_rate` | `XX.X%` | 默认 |
| 交易笔数 | `trade_count` | 整数 | 默认 |
| 止损次数 | `stop_loss_count` | 整数 | 默认 |

### 2.3 净值曲线图

- 库：Chart.js 4.x（与 quant-strategy 一致）
- 红线：策略净值（归一化 1.0 起）
- 蓝线：买入持有基准
- X 轴：日期；Y 轴：净值
- 响应式，高度约 280px

### 2.4 交易信号图

- 价格折线（灰/白）
- 入场通道上轨（红虚线，`entry_high`）
- 离场通道下轨（绿虚线，`exit_low`）
- 买入点：绿色 ▲（`scatter`）
- 卖出点：红色 ▼（`scatter`）
- Tooltip：日期、价格、触发原因（突破/止损/通道）

### 2.5 交易明细表

| 列 | 字段 |
|----|------|
| 入场日期 | `entry_date` |
| 出场日期 | `exit_date` |
| 入场价 | `entry_price` |
| 出场价 | `exit_price` |
| 股数 | `qty` |
| 收益率 | `return_pct` |
| 持仓天 | `hold_days` |
| 触发 | `trigger`（BREAKOUT / CHANNEL_EXIT / STOP_LOSS） |

支持按收益率排序；最多显示 100 行。

---

## 3. 技术架构

### 3.1 数据流

```
GitHub Actions (每日)
    → python src/data_fetch.py
    → python playground/build_playground.py
    → 嵌入 PAYLOAD JSON 至 index.html
    → push gh-pages
    → GitHub Pages 静态托管
```

### 3.2 浏览器端回测

与 quant-strategy 的 `assets/backtest.js` 模式一致：

1. `build_playground.py` 将 OHLCV 压缩为 JSON payload
2. `assets/turtle_backtest.js` 实现：
   - `computeDonchian(rows, n)` 
   - `computeATR(rows, period)`
   - `computeSignals(rows, config)`
   - `runBacktest(rows, config)`
   - `computeMetrics(equity, trades)`
3. 侧栏事件 → 切片时段 → 重算 → 刷新三图一表

**Payload 结构**：

```json
{
  "meta": {
    "updated_at": "2026-07-11",
    "repo": "https://github.com/wangmx816/turtle-quant-strategy",
    "data_range": { "start": "2025-07-04", "end": "2026-07-03" }
  },
  "stock_list": [
    { "symbol": "002202", "name": "金风科技", "ts_code": "002202.SZ" }
  ],
  "quotes": {
    "002202": {
      "name": "金风科技",
      "rows": [
        { "d": "2025-07-04", "o": 10.17, "h": 10.18, "l": 9.88, "c": 9.89, "v": 497842 }
      ]
    }
  }
}
```

> 注：Playground 需要 OHLC 全字段（比 quant-strategy 仅 close 更丰富）。

### 3.3 Python / JS 逻辑一致性

验收时抽样对比：同一标的、同一参数下，Python `run_backtest()` 与 JS `runBacktest()` 的 Sharpe 偏差 < 0.05。

---

## 4. 文件清单

```
playground/
├── build_playground.py      # 生成 index.html + 嵌入 payload
├── assets/
│   ├── turtle_backtest.js   # 核心回测引擎
│   └── style.css            # 可选，也可内联
└── index.html               # 生成产物（同步至根目录）

.github/workflows/
└── update_data.yml          # 每日数据更新 + Pages 部署
```

---

## 5. GitHub Actions 工作流

### 5.1 `update_data.yml`

```yaml
name: Daily Data Update

on:
  schedule:
    - cron: '30 10 * * 1-5'   # 工作日 18:30 UTC+8
  workflow_dispatch:            # 支持手动触发

permissions:
  contents: write
  pages: write

jobs:
  update-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - run: pip install -r requirements.txt

      - name: Fetch latest quotes
        run: python src/data_fetch.py

      - name: Build playground
        run: python playground/build_playground.py

      - name: Build dashboard outputs (optional)
        run: python dashboard/build_dashboard.py --json-only

      - name: Commit data & HTML
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/ playground/index.html index.html output/
          git diff --cached --quiet || git commit -m "chore: daily data update $(date +%Y-%m-%d)"
          git push

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: .
          publish_branch: gh-pages
          exclude_assets: '.github,notebooks,src,dashboard,spec_*.md'
```

### 5.2 Pages 配置

仓库 Settings → Pages → Source: `gh-pages` 分支，根目录 `/`。

访问地址：`https://wangmx816.github.io/turtle-quant-strategy/`

### 5.3 数据新鲜度标识

页面右上角显示：

```
数据更新：2026-07-11（242 个交易日）
```

取自 `PAYLOAD.meta.updated_at` 与当前标的切片后行数。

---

## 6. UI 设计规范

### 6.1 主题

- 深色主题（对齐截图 1）
- CSS 变量：

```css
:root {
  --bg: #0f172a;
  --sidebar: #1e293b;
  --panel: #1e293b;
  --text: #f1f5f9;
  --muted: #94a3b8;
  --accent: #38bdf8;
  --green: #4ade80;
  --red: #f87171;
  --border: #334155;
}
```

### 6.2 响应式

- 桌面：侧栏 280px + 主区域
- 移动：侧栏折叠为顶部抽屉

### 6.3 加载状态

参数变更时 KPI 区显示「计算中...」，图表半透明遮罩。

---

## 7. 参数热力图嵌入（可选增强）

侧栏底部增加「参数敏感性」折叠面板：

- 使用 Dashboard 预计算的 `output/best_params.json`
- 显示当前标的 Top-3 参数组合简表
- 链接到 Notebook 完整热力图

---

## 8. 部署清单

| 步骤 | 命令 / 操作 |
|------|-------------|
| 初始化仓库 | `gh repo create wangmx816/turtle-quant-strategy --public` |
| 首次取数 | `python src/data_fetch.py` |
| 构建 Playground | `python playground/build_playground.py` |
| 本地预览 | `python -m http.server 8080` |
| 推送 | `git push origin main` |
| 启用 Pages | 仓库 Settings → Pages → gh-pages |
| 验证 Actions | 手动触发 `workflow_dispatch` |

---

## 9. 验收标准

- [ ] 五只股票可切换，图表即时刷新
- [ ] 四个时段按钮正确切片数据
- [ ] 六个参数滑块生效且默认值与 Spec 一致
- [ ] KPI 六项指标显示正确
- [ ] 净值曲线、信号图、明细表三处数据一致
- [ ] 买卖点与通道可独立开关
- [ ] Actions 手动触发后数据日期更新
- [ ] Pages 可公开访问
- [ ] Python/JS 回测结果偏差 < 5%

---

## 10. 与 TASK4 作业的关系

| 作业要求 | Playground 对应 |
|----------|----------------|
| 选择不同标的 | `stockSelect` |
| 选择不同时段 | `periodBtns` |
| 配置海龟参数 | 侧栏滑块 |
| 入场/退出 Sharpe 组合 | Dashboard 热力图 + 可选简表 |
| 回测指标 | KPI 条 |
| 交易点位可视化 | 信号图 + 明细表 |
| 每日补充新数据 | GitHub Actions |
| 最新完整数据回测 | 自动部署后 Pages 即用 |
