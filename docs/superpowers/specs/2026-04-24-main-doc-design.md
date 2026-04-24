# Main Documentation Spec — SA Intraday CTA System
**Date**: 2026-04-24
**Author**: Sisyphus (via brainstorming session)
**Status**: Approved

## 1. Concept & Vision

Comprehensive bilingual (Chinese/English) technical documentation for the SA Intraday CTA System, designed as both a PPT presentation script and a deep-reference archive document. The doc must serve two audiences simultaneously: technical users who need formulas and code context, and non-technical users who need business logic and chart interpretation guidance.

## 2. Structure

```
docs/MAIN.md
├── 0. 系统概览 / System Overview
│   ├── 合约与品种信息 (SA纯碱) / Contract & Instrument
│   ├── 合约规格参数表 / Contract Specifications
│   └── 手续费与成本结构 / Fee & Cost Structure
├── 1. 系统架构 / Architecture
│   ├── MFE 5210 设计模式总览 / Design Patterns Overview
│   ├── 核心模块依赖关系 / Module Dependencies
│   └── 数据流向 / Data Flow
├── 2. 设计模式 / Design Patterns
│   ├── Template Method (pipeline.py) / pipeline.py
│   ├── Protocol (contracts.py) / contracts.py
│   ├── Factory (factory.py) / factory.py
│   └── Facade (facade.py) / facade.py
├── 3. 策略逻辑 / Strategy Logic
│   ├── DualThrust 算法详解 / DualThrust Algorithm
│   ├── 参数配置表 / Parameter Table
│   └── 信号生成示例 / Signal Generation Example
├── 4. 订单管理 / Order Management
│   ├── TickExecutionSimulator 执行引擎 / Execution Engine
│   ├── 成本分解公式 / Cost Formulas
│   └── 订单状态机 / Order State Machine
├── 5. 回测引擎 / Backtest Engine
│   ├── 事件驱动架构 / Event-Driven Architecture
│   ├── 信号触发订单流程 / Signal-to-Order Flow
│   ├── 心跳机制 / Heartbeat Mechanism
│   └── 风控规则 / Risk Controls
├── 6. TCA 分析框架 / TCA Framework
│   ├── Pre-trade 预测 / Pre-trade Predictions
│   ├── Intra-day 自适应信号 / Intra-day Adaptive Signals
│   └── Post-trade IS 分解 / Post-trade IS Decomposition
└── 7. GUI 图表说明 / GUI Charts Reference
    ├── Strategy & Risk Tab
    ├── Execution & TCA Tab
    ├── Pre/Intra Trade Tab
    └── TCA Metrics Tab
```

## 3. Content Standards

- Every section has Chinese heading first, then English: `## 3.1 双子 Thrust 策略 / DualThrust Strategy`
- Parameter tables with columns: 参数名 / Parameter | 默认值 / Default | 来源 / Source | 说明 / Description
- Formulas in `code blocks` with Chinese explanation inline
- Each GUI chart: 数据源 / Data Source (SQL table + columns), 含义 / Meaning, 解读角度 / Interpretation
- Code snippets for critical logic (IS decomposition, signal generation)

## 4. Key Facts to Include

### Contract (SA 纯碱 / Soda Ash)
- Exchange: CZCE (郑州商品交易所)
- Contract multiplier: 20 tons/手
- Tick size: 1 CNY/ton
- Fee rate: 0.0002 (万2)
- Slippage: 1 tick

### Strategy: DualThrust
- lookback_days: 3
- k1: 0.4 (default), configurable
- k2: 0.4 (default), configurable
- max_hold_bars: 20

### TCA Stages
- Pre-trade: spread_bp_est, market_impact_est_bps, timing_risk_bps, predicted_total_cost_bps, recommended_algo
- Intra-day: arrival_cost_bps, spread_bp_median, depth_proxy, adaptive_action (NORMAL/SLOW_OR_PAUSE/SLOW_DOWN/MONITOR)
- Post-trade: delay_cost_bps, execution_cost_bps, fixed_fee_bps, opportunity_cost_bps, implementation_shortfall_bps, rpm, tca_zscore

### GUI Tabs
- Strategy & Risk: equity_curve, drawdown_curve, position_curve, daily_pnl
- Execution & TCA: tca_cost, arrival_by_hour, is_decomposition, benchmark_panel
- Pre/Intra Trade: pretrade_panel, intraday_panel, execution_flow
- TCA Metrics: cost_by_direction, predicted_vs_actual, rpm_dist, zscore_dist, tca_kpis_table

## 5. Self-Review Checklist

- [x] All 7 sections present with adequate depth
- [x] Bilingual format applied (Chinese first, English second)
- [x] Parameter tables for key configs
- [x] Formula code blocks for TCA and execution costs
- [x] All 14+ GUI charts documented with data sources and meanings
- [x] No TBD/TODO placeholders
- [x] No contradictory information
- [x] Scope: comprehensive but single-doc (no decomposition needed)