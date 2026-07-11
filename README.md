# turtle-quant-strategy

海龟交易法则（Turtle Trading）回测与分析项目（TASK4）。

## 功能概览

- **策略引擎**：唐奇安通道突破 + ATR 止损
- **Notebook**：取数 → 指标 → 信号 → 回测 → 热力图 全流程
- **Dashboard**：参数敏感性分析（Sharpe 热力图）
- **Playground**：浏览器交互式回测看板
- **CI**：GitHub Actions 工作日自动更新行情数据

## 标的（与 quant-strategy 一致）

| 代码 | 名称 |
|------|------|
| 002202.SZ | 金风科技 |
| 600031.SH | 三一重工 |
| 000425.SZ | 徐工机械 |
| 600207.SH | 安彩高科 |
| 000816.SZ | 智慧农业 |

## Spec 文档

| 文件 | 说明 |
|------|------|
| [spec_turtle_strategy.md](spec_turtle_strategy.md) | 策略定义、指标公式、回测规范 |
| [spec_dashboard.md](spec_dashboard.md) | 静态分析看板与热力图 |
| [spec_playground.md](spec_playground.md) | 交互式 Playground 与 CI 部署 |

## 快速开始（实现后）

```bash
pip install -r requirements.txt
python src/data_fetch.py
python dashboard/build_dashboard.py
python playground/build_playground.py
jupyter notebook notebooks/turtle_strategy_backtest.ipynb
python generate_task4_report.py
```

## 在线地址（部署后）

- 仓库：https://github.com/wangmx816/turtle-quant-strategy
- Playground：https://wangmx816.github.io/turtle-quant-strategy/

## 目录结构（规划）

```
turtle-quant-strategy/
├── spec_turtle_strategy.md
├── spec_dashboard.md
├── spec_playground.md
├── src/                     # 策略核心
├── notebooks/               # Jupyter 分析
├── dashboard/               # 热力图与静态报告
├── playground/              # 交互看板
├── data/                    # 日线 CSV
├── output/                  # 图表与 JSON
└── .github/workflows/       # 每日数据更新
```

## 参考

- 上游数据与回测框架：[quant-strategy](https://github.com/wangmx816/quant-strategy)
- Playground 参考：[turtle-strategy-playground](https://waanng.github.io/turtle-strategy-playground/)
