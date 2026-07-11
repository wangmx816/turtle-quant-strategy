# 海龟交易策略 Spec（spec_turtle_strategy.md）

> **版本**：1.0.0  
> **最后更新**：2026-07-11  
> **关联项目**：[turtle-quant-strategy](https://github.com/wangmx816/turtle-quant-strategy)  
> **上游数据源**：与 [quant-strategy](https://github.com/wangmx816/quant-strategy) 保持一致（东方财富 API，前复权日线）

---

## 1. 目的与范围

本 Spec 定义海龟法则（Turtle Trading）在 A 股日线数据上的**完整实现规范**，覆盖：

1. 策略核心思想与交易规则
2. 唐奇安通道（Donchian Channel）、ATR、止损的计算公式
3. 买卖信号生成逻辑
4. 模拟交易与回测引擎
5. 量化指标计算
6. Notebook 可视化输出
7. 与 Playground 看板、Dashboard 分析看板的数据契约

**不在本 Spec 范围**：期货多品种组合、跨市场套利、实盘下单接口。

---

## 2. 策略核心思想

### 2.1 起源

海龟交易法由理查德·丹尼斯（Richard Dennis）与威廉·埃克哈特（William Eckhardt）于 1983 年通过「交易员培养实验」系统化总结，核心命题：

> **趋势可以被规则化捕捉；风险管理比预测方向更重要。**

### 2.2 核心思想（实现层面）

| 维度 | 思想 | 在本项目中的体现 |
|------|------|------------------|
| 入场 | 价格突破 N 日高点 → 趋势可能启动 | `entry_period` 唐奇安上轨突破买入 |
| 出场 | 价格跌破 M 日低点 → 趋势可能结束 | `exit_period` 唐奇安下轨跌破卖出 |
| 波动率 | ATR 衡量市场「呼吸」，用于止损与仓位 | `atr_period` + `stop_atr_mult` |
| 风险控制 | 单笔亏损限制在账户固定比例 | 2×ATR 止损（可配置） |
| 纪律 | 完全机械化，消除情绪干扰 | 信号由规则生成，无主观判断 |

### 2.3 关键优势

1. **规则明确、可回测**：所有决策由数值阈值触发，适合量化验证。
2. **趋势友好**：在单边行情中能持有较长时间，捕捉大幅波动。
3. **风险可控**：ATR 动态止损使不同波动率标的使用统一风险框架。
4. **参数可优化**：入场/出场周期、ATR 周期可在历史数据上敏感性分析（热力图）。
5. **跨品种适用**：不依赖基本面，适用于流动性较好的趋势性资产。

### 2.4 主要局限（需在报告中说明）

- 震荡市中频繁假突破，胜率下降、交易成本上升。
- 滞后性：突破入场意味着放弃底部，出场同理。
- 单一多头简化版无法覆盖原版海龟的加仓与多系统并行。

---

## 3. 关键概念定义

### 3.1 唐奇安通道（Donchian Channel / 高低点通道）

在交易日 `t`，给定回看窗口 `N`：

```
上轨 entry_high[t] = max(high[t-N : t-1])   # 不含当日，避免前视偏差
下轨 entry_low[t]  = min(low[t-N : t-1])
```

- **入场通道周期 `entry_period`（N）**：默认 20。收盘价 **向上突破** 上轨 → 买入信号。
- **离场通道周期 `exit_period`（M）**：默认 10。收盘价 **向下跌破** 下轨 → 卖出信号。
- 经典海龟使用 **双系统**：系统一 N=20/M=10，系统二 N=55/M=20。本项目默认实现系统一，系统二作为扩展参数。

**注意**：入场用 `entry_period`，出场用 `exit_period`，二者可独立配置（截图 2 热力图即对此做敏感性分析）。

### 3.2 平均真实波幅（ATR）

真实波幅（True Range）：

```
TR[t] = max(
    high[t] - low[t],
    |high[t] - close[t-1]|,
    |low[t] - close[t-1]|
)
```

ATR 采用 **Wilder 平滑**（与 ai-quant-lab / quant-strategy 一致）：

```
ATR[t] = Wilder_EMA(TR, period=atr_period)
```

默认 `atr_period = 20`（经典海龟为 20 日 ATR）。

**用途**：
- 止损距离 = `stop_atr_mult × ATR`（默认 2.0，截图 Playground 为 0.5 表示更紧止损，属教学简化）
- 仓位单位：`1 Unit = (账户 × 风险比例) / ATR`（完整版；TASK4 简化为固定仓位比例）

### 3.3 止损条件

本项目实现 **ATR 跟踪止损**（多头）：

```
止损价 stop_price[t] = 持仓后最高价 - stop_atr_mult × ATR[t]
```

触发规则（每日收盘后检查，次日开盘或收盘价执行——与回测引擎配置一致）：

1. 若 `close[t] < stop_price[t]` → 强制卖出（`trigger = "STOP_LOSS"`）
2. 若 `close[t] < exit_low[t]`（M 日下轨）→ 规则卖出（`trigger = "CHANNEL_EXIT"`）
3. 止损优先于通道出场（同日同时满足时记为止损）

### 3.4 买入 / 卖出信号（简化单仓位版）

| 信号 | 条件 | 说明 |
|------|------|------|
| 买入 `buy_signal` | `position==0` 且 `close > entry_high` | 突破入场 |
| 卖出 `sell_signal` | `position==1` 且 (`close < exit_low` 或 `close < stop_price`) | 通道或止损离场 |

**状态机**：

```
空仓 --[突破上轨]--> 持仓 --[跌破下轨 或 止损]--> 空仓
```

---

## 4. 数据规范

### 4.1 标的池（与 quant-strategy 一致）

| symbol | ts_code | name_zh | market |
|--------|---------|---------|--------|
| 002202 | 002202.SZ | 金风科技 | 0 |
| 600031 | 600031.SH | 三一重工 | 1 |
| 000425 | 000425.SZ | 徐工机械 | 0 |
| 600207 | 600207.SH | 安彩高科 | 1 |
| 000816 | 000816.SZ | 智慧农业 | 0 |

### 4.2 数据文件

```
data/{symbol}_daily.csv
```

Schema（与 quant-strategy 相同）：

```csv
ts_code,trade_date,open,high,low,close,volume,amount,pct_chg
```

- 复权方式：前复权 `qfq`
- 时间范围：默认近 1 年（242 交易日），可通过 Playground 选择 3月/6月/1年/2年
- 数据来源：东方财富 `push2his.eastmoney.com`（复用 `src/data_fetch.py`）

### 4.3 数据更新

- **本地**：`python src/data_fetch.py`
- **CI**：GitHub Actions 工作日 18:30 UTC+8 自动拉取（见 `spec_playground.md` § CI）

---

## 5. 模块设计

```
turtle-quant-strategy/
├── spec_turtle_strategy.md    # 本文件
├── spec_dashboard.md          # 静态分析看板 Spec
├── spec_playground.md         # 交互式 Playground Spec
├── src/
│   ├── data_fetch.py          # 复用/继承 quant-strategy
│   ├── indicators.py          # 唐奇安通道 + ATR
│   ├── signals.py             # 买卖信号状态机
│   ├── backtest.py            # 海龟回测引擎
│   └── metrics.py             # 指标计算（可合并入 backtest.py）
├── notebooks/
│   └── turtle_strategy_backtest.ipynb
├── playground/
│   ├── build_playground.py    # 生成 index.html
│   ├── assets/turtle_backtest.js
│   └── index.html
├── dashboard/
│   └── build_dashboard.py     # 参数热力图 + 静态报告
├── output/
│   ├── heatmap_sharpe.png
│   ├── signals_{symbol}.png
│   └── backtest_summary.json
├── .github/workflows/
│   └── update_data.yml
├── requirements.txt
└── README.md
```

### 5.1 `src/indicators.py`

```python
def compute_donchian(df, entry_period: int, exit_period: int) -> pd.DataFrame:
    """返回 entry_high, entry_low, exit_high, exit_low 四列。"""

def compute_atr(df, period: int = 20) -> pd.Series:
    """Wilder 平滑 ATR，与 ai-quant-lab indicators.compute_atr 一致。"""
```

### 5.2 `src/signals.py`

```python
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
    """输出列：entry_high, exit_low, atr, stop_price, position, buy_signal, sell_signal"""
```

### 5.3 `src/backtest.py`

回测流程（对齐 quant-strategy 架构）：

1. `compute_turtle_signals()` 生成信号
2. 逐日遍历：买入（突破）、卖出（止损/通道）、更新权益
3. `compute_metrics()` 输出 KPI
4. `run_param_grid()` 参数网格搜索（供 Dashboard 热力图）

### 5.4 回测指标（必须输出）

| 指标 | 字段名 | 说明 |
|------|--------|------|
| 年化收益 | `annualized_return` | % |
| 夏普比率 | `sharpe_ratio` | 年化，rf=2% |
| 最大回撤 | `max_drawdown` | % |
| 胜率 | `win_rate` | 盈利交易占比 % |
| 交易笔数 | `trade_count` | 完整买卖对数 |
| 止损次数 | `stop_loss_count` | 触发 ATR 止损次数 |
| 累计收益 | `cumulative_return` | % |
| 盈亏比 | `profit_loss_ratio` | 平均盈利/平均亏损 |
| 基准年化 | `benchmark_annualized` | 买入持有 |

---

## 6. 参数网格（Dashboard 热力图）

默认搜索空间（与截图 2 对齐，可扩展）：

```yaml
entry_period: [10, 20, 30, 40, 55, 60]
exit_period:  [5, 10, 15, 20]
atr_period:   [14, 20, 30]          # 热力图固定 atr=20，全网格搜索时展开
```

热力图：
- X 轴：`exit_period`
- Y 轴：`entry_period`
- 色阶：Sharpe Ratio（绿高红低）
- 单元格标注数值（保留 3 位小数）

输出最优参数摘要：

```
最优参数: entry={e}, exit={m}, atr={a}
最优 Sharpe: {sharpe}
年化收益: {ann_return}%
```

---

## 7. Notebook 规范（`turtle_strategy_backtest.ipynb`）

### 7.1 章节结构

| 序号 | 章节 ID | 内容 |
|------|---------|------|
| 1 | `setup` | 导入、参数、加载 CSV |
| 2 | `load_data` | 五只股票概览表 |
| 3 | `donchian` | 计算通道，打印中间变量 |
| 4 | `atr` | 计算 ATR，与通道叠加图 |
| 5 | `signals` | 买卖信号表 |
| 6 | `visualize` | 图1 股价+通道+买卖点 |
| 7 | `backtest` | 单标的回测 KPI 表 |
| 8 | `param_sweep` | 热力图（图2） |
| 9 | `multi_stock` | 五股对比表 |
| 10 | `conclusion` | 适应场景与心得 |

### 7.2 图表要求（对应 TASK4 提交）

- 每张图必须有 **图号** 与 **标题**（如「图1 金风科技海龟策略信号图」）
- Notebook 或 Word 报告中附 **解读段落**（2–3 句）

### 7.3 默认参数

```python
SYMBOL = "002202"
ENTRY_PERIOD = 20
EXIT_PERIOD = 10
ATR_PERIOD = 20
STOP_ATR_MULT = 2.0
```

---

## 8. 验收标准

- [ ] 五只股票数据可从 `data/` 加载，格式与 quant-strategy 一致
- [ ] 唐奇安通道计算不含前视偏差（shift 1 日）
- [ ] ATR 采用 Wilder 平滑，与 ai-quant-lab 结果一致（抽样校验）
- [ ] 买卖信号在图上可辨识（▲ 买 / ▼ 卖）
- [ ] 回测含手续费万三、滑点万一
- [ ] 输出全部 KPI 字段
- [ ] 参数热力图可找出最优 entry/exit 组合
- [ ] Playground 看板可在线交互（见 spec_playground.md）
- [ ] GitHub Actions 每日更新数据并成功部署 Pages

---

## 9. 依赖

```
pandas>=2.0.0
numpy>=1.24.0
matplotlib>=3.7.0
seaborn>=0.13.0
requests>=2.28.0
python-docx>=1.1.0   # Word 报告
```

---

## 10. 参考文献

- Curtis Faith, *Way of the Turtle* (2007)
- Richard Dennis Turtle Trading Rules (public domain summaries)
- 本项目上游：quant-strategy 双均线回测框架
