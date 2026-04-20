# TCA Framework for SA Intraday CTA

## 1. Objective

For single-instrument commodity futures intraday CTA, TCA is used to measure and improve best execution quality. The implementation follows a three-stage framework:

- Pre-trade analysis
- Intra-day real-time analysis
- Post-trade analysis

Data used:

- 1-minute bars: volatility and timing-risk context
- L1 ticks: spread, depth proxy, VWAP, RPM, fill-quality benchmarks

## 2. Stage A: Pre-trade Analysis

### 2.1 Inputs

- orders table (order timestamp, side, quantity, signal reference price)
- min1 bars
- tick stream

### 2.2 Metrics

For each order:

- spread_bp_est
  - estimated spread in bps from nearby tick window
- market_impact_est_bps
  - quantity vs depth proxy estimate
- timing_risk_bps
  - recent 1-minute volatility scaled to execution horizon
- predicted_total_cost_bps
  - synthetic pre-trade cost forecast
- recommended_algo
  - POV / VWAP / PASSIVE_LIMIT / ACTIVE_LIMIT according to risk and liquidity

### 2.3 Why it matters

- Select execution style before sending orders
- Anticipate cost and urgency

## 3. Stage B: Intra-day Analysis

### 3.1 Inputs

- fills
- ticks
- min1 bars

### 3.2 Monitoring Dimensions

Minute-level panel:

- spread_bp_median
- depth_proxy
- bar_abs_return_bp
- arrival_cost_bps
- total_cost
- adaptive_action
  - NORMAL / MONITOR / SLOW_DOWN / SLOW_OR_PAUSE

### 3.3 Adaptive Actions

Rules trigger under:

- spread widening
- depth deterioration
- volatility spike
- abnormal arrival slippage

This supports dynamic throttling or temporary pause decisions.

## 4. Stage C: Post-trade Analysis

## 4.1 Core Cost Metric: Implementation Shortfall (IS)

IS is decomposed order by order:

- Delay Cost
  - signal/decision reference price to arrival price
- Execution Cost
  - arrival price to realized average fill price
- Opportunity Cost
  - unfilled portion cost (zero in full-fill simulation)
- Fixed Fee Cost
  - commission and exchange fees

Total:

$$
IS_{bps} = Delay_{bps} + Execution_{bps} + Opportunity_{bps} + FixedFee_{bps}
$$

## 4.2 Benchmarks

- Arrival benchmark:
$$
Arrival\ Cost_{bp} = Side \times \frac{P_{avg} - P_0}{P_0} \times 10000
$$

- VWAP benchmark (interval)
  - compare fill price to tick-based interval VWAP

- RPM (Relative Performance Measure)
  - percentile quality against market trades in local tick window
  - higher than 50 indicates better-than-median execution quality

- Z-score (risk-adjusted execution score)
$$
Z = \frac{PredictedCost_{bps} - ActualIS_{bps}}{TimingRisk_{bps}}
$$

## 5. Output Tables

The pipeline writes the following run-scoped TCA tables:

- tca_pre_trade
- tca_intra_day
- tca_post_trade
- tca_summary
- tca_by_hour
- tca_kpis

All tables include run_id when persisted.

## 6. Output Artifacts

Per run_id CSV outputs:

- tca_pre_trade_<run_id>.csv
- tca_intra_day_<run_id>.csv
- tca_post_trade_<run_id>.csv
- tca_summary_<run_id>.csv
- tca_by_hour_<run_id>.csv
- tca_kpis_<run_id>.csv

## 7. GUI Integration

The dashboard visualizes TCA across three tabs:

- Execution cost decomposition by direction
- Arrival cost by hour
- IS decomposition and benchmark panel (RPM vs IS)
- Pre-trade risk-vs-cost scatter
- Intra-day adaptive signal timeline

Branding and visual language follow Renaissance-Technologies styling.

## 8. Current Simulation Assumptions

- Full fill model in backtest execution engine
- Opportunity cost typically 0 under current execution simulator
- Timing risk and impact forecasts are model-based proxies and can be calibrated further

These assumptions are explicit so that production execution integration can replace proxies with real OMS/exchange events later.
