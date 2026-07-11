# 海龟策略分析看板 Spec（spec_dashboard.md）

> **版本**：1.0.0  
> **最后更新**：2026-07-11  
> **父 Spec**：`spec_turtle_strategy.md`  
> **参考样例**：Jupyter Notebook 热力图（截图 2）、参数敏感性分析报告

---

## 1. 目的

构建**静态分析看板（Dashboard）**，用于：

1. 批量回测五只标的
2. 入场/出场通道参数网格搜索
3. 生成 Sharpe 比率热力图（核心交付物，对应截图 2）
4. 输出 JSON/PNG 供 Notebook 与 Word 报告引用
5. 为 Playground 提供预计算基准数据（可选）

与 Playground 的区别：

| 维度 | Dashboard（本 Spec） | Playground |
|------|---------------------|------------|
| 形态 | Python 脚本 + Notebook + 静态图 | 浏览器交互 HTML |
| 用户 | 分析师/作业提交 | 在线演示 |
| 参数 | 全网格批量扫描 | 滑块实时调参 |
| 输出 | PNG、JSON、Word | 实时图表 |

---

## 2. 目录结构

```
dashboard/
├── build_dashboard.py       # 主入口：网格搜索 + 出图
├── templates/
│   └── report_section.md    # Word 报告图表解读模板
└── output/                  # 生成物（或写入项目根 output/）
    ├── heatmap_sharpe_{symbol}.png
    ├── heatmap_sharpe_all.png
    ├── param_grid_{symbol}.csv
    ├── best_params.json
    └── equity_curve_{symbol}.png
```

---

## 3. 功能需求

### 3.1 参数网格搜索

**输入**：

```python
@dataclass
class GridConfig:
    entry_periods: list[int] = [10, 20, 30, 40, 55, 60]
    exit_periods: list[int] = [5, 10, 15, 20]
    atr_period: int = 20          # 热力图第一轮固定
    stop_atr_mult: float = 2.0
    symbols: list[str] = ALL_SYMBOLS
```

**处理**：

对每个 `(symbol, entry, exit)` 组合调用 `run_backtest()`，记录：

```json
{
  "symbol": "002202",
  "entry_period": 20,
  "exit_period": 10,
  "sharpe_ratio": 0.62,
  "annualized_return": 9.47,
  "max_drawdown": -10.90,
  "win_rate": 59.46,
  "trade_count": 37,
  "stop_loss_count": 6
}
```

**输出**：`output/param_grid_{symbol}.csv`

### 3.2 Sharpe 热力图（图2）

**图表规格**：

| 属性 | 值 |
|------|-----|
| 图类型 | Seaborn heatmap |
| 标题 | `图2 {name_zh} 入场/出场通道 Sharpe 比率敏感性分析` |
| X 轴 | 退出通道周期 (exit_period) |
| Y 轴 | 入场通道周期 (entry_period) |
| 色图 | `RdYlGn`，中心值 0.5 |
| 标注 | 每格显示 Sharpe（3 位小数） |
| 尺寸 | 10×7 英寸，dpi=150 |
| 文件 | `output/heatmap_sharpe_{symbol}.png` |

**解读模板**（写入 Word）：

> 图2 展示了 {name_zh} 在不同入场通道周期与退出通道周期组合下的夏普比率分布。颜色越绿表示风险调整后收益越好。可见最优区域集中在 entry={best_entry}、exit={best_exit}，Sharpe 达 {best_sharpe}，说明该标的在 {趋势特征描述} 阶段更适合 {短/长} 周期突破策略。

### 3.3 最优参数摘要

脚本结束时打印并写入 `output/best_params.json`：

```json
{
  "002202": {
    "best_entry": 10,
    "best_exit": 5,
    "best_atr": 30,
    "sharpe_ratio": 1.3145,
    "annualized_return": 17.89
  }
}
```

### 3.4 五股横向对比表

生成 Markdown / DataFrame：

| 标的 | 默认参数 Sharpe | 最优 Sharpe | 最优 entry/exit | 年化收益 | 最大回撤 |
|------|----------------|-------------|-----------------|----------|----------|
| 金风科技 | ... | ... | ... | ... | ... |
| ... | | | | | |

### 3.5 信号可视化（图1）

**图表规格**：

| 属性 | 值 |
|------|-----|
| 图类型 | Matplotlib 双子图 |
| 标题 | `图1 {name_zh} 海龟策略 — 价格、唐奇安通道与交易信号` |
| 上图 | 收盘价 + entry_high（红虚线）+ exit_low（绿虚线） |
| 标记 | 买入 ▲ 绿色；卖出 ▼ 红色 |
| 下图 | ATR 曲线 + 止损线（持仓期间） |
| 文件 | `output/signals_{symbol}.png` |

### 3.6 净值曲线（图3）

| 属性 | 值 |
|------|-----|
| 标题 | `图3 {name_zh} 策略净值 vs 买入持有基准` |
| 线 | 策略净值（红）、基准（蓝） |
| 文件 | `output/equity_curve_{symbol}.png` |

---

## 4. CLI 接口

```bash
# 全量分析（五股 + 热力图 + 对比表）
python dashboard/build_dashboard.py

# 单标的
python dashboard/build_dashboard.py --symbol 002202

# 自定义网格
python dashboard/build_dashboard.py --entry 10,20,30,55,60 --exit 5,10,20

# 仅输出 JSON（供 Playground 预计算）
python dashboard/build_dashboard.py --json-only
```

---

## 5. Notebook 集成

`notebooks/turtle_strategy_backtest.ipynb` 第 8 节直接调用：

```python
from dashboard.build_dashboard import run_grid_search, plot_heatmap

grid_df = run_grid_search("002202")
fig = plot_heatmap(grid_df, title="图2 金风科技 参数敏感性热力图")
```

---

## 6. Word 报告生成（TASK4）

脚本 `generate_task4_report.py` 读取 Dashboard 输出，生成 `姓名+TASK4.docx`：

**格式要求**（作业规范）：

- 字体：宋体
- 字号：五号（10.5pt）
- 行距：1.5 倍
- 段间距：0 磅
- 对齐：两端对齐
- 图表：带图号与标题，每图附解读段落

**报告章节**：

1. 海龟策略核心思想与优势
2. 唐奇安通道、ATR、止损概念解释
3. 数据与实现说明
4. 图1 信号图 + 解读
5. 图2 热力图 + 解读
6. 图3 净值曲线 + 解读
7. 五股对比表 + 解读
8. 参数调节实验与心得
9. Playground 看板说明（附链接）

---

## 7. 验收标准

- [ ] `build_dashboard.py` 一键运行无报错
- [ ] 每只股票生成 heatmap PNG，色阶与数值标注正确
- [ ] `best_params.json` 与热力图最优格一致
- [ ] 图1/图2/图3 均有图号标题
- [ ] 五股对比表含默认参数与最优参数两行
- [ ] 输出 CSV 可被 Notebook 复用

---

## 8. 性能

- 单标的 6×4=24 组参数：< 5 秒
- 五标的全网格：< 30 秒
- 图表生成：< 10 秒
