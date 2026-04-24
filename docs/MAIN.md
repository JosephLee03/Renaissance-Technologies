# SA Intraday CTA System — Main Documentation
# SA 日内 CTA 交易系统 — 主文档

**Version**: 2026.04.24 | **Contract**: CZCE SA (纯碱/Soda Ash) | **Holding Period**: Intraday (< 1 day)
**版本**: 2026.04.24 | **合约**: 郑商所 SA (纯碱) | **持仓周期**: 日内 (< 1天)

---

## 0. 系统概览 / System Overview

### 0.1 合约与品种信息 / Contract & Instrument

SA（纯碱，Soda Ash）是郑商所（CZCE）上市的化工品种，本系统以 **SA 主力合约**为交易标的。

| 项目 / Item | 说明 / Description |
|---|---|
| 交易所 / Exchange | CZCE（郑州商品交易所） |
| 品种代码 / Symbol | SA |
| 品种名称 / Name | 纯碱（Soda Ash） |
| 合约乘数 / Contract Multiplier | **20 吨/手** |
| 最小变动 / Tick Size | **1 元/吨** |
| 保证金 / Margin | 参考交易所标准 / Exchange standard |
| 持��限制 / Position Limit | 日内策略，最大仓位 1 手 / Intraday, max 1 lot |

### 0.2 手续费与滑点结构 / Fee & Slippage Structure

每笔交易的实际成本由以下四部分组成：

| 成本项 / Cost Component | 计算方式 / Formula | 默认值 / Default |
|---|---|---|
| 手续费 / Fee | `abs(qty) × fill_price × contract_multiplier × fee_rate` | `fee_rate = 0.0002` (万2) |
| 价差成本 / Spread Cost | `abs(qty) × 0.5 × spread × contract_multiplier` | `spread = max(ask - bid, tick_size)` |
| 滑点成本 / Slippage Cost | `abs(qty) × slippage_ticks × tick_size × contract_multiplier` | `slippage_ticks = 1.0` |
| 市场冲击成本 / Market Impact | `abs(qty) × abs(impact_px) × contract_multiplier` | `impact_px = impact_coeff × abs(qty) / volume × tick_size`, `impact_coeff = 0.2` |

**总成本 / Total Cost = Fee + Spread Cost + Slippage Cost + Market Impact**

> 示例：一笔成交 10 手、成交价 2000 元的交易：
> `fee = 10 × 2000 × 20 × 0.0002 = 80 元`
> `spread_cost = 10 × 0.5 × 1 × 20 = 100 元`
> `slippage_cost = 10 × 1 × 1 × 20 = 200 元`
> `impact_cost ≈ 10 × 0.2 × 10 / 1000 × 1 × 20 ≈ 4 元`
> **合计 ≈ 384 元**

---

## 1. 系统架构 / Architecture

### 1.1 架构总览 / Architecture Overview

本系统遵循 **MFE 5210 设计原则**（量化金融工程标准），采用四层分层架构：

```
┌──────────────────────────────────────────────┐
│          入口 Entry (scripts/run_pipeline.py) │
└──────────────────────┬───────────────────────┘
                       ↓
┌──────────────────────────────────────────────┐
│              Facade (facade.py)              │
│          run_pipeline() 统一入口点            │
└──────────────────────┬───────────────────────┘
                       ↓
┌──────────────────────────────────────────────┐
│         Template (pipeline.py)               │
│     IntradayPipeline — 定义执行步骤骨架       │
└──────────────────────┬───────────────────────┘
                       ↓
┌──────────────────────────────────────────────┐
│         Factory (factory.py)                  │
│   CTAComponentFactory — 创建信号/回测/TCA 等   │
└──────────────────────┬───────────────────────┘
                       ↓
┌──────────────────────────────────────────────┐
│              Core Engines                     │
│  signal.py | backtest.py | execution.py      │
│  tca.py | metrics.py | storage.py             │
└──────────────────────────────────────────────┘
```

### 1.2 数据流向 / Data Flow

```
数据加载 (min1 bars + tick data)
        ↓
信号生成 (DualThrust Signal)
        ↓
回测引擎 (Event-driven Fill Simulation)
        ↓
TCA 分析 (Pre-trade → Intra-day → Post-trade)
        ↓
指标计算 (Metrics)
        ↓
SQLite 持久化 (artifacts/sa_intraday.sqlite)
        ↓
GUI 可视化 (Dash Dashboard)
```

---

## 2. 设计模式 / Design Patterns

### 2.1 模板方法 / Template Method — `pipeline.py`

`IntradayPipeline` 定义了回测的标准化执行骨架，各步骤由子类或工厂实现：

```
run() 流程：
  1. _prepare_context    → 加载配置、构建工厂、发现交易日
  2. _load_data          → 加载 min1 和 tick 数据
  3. _build_signal       → 生成交易信号
  4. _run_backtest       → 运行事件驱动回测
  5. _analyze            → 计算 Metrics + TCA
  6. _persist            → 写入 SQLite
```

每个步骤独立可替换，不影响整体流程。

### 2.2 协议 / Protocol — `contracts.py`

定义组件接口契约（如 `ISignalCalculator`、`ITCAAnalyzer`），确保各模块通过标准接口交互，便于单元测试和模块替换。

### 2.3 工厂 / Factory — `factory.py`

`CTAComponentFactory` 负责创建所有核心组件实例：

- `create_signal()` → DualThrust SignalCalculator
- `create_backtest()` → BacktestEngine
- `create_tca()` → TCAAnalyzer
- `create_metrics()` → MetricsCalculator

### 2.4 门面 / Facade — `facade.py`

`run_pipeline()` 是外部调用的唯一入口，封装了 Pipeline 实例化和执行逻辑。

---

## 3. 策略逻辑 / Strategy Logic

### 3.1 双子 Thrust 算法 / DualThrust Algorithm

双子 Thrust（DualThrust）是一种经典的日内突破型策略，通过前 N 日的价格区间来设定当日日内交易的上下边界。

**算法核心 / Core Algorithm:**

```python
# 1. 计算历史高低 (前 lookback_days 日)
hist_high = max(day_high over lookback_window, shifted by 1 day)
hist_low  = min(day_low over lookback_window, shifted by 1 day)

# 2. 计算区间宽度
dual_thrust_range = max(hist_high - hist_low, 0)

# 3. 计算日内边界
upper = day_open + k1 × dual_thrust_range
lower = day_open - k2 × dual_thrust_range

# 4. 信号逻辑 (在每日 1min bar 上循环)
if pos == 0:                       # 无持仓
    if close >= upper: pos = +1   # 做多
    elif close <= lower: pos = -1  # 做空
elif pos > 0:                       # 持多
    if close <= lower: pos = -1    # 反手做空
elif pos < 0:                       # 持空
    if close >= upper: pos = +1    # 反手做多
if hold_bars >= max_hold_bars: pos = 0  # 超时强制平仓
```

### 3.2 参数配置表 / Parameter Table

| 参数 / Parameter | 默认值 / Default | 配置来源 / Source | 说明 / Description |
|---|---|---|---|
| `lookback_days` | 3 | `config/default.yaml` | 前溯计算区间的高低价天数 |
| `k1` (上轨系数) | 0.4 | `config/default.yaml` | 上轨 = `open + k1 × range` |
| `k2` (下轨系数) | 0.4 | `config/default.yaml` | 下轨 = `open - k2 × range` |
| `max_hold_bars` | 20 | `config/default.yaml` | 最大持仓 bars 数，超限强制平仓 |

**注意 / Note**: k1 和 k2 在 `signal.py` 中实际默认值为 **0.4**，而非配置文件中的 0.4（以代码为准）。`default.yaml` 中的 0.18 是另一个配置示例，实际使用见 `signal.py`。

### 3.3 风控规则 / Risk Rules

| 规则 / Rule | 值 / Value | 说明 / Description |
|---|---|---|
| `max_position` | 1 | 最大同时持仓手数 |
| `max_daily_loss` | 15,000 元 | 当日最大亏损上限，触及后停止交易 |
| `force_flat_time` | 14:55:00 | 强制平仓时间（收盘前 5 分钟） |
| `max_consecutive_losses` | 6 | 最大连续亏损次数，触及后进入冷却 |
| `cooldown_minutes` | 8 | 连续亏损后冷却时间（分钟） |

---

## 4. 订单管理 / Order Management

### 4.1 执行引擎 / Execution Engine — `TickExecutionSimulator`

`execution.py` 中的 `TickExecutionSimulator` 负责在回测中对每个订单进行成交模拟：

```
输入: decision_ts, side, qty, ticks_df, ExecutionConfig
输出: fill_price, total_cost, 以及各成本分项
```

**成交价格计算 / Fill Price Calculation:**

```python
# 1. 获取决策时刻的 bid/ask
decision_price = ticks[decision_ts].close
bid = ticks[decision_ts].bid  # fallback: decision_price - tick_size
ask = ticks[decision_ts].ask   # fallback: decision_price + tick_size
spread = max(ask - bid, tick_size)

# 2. 基础成交价 (base fill price)
if side > 0: base_fill = ask      # 买入 → 成交于 ask
if side < 0: base_fill = bid      # 卖出 → 成交于 bid

# 3. 加入滑点和冲击
impact_ticks = impact_coeff × abs(qty) / volume
impact_px    = impact_ticks × tick_size
fill_price   = base_fill + side × (slippage_ticks × tick_size + impact_px)
```

### 4.2 成本分解公式 / Cost Formulas

| 成本项 / Cost | 公式 / Formula | 说明 / Description |
|---|---|---|
| **Fee** | `abs(qty) × fill_price × contract_multiplier × fee_rate` | 交易所收取手续费 |
| **Spread Cost** | `abs(qty) × 0.5 × spread × contract_multiplier` | bid/ask 价差的理论成本 |
| **Slippage Cost** | `abs(qty) × slippage_ticks × tick_size × contract_multiplier` | 滑点造成的额外损失 |
| **Impact Cost** | `abs(qty) × abs(impact_px) × contract_multiplier` | 大单对市场的冲击成本 |
| **Total Cost** | `fee + spread_cost + slippage_cost + impact_cost` | 全部成本之和 |

---

## 5. 回测引擎 / Backtest Engine

### 5.1 事件驱动架构 / Event-Driven Architecture

回测引擎通过事件钩子（`event_hook`）记录关键事件，供日志和事后分析使用：

| 事件 / Event | 触发时机 / Trigger | 包含数据 / Data |
|---|---|---|
| `backtest_start` | 回测开始 | run_id, 初始权益 |
| `order_fill` | 订单成交 | fill_price, qty, total_cost |
| `trade_closed` | 交易平仓 | entry/exit price, gross/net PnL |
| `day_start` | 交易日开始 | trade_day |
| `day_end` | 交易日结束 | day_pnl, cum_pnl |
| `heartbeat` | 每 N bars | bar_index, ts, position, day_pnl |
| `backtest_end` | 回测结束 | final equity, total return |

### 5.2 信号到订单的流程 / Signal-to-Order Flow

```
signal_df (ts, trade_day, close, target_pos)
        ↓
backtest loop: 比较 target_pos vs current position
        ↓
差异 → 发出 execute_single(qty)
        ↓
TickExecutionSimulator.simulate() 生成成交记录
        ↓
更新 equity_df, fills_df, trades_df
```

**订单处理逻辑 / Order Logic:**

- `pos = 0` → `target_pos ≠ 0`: **开仓** (开仓手数 = abs(target_pos) × 合约乘数)
- `pos ≠ 0` → `target_pos = 0`: **平仓** (全平)
- `pos > 0` → `target_pos < 0`: **先平多，再开空** (两步)
- `pos < 0` → `target_pos > 0`: **先平空，再开多** (两步)
- `pos ≠ 0` → `abs(target_pos) < abs(pos)`: **减仓**

### 5.3 心跳机制 / Heartbeat

当 `heartbeat_bars > 0` 时，回测引擎每经过 `heartbeat_bars` 根 bars 发射一条心跳事件，提供实时进度快照：

```python
# 每 heartbeat_bars 根 bars 发射:
{
    "event": "heartbeat",
    "bar_index": i,
    "ts": ts,
    "trade_day": trade_day,
    "position": current_pos,
    "day_pnl": day_pnl,
    "cum_pnl": cum_pnl
}
```

---

## 6. TCA 分析框架 / TCA Framework

### 6.1 Pre-trade 预测 / Pre-trade Predictions

在订单发出前，基于市场微观结构预测执行成本：

| 指标 / Metric | 公式 / Formula | 说明 / Description |
|---|---|---|
| `spread_bp_est` | `median(spread_bp)` 在决策前 5 分钟 tick 窗口 | 预估价差 (bps) |
| `market_impact_est_bps` | `qty / depth_proxy × impact_scale` | 预估市场冲击 (bps) |
| `timing_risk_bps` | `std(returns) × √30 × 10000` | 时序风险 (bps)，基于 30 分钟年化 |
| `predicted_total_cost_bps` | `spread_bp_est + impact_est + timing_risk_weight × timing_risk_bps` | 预测总成本 |
| `recommended_algo` | 阈值判断 | 推荐算法: DIRECT / VWAP / TWAP / POV |

**算法推荐阈值 / Algo Selection Thresholds:**

```
if timing_risk_bps >= 12 → POV
elif market_impact_est_bps >= 8 → VWAP
elif spread_bp_est >= 3 → TWAP
else → DIRECT
```

### 6.2 Intra-day 自适应信号 / Intra-day Adaptive Signals

基于盘中实时数据，动态调整交易行为：

| 指标 / Metric | 含义 / Meaning |
|---|---|
| `arrival_cost_bps` | `(fill_price - arrival_price) / arrival_price × 10000` 买单为正，卖单为负 |
| `spread_bp_median` | 分钟窗口内 tick spread 中位数 |
| `depth_proxy` | 分钟窗口内交易量中位数（流动性代理） |
| `adaptive_action` | 自适应行为: NORMAL / SLOW_OR_PAUSE / SLOW_DOWN / MONITOR |

**自适应决策规则 / Adaptive Decision Rules:**

```
if depth_proxy > 0 and depth_proxy <= depth_q25 → SLOW_OR_PAUSE
if spread_bp_median >= spread_q75 × 1.5        → SLOW_OR_PAUSE
if bar_abs_return_bp >= vol_q75                  → SLOW_DOWN
if |arrival_cost_bps| >= 5                        → MONITOR
else                                               → NORMAL
```

### 6.3 Post-trade IS 分解 / Post-trade IS Decomposition

每笔订单成交后，计算实现 shortfall（IS）及其各组成部分���

**IS = Delay Cost + Execution Cost + Fixed Fee + Opportunity Cost**

| 成本项 / Component | 公式 / Formula |
|---|---|
| `delay_cost_bps` | `side × (avg_arrival_price - decision_price_ref) / decision_price_ref × 10000` |
| `execution_cost_bps` | `side × (avg_fill_price - avg_arrival_price) / avg_arrival_price × 10000` |
| `fixed_fee_bps` | `(total_fee / notional) × 10000` |
| `opportunity_cost_bps` | 当前版本设为 0（未成交部分的机会成本） |
| `implementation_shortfall_bps` | `delay + execution + fixed_fee + opportunity` |

**Benchmark 指标 / Benchmark Metrics:**

| 指标 / Metric | 含义 / Meaning |
|---|---|
| `vwap_cost_bps` | 相对于 interval VWAP 的成本 |
| `rpm` | Fill price percentile rank (0-100%)，50 = at VWAP |
| `tca_zscore` | `(predicted_cost - actual_IS) / timing_risk` 预测准确性 |

**算法对比模拟 / Algorithm Comparison:**

对每笔订单分别模拟 DIRECT / VWAP / TWAP / POV 四种算法的成本，评估各算法的相对表现。spread factor 参数如下：

| 算法 / Algo | Spread Factor |
|---|---|
| DIRECT | 0.35 |
| VWAP | 0.12 |
| TWAP | 0.15 |
| POV | 0.10 |

---

## 7. GUI 图表说明 / GUI Charts Reference

### 7.1 Strategy & Risk — 策略与风控

**Equity Curve / 权益曲线**
- 数据源 / Data Source: `equity_curve` 表 → `ts`, `equity`
- 含义 / Meaning: 账户权益随时间的增长轨迹，反映策略整体盈利能力
- 解读 / Interpretation: 持续上升为正向策略；观察最大回撤区间

**Drawdown Curve / 回撤曲线**
- 数据源 / Data Source: `equity_curve` 表 → `ts`, `drawdown`
- 含义 / Meaning: 从历史高点的回落幅度
- 解读 / Interpretation: 最大回撤值决定了最坏情况下的风险暴露；结合最大日亏风控参数验证

**Position Timeline / 持仓时间线**
- 数据源 / Data Source: `equity_curve` 表 → `ts`, `position`（采样，每 50 行取 1 条）
- 含义 / Meaning: 策略在每个时间点的多空方向和仓位大小
- 解读 / Interpretation: 确认信号正确驱动仓位变化；观察是否存在不符合策略的持仓

**Daily PnL / 日盈亏柱状图**
- 数据源 / Data Source: `equity_curve` 表 → `trade_day` 分组后 `SUM(pnl_net)`
- 含义 / Meaning: 每个交易日的净盈亏
- 解读 / Interpretation: 胜率、正偏度意味着���向期望；连续亏损触发风控冷却机制

### 7.2 Execution & TCA — 执行与交易成本分析

**TCA Cost Decomposition / TCA 成本分解**
- 数据源 / Data Source: `tca_summary` 表 → `direction`, `total_spread_cost`, `total_slippage_cost`, `total_impact_cost`, `total_fee`
- 含义 / Meaning: 按多空方向分组的各项成本占比
- 解读 / Interpretation: 识别成本最高的组成部分；若 spread_cost 占比过大，考虑调整滑点参数

**Arrival Cost by Hour / 分时到达成本**
- 数据源 / Data Source: `tca_by_hour` 表 → `hour`, `avg_arrival_cost_bps`
- 含义 / Meaning: 每天各小时的平均到达成本（bps）
- 解读 / Interpretation: 某些时段（如开盘/收盘）冲击成本显著更高，验证是否需要调整策略交易时段

**IS Decomposition / IS 分解**
- 数据源 / Data Source: `tca_post_trade` 表 → 均值聚合 `delay_cost_bps`, `execution_cost_bps`, `fixed_fee_bps`, `opportunity_cost_bps`
- 含义 / Meaning: IS 的四个组成部分各自的均值水平（bps）
- 解读 / Interpretation: delay cost 高 → 信号延迟问题；execution cost 高 → 执行效率问题；fee 高 → 手续费优化空间

**Benchmark Panel / 基准面板**
- 数据源 / Data Source: `tca_post_trade` 表 → `rpm` vs `implementation_shortfall_bps`，按 `direction` 着色
- 含义 / Meaning: Fill quality (RPM) vs 实现成本 (IS) 的散点分布
- 解读 / Interpretation: RPM 接近 50% 且 IS 低 → 最佳执行；RPM 偏离 50% 过多需分析原因

### 7.3 Pre/Intra Trade — 盘前盘中分析

**Pre-trade Panel / 盘前预测**
- 数据源 / Data Source: `tca_pre_trade` 表 → `timing_risk_bps`, `predicted_total_cost_bps`，按 `recommended_algo` 着色
- 含义 / Meaning: 订单发出前的成本预测和算法推荐
- 解读 / Interpretation: 验证算法推荐的合理性；成本预测与实际 IS 对比评估预测质量

**Intra-day Panel / 盘中自适应**
- 数据源 / Data Source: `tca_intra_day` 表 → `arrival_cost_bps`（可选叠加 `spread_bp_median`）
- 含义 / Meaning: 盘中实时到达成本变化趋势
- 解读 / Interpretation: 监测实盘中的成本变化，触发 adaptive_action 调整交易行为

**Execution Flow / 执行流向**
- 数据源 / Data Source: `fills` 表（优先）或 `orders` 表 → 按 `hour` 分组 `SUM(total_cost)` 或 `COUNT(qty)`
- 含义 / Meaning: 各小时的总执行成本或订单数量分布
- 解读 / Interpretation: 确认执行集中在预期的日内时段；成本集中时段需重点分析

### 7.4 TCA Metrics — TCA 指标

**Cost by Direction / 分方向成本**
- 数据源 / Data Source: `tca_post_trade` 表 → 按 `direction` 分组 `AVG(implementation_shortfall_bps)`
- 含义 / Meaning: 多空两侧各自的平均 IS（bps）
- 解读 / Interpretation: 若一侧成本显著更高，说明该方向执行难度更大

**Predicted vs Actual Cost / 预测 vs 实际成本**
- 数据源 / Data Source: `tca_post_trade` 表 → `predicted_total_cost_bps` vs `implementation_shortfall_bps`（采样 500 条）
- 含义 / Meaning: 检验盘前成本预测的准确性
- 解读 / Interpretation: 散点接近对角线 → 预测可靠；若系统性偏离 → 需要重新校准模型

**RPM Distribution / RPM 分布**
- 数据源 / Data Source: `tca_post_trade` 表 → `rpm` 分布直方图（20 bins）
- 含义 / Meaning: Fill price ranking 在市场中的百分位分布
- 解读 / Interpretation: 集中于 50% 附近 → 执行中性；若偏移需分析方向性偏差

**Z-Score Distribution / Z-Score 分布**
- 数据源 / Data Source: `tca_post_trade` 表 → `tca_zscore` 分布直方图（20 bins）
- 含义 / Meaning: 预测成本与实际成本偏差的风险标准化量度
- 解读 / Interpretation: 均值接近 0 → 无系统性偏差；均值偏离 → 预测模型方向性错误

**TCA KPIs Table / TCA 关键指标表**
- 数据源 / Data Source: `tca_kpis` 表（最新一行）
- 含义 / Meaning: 综合 TCA 表现摘要：IS、到达成本、RPM、Z-Score 等
- 解读 / Interpretation: 一眼掌握整体执行质量；与基准对比评估改进空间

---

## 附录 A: SQLite 数据库结构 / Appendix A: SQLite Schema

| 表名 / Table | 主要列 / Key Columns | 用途 / Purpose |
|---|---|---|
| `equity_curve` | ts, trade_day, equity, drawdown, position, pnl_net | 权益与持仓历史 |
| `strategy_summary` | trade_day, signal_count, target_pos | 每日信号汇总 |
| `execution_summary` | trade_day, fill_count, total_cost | 每日执行汇总 |
| `tca_summary` | direction, total_spread_cost, total_slippage_cost... | TCA 成本汇总 |
| `tca_by_hour` | hour, avg_arrival_cost_bps | 分时 TCA |
| `tca_pre_trade` | order_id, timing_risk_bps, predicted_total_cost_bps... | 盘前预测 |
| `tca_intra_day` | minute, arrival_cost_bps, adaptive_action... | 盘中自适应 |
| `tca_post_trade` | order_id, delay_cost_bps, execution_cost_bps... | 盘后 IS 分解 |
| `tca_kpis` | fills, arrival_cost_bps_mean, rpm_mean... | TCA 关键指标 |
| `fills` | ts, qty, fill_price, total_cost | 每笔成交明细 |

## 附录 B: 关键配置参数 / Appendix B: Key Configuration

| 配置项 / Config | 路径 / Path | 默认值 / Default |
|---|---|---|
| 策略参数 / Strategy | `strategy.lookback_days` | 3 |
| 策略参数 / Strategy | `strategy.k1` / `strategy.k2` | 0.4 / 0.4 |
| 策略参数 / Strategy | `strategy.max_hold_bars` | 20 |
| 风控 / Risk | `risk.max_position` | 1 |
| 风控 / Risk | `risk.max_daily_loss` | 15,000 |
| 风控 / Risk | `risk.force_flat_time` | "14:55:00" |
| 执行 / Execution | `execution.contract_multiplier` | 20.0 |
| 执行 / Execution | `execution.fee_rate` | 0.0002 |
| 执行 / Execution | `execution.slippage_ticks` | 1.0 |
| 执行 / Execution | `execution.impact_coeff` | 0.2 |
| TCA / TCA | `tca.simulation.direct_spread_factor` | 0.35 |
| TCA / TCA | `tca.pre_trade.impact_scale` | 5.0 |
| TCA / TCA | `tca.pre_trade.timing_risk_weight` | 0.5 |
| 数据 / Data | `data.root` | `data/CZCE/sa` |
| 数据库 / Database | `database.path` | `artifacts/sa_intraday.sqlite` |

---

*Document generated: 2026-04-24 | System Version: 2026.04.24*
*文档生成日期: 2026-04-24 | 系统版本: 2026.04.24*