from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


def _empty_tca_report() -> Dict[str, pd.DataFrame]:
    empty = pd.DataFrame()
    return {
        "summary": empty,
        "by_hour": empty,
        "pre_trade": empty,
        "intra_day": empty,
        "post_trade": empty,
        "kpis": empty,
    }


def _safe_div(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    den = denominator.replace(0.0, np.nan)
    return (numerator / den).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def _prepare_orders(orders_df: pd.DataFrame) -> pd.DataFrame:
    if orders_df.empty:
        return pd.DataFrame()

    orders = orders_df.copy()
    if "order_id" not in orders.columns:
        orders = orders.reset_index(drop=True)
        orders.insert(0, "order_id", range(1, len(orders) + 1))

    orders["ts"] = pd.to_datetime(orders["ts"])
    orders["trade_day"] = orders["trade_day"].astype(str)

    side_raw = orders["side"].astype(str).str.upper()
    orders["side_sign"] = np.where(side_raw.str.startswith("B"), 1.0, -1.0)
    orders["qty"] = pd.to_numeric(orders["qty"], errors="coerce").fillna(0.0).abs()
    orders["decision_price"] = pd.to_numeric(orders.get("close", 0.0), errors="coerce").fillna(0.0)
    return orders


def _prepare_ticks(ticks_df: pd.DataFrame) -> pd.DataFrame:
    if ticks_df.empty:
        return pd.DataFrame()

    ticks = ticks_df.copy()
    ticks["ts"] = pd.to_datetime(ticks["ts"])
    if "trade_day" in ticks.columns:
        ticks["trade_day"] = ticks["trade_day"].astype(str)
    else:
        ticks["trade_day"] = ticks["ts"].dt.strftime("%Y%m%d")

    ticks["price"] = pd.to_numeric(ticks.get("price", 0.0), errors="coerce").fillna(0.0)
    ticks["bid_price_0"] = pd.to_numeric(ticks.get("bid_price_0", ticks["price"]), errors="coerce").fillna(ticks["price"])
    ticks["ask_price_0"] = pd.to_numeric(ticks.get("ask_price_0", ticks["price"]), errors="coerce").fillna(ticks["price"])
    ticks["volume"] = pd.to_numeric(ticks.get("volume", 1.0), errors="coerce").fillna(1.0).clip(lower=1.0)

    mid = ((ticks["bid_price_0"] + ticks["ask_price_0"]) / 2.0).replace(0.0, np.nan)
    spread = (ticks["ask_price_0"] - ticks["bid_price_0"]).clip(lower=0.0)
    ticks["spread_bp"] = _safe_div(spread, mid) * 10000.0
    return ticks


def _prepare_min1(min1_df: pd.DataFrame) -> pd.DataFrame:
    if min1_df.empty:
        return pd.DataFrame()

    bars = min1_df.copy()
    bars["ts"] = pd.to_datetime(bars["ts"])
    bars["trade_day"] = bars["trade_day"].astype(str)
    bars["close"] = pd.to_numeric(bars.get("close", 0.0), errors="coerce").fillna(0.0)
    return bars


def _build_pre_trade(orders: pd.DataFrame, bars: pd.DataFrame, ticks: pd.DataFrame) -> pd.DataFrame:
    if orders.empty:
        return pd.DataFrame()

    records = []
    for row in orders.itertuples(index=False):
        ts = pd.Timestamp(row.ts)
        day = str(row.trade_day)

        ticks_day = ticks[ticks["trade_day"] == day] if not ticks.empty else pd.DataFrame()
        ticks_win = ticks_day[(ticks_day["ts"] >= ts - pd.Timedelta(minutes=5)) & (ticks_day["ts"] <= ts + pd.Timedelta(minutes=5))]
        if ticks_win.empty:
            ticks_win = ticks_day

        spread_bp_est = float(ticks_win["spread_bp"].median()) if not ticks_win.empty else 0.0
        depth_proxy = float(ticks_win["volume"].median()) if not ticks_win.empty else 1.0
        impact_est_bps = float(abs(float(row.qty)) / max(depth_proxy, 1.0) * 5.0)

        bars_day = bars[bars["trade_day"] == day] if not bars.empty else pd.DataFrame()
        bars_hist = bars_day[bars_day["ts"] <= ts].tail(30)
        if len(bars_hist) > 2:
            ret = bars_hist["close"].pct_change().dropna()
            timing_risk_bps = float(ret.std(ddof=0) * np.sqrt(30.0) * 10000.0)
        else:
            timing_risk_bps = 0.0

        predicted_total_cost_bps = float(spread_bp_est + impact_est_bps + 0.5 * timing_risk_bps)

        if timing_risk_bps >= 12.0:
            recommended_algo = "POV"
        elif impact_est_bps >= 8.0:
            recommended_algo = "VWAP"
        elif spread_bp_est <= 1.5:
            recommended_algo = "PASSIVE_LIMIT"
        else:
            recommended_algo = "ACTIVE_LIMIT"

        records.append(
            {
                "order_id": int(row.order_id),
                "trade_day": day,
                "decision_ts": ts,
                "side": "buy" if float(row.side_sign) > 0 else "sell",
                "order_qty": float(row.qty),
                "decision_price": float(row.decision_price),
                "spread_bp_est": spread_bp_est,
                "market_impact_est_bps": impact_est_bps,
                "timing_risk_bps": timing_risk_bps,
                "predicted_total_cost_bps": predicted_total_cost_bps,
                "recommended_algo": recommended_algo,
            }
        )

    return pd.DataFrame(records)


def _build_intra_day(fills: pd.DataFrame, bars: pd.DataFrame, ticks: pd.DataFrame) -> pd.DataFrame:
    if fills.empty and bars.empty and ticks.empty:
        return pd.DataFrame()

    parts = []

    if not ticks.empty:
        tick_min = ticks.copy()
        tick_min["minute"] = tick_min["ts"].dt.floor("min")
        tick_agg = (
            tick_min.groupby("minute", as_index=False)
            .agg(
                spread_bp_median=("spread_bp", "median"),
                depth_proxy=("volume", "median"),
            )
            .sort_values("minute")
        )
        parts.append(tick_agg)

    if not bars.empty:
        bar_min = bars.copy().sort_values("ts")
        bar_min["minute"] = bar_min["ts"].dt.floor("min")
        bar_agg = bar_min.groupby("minute", as_index=False)["close"].last().sort_values("minute")
        bar_agg["bar_abs_return_bp"] = bar_agg["close"].pct_change().abs().fillna(0.0) * 10000.0
        bar_agg = bar_agg[["minute", "bar_abs_return_bp"]]
        parts.append(bar_agg)

    if not fills.empty:
        fill_min = fills.copy()
        fill_min["minute"] = fill_min["ts"].dt.floor("min")
        fill_agg = (
            fill_min.groupby("minute", as_index=False)
            .agg(
                fill_count=("qty", "count"),
                arrival_cost_bps=("arrival_cost_bps", "mean"),
                total_cost=("total_cost", "sum"),
            )
            .sort_values("minute")
        )
        parts.append(fill_agg)

    merged = None
    for part in parts:
        if merged is None:
            merged = part
        else:
            merged = merged.merge(part, on="minute", how="outer")

    if merged is None or merged.empty:
        return pd.DataFrame()

    merged = merged.sort_values("minute").reset_index(drop=True)
    numeric_defaults = {
        "fill_count": 0.0,
        "arrival_cost_bps": 0.0,
        "total_cost": 0.0,
        "spread_bp_median": 0.0,
        "depth_proxy": 0.0,
        "bar_abs_return_bp": 0.0,
    }
    for col, default_val in numeric_defaults.items():
        if col not in merged.columns:
            merged[col] = default_val
        merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(default_val)

    depth_q25 = float(merged["depth_proxy"].replace(0.0, np.nan).quantile(0.25)) if not merged.empty else 0.0
    spread_q75 = float(merged["spread_bp_median"].quantile(0.75)) if not merged.empty else 0.0
    vol_q75 = float(merged["bar_abs_return_bp"].quantile(0.75)) if not merged.empty else 0.0

    merged["adaptive_action"] = "NORMAL"
    merged.loc[(merged["depth_proxy"] > 0.0) & (merged["depth_proxy"] <= depth_q25), "adaptive_action"] = "SLOW_OR_PAUSE"
    merged.loc[merged["spread_bp_median"] >= spread_q75 * 1.5, "adaptive_action"] = "SLOW_OR_PAUSE"
    merged.loc[merged["bar_abs_return_bp"] >= vol_q75, "adaptive_action"] = "SLOW_DOWN"
    merged.loc[merged["arrival_cost_bps"].abs() >= 5.0, "adaptive_action"] = "MONITOR"

    return merged


def _calc_vwap_and_rpm(ts: pd.Timestamp, day: str, side_sign: float, fill_price: float, ticks: pd.DataFrame) -> Dict[str, float]:
    if ticks.empty:
        return {"interval_vwap": float(fill_price), "vwap_cost_bps": 0.0, "rpm": 50.0}

    ticks_day = ticks[ticks["trade_day"] == str(day)]
    window = ticks_day[(ticks_day["ts"] >= ts - pd.Timedelta(minutes=5)) & (ticks_day["ts"] <= ts + pd.Timedelta(minutes=5))]
    if window.empty:
        window = ticks_day

    if window.empty:
        return {"interval_vwap": float(fill_price), "vwap_cost_bps": 0.0, "rpm": 50.0}

    weights = window["volume"].astype(float).clip(lower=1.0)
    interval_vwap = float(np.average(window["price"].astype(float), weights=weights))

    vwap_cost_bps = float(side_sign * (float(fill_price) - interval_vwap) / max(interval_vwap, 1e-12) * 10000.0)
    if side_sign > 0:
        rpm = float((window["price"].astype(float) >= float(fill_price)).mean() * 100.0)
    else:
        rpm = float((window["price"].astype(float) <= float(fill_price)).mean() * 100.0)

    return {
        "interval_vwap": interval_vwap,
        "vwap_cost_bps": vwap_cost_bps,
        "rpm": rpm,
    }


def _build_post_trade(
    fills: pd.DataFrame,
    orders: pd.DataFrame,
    ticks: pd.DataFrame,
    pre_trade: pd.DataFrame,
    contract_multiplier: float,
) -> pd.DataFrame:
    if fills.empty:
        return pd.DataFrame()

    working = fills.copy()
    working["trade_day"] = working["trade_day"].astype(str)
    working["decision_ts"] = pd.to_datetime(working["decision_ts"])
    working["side_sign"] = np.sign(working["side"].astype(float)).replace(0.0, 1.0)
    working["abs_qty"] = working["qty"].astype(float).abs()

    working["w_fill"] = working["fill_price"].astype(float) * working["abs_qty"]
    working["w_arrival"] = working["arrival_price"].astype(float) * working["abs_qty"]
    working["w_decision"] = working["decision_price"].astype(float) * working["abs_qty"]

    grouped = (
        working.groupby(["trade_day", "decision_ts", "side_sign"], as_index=False)
        .agg(
            fill_count=("qty", "count"),
            filled_qty=("abs_qty", "sum"),
            w_fill=("w_fill", "sum"),
            w_arrival=("w_arrival", "sum"),
            w_decision=("w_decision", "sum"),
            total_fee=("fee", "sum"),
            total_spread_cost=("spread_cost", "sum"),
            total_slippage_cost=("slippage_cost", "sum"),
            total_impact_cost=("impact_cost", "sum"),
            total_cost=("total_cost", "sum"),
        )
        .sort_values(["trade_day", "decision_ts"])
        .reset_index(drop=True)
    )

    grouped["avg_fill_price"] = _safe_div(grouped["w_fill"], grouped["filled_qty"])
    grouped["avg_arrival_price"] = _safe_div(grouped["w_arrival"], grouped["filled_qty"])
    grouped["avg_decision_price"] = _safe_div(grouped["w_decision"], grouped["filled_qty"])

    if not orders.empty:
        order_ref = orders.copy()
        order_ref = order_ref.rename(columns={"ts": "decision_ts", "qty": "order_qty", "decision_price": "signal_price"})
        order_ref = order_ref[["order_id", "trade_day", "decision_ts", "side_sign", "order_qty", "signal_price"]]
        order_ref = order_ref.drop_duplicates(subset=["trade_day", "decision_ts", "side_sign"], keep="last")
        grouped = grouped.merge(order_ref, on=["trade_day", "decision_ts", "side_sign"], how="left")
    else:
        grouped["order_id"] = np.nan
        grouped["order_qty"] = grouped["filled_qty"]
        grouped["signal_price"] = grouped["avg_decision_price"]

    grouped["decision_price_ref"] = grouped["signal_price"].fillna(grouped["avg_decision_price"]).replace(0.0, np.nan)
    grouped["decision_price_ref"] = grouped["decision_price_ref"].fillna(grouped["avg_arrival_price"])

    side = grouped["side_sign"].astype(float)
    grouped["delay_cost_bps"] = side * _safe_div(
        grouped["avg_arrival_price"] - grouped["decision_price_ref"],
        grouped["decision_price_ref"],
    ) * 10000.0
    grouped["execution_cost_bps"] = side * _safe_div(
        grouped["avg_fill_price"] - grouped["avg_arrival_price"],
        grouped["avg_arrival_price"],
    ) * 10000.0

    notional = grouped["filled_qty"].astype(float) * grouped["avg_arrival_price"].astype(float) * float(contract_multiplier)
    grouped["fixed_fee_bps"] = _safe_div(grouped["total_fee"].astype(float), notional) * 10000.0

    grouped["order_qty"] = pd.to_numeric(grouped["order_qty"], errors="coerce").fillna(grouped["filled_qty"])
    grouped["unfilled_qty"] = (grouped["order_qty"] - grouped["filled_qty"]).clip(lower=0.0)
    grouped["opportunity_cost_bps"] = 0.0

    grouped["implementation_shortfall_bps"] = (
        grouped["delay_cost_bps"]
        + grouped["execution_cost_bps"]
        + grouped["fixed_fee_bps"]
        + grouped["opportunity_cost_bps"]
    )

    bench_records = []
    for row in grouped.itertuples(index=False):
        bench_records.append(
            _calc_vwap_and_rpm(
                ts=pd.Timestamp(row.decision_ts),
                day=str(row.trade_day),
                side_sign=float(row.side_sign),
                fill_price=float(row.avg_fill_price),
                ticks=ticks,
            )
        )
    bench_df = pd.DataFrame(bench_records)
    grouped = pd.concat([grouped.reset_index(drop=True), bench_df], axis=1)

    grouped["direction"] = np.where(grouped["side_sign"] > 0.0, "buy", "sell")

    if not pre_trade.empty:
        pre_cols = ["order_id", "timing_risk_bps", "predicted_total_cost_bps"]
        grouped = grouped.merge(pre_trade[pre_cols], on="order_id", how="left")
    else:
        grouped["timing_risk_bps"] = 0.0
        grouped["predicted_total_cost_bps"] = 0.0

    grouped["timing_risk_bps"] = pd.to_numeric(grouped["timing_risk_bps"], errors="coerce").fillna(0.0)
    grouped["predicted_total_cost_bps"] = pd.to_numeric(grouped["predicted_total_cost_bps"], errors="coerce").fillna(0.0)
    grouped["tca_zscore"] = _safe_div(
        grouped["predicted_total_cost_bps"] - grouped["implementation_shortfall_bps"],
        grouped["timing_risk_bps"],
    )

    return grouped[
        [
            "order_id",
            "trade_day",
            "decision_ts",
            "direction",
            "filled_qty",
            "unfilled_qty",
            "avg_fill_price",
            "avg_arrival_price",
            "decision_price_ref",
            "delay_cost_bps",
            "execution_cost_bps",
            "fixed_fee_bps",
            "opportunity_cost_bps",
            "implementation_shortfall_bps",
            "interval_vwap",
            "vwap_cost_bps",
            "rpm",
            "predicted_total_cost_bps",
            "timing_risk_bps",
            "tca_zscore",
            "total_cost",
            "total_spread_cost",
            "total_slippage_cost",
            "total_impact_cost",
            "total_fee",
        ]
    ]


def build_tca_report(
    fills_df: pd.DataFrame,
    orders_df: pd.DataFrame,
    min1_df: pd.DataFrame,
    ticks_df: pd.DataFrame,
    contract_multiplier: float = 1.0,
) -> Dict[str, pd.DataFrame]:
    orders = _prepare_orders(orders_df)
    ticks = _prepare_ticks(ticks_df)
    bars = _prepare_min1(min1_df)

    pre_trade = _build_pre_trade(orders=orders, bars=bars, ticks=ticks)

    if fills_df.empty:
        intra_day = _build_intra_day(fills=pd.DataFrame(), bars=bars, ticks=ticks)
        kpis = pd.DataFrame(
            [
                {
                    "fills": 0,
                    "arrival_cost_bps_mean": 0.0,
                    "arrival_cost_bps_std": 0.0,
                    "implementation_shortfall_bps_mean": 0.0,
                    "vwap_cost_bps_mean": 0.0,
                    "rpm_mean": 50.0,
                    "timing_risk_bps_mean": float(pre_trade["timing_risk_bps"].mean()) if not pre_trade.empty else 0.0,
                    "predicted_total_cost_bps_mean": float(pre_trade["predicted_total_cost_bps"].mean()) if not pre_trade.empty else 0.0,
                    "z_score_mean": 0.0,
                }
            ]
        )
        return {
            "summary": pd.DataFrame(),
            "by_hour": pd.DataFrame(),
            "pre_trade": pre_trade,
            "intra_day": intra_day,
            "post_trade": pd.DataFrame(),
            "kpis": kpis,
        }

    fills = fills_df.copy()
    fills["ts"] = pd.to_datetime(fills["ts"])
    fills["decision_ts"] = pd.to_datetime(fills["decision_ts"])
    fills["side"] = fills["side"].astype(float)
    fills["trade_day"] = fills["ts"].dt.strftime("%Y%m%d") if "trade_day" not in fills.columns else fills["trade_day"].astype(str)

    signed_slippage_px = (fills["fill_price"] - fills["arrival_price"]) * fills["side"]
    fills["arrival_cost_bps"] = _safe_div(signed_slippage_px, fills["arrival_price"].replace(0.0, np.nan)) * 10000.0
    fills["direction"] = np.where(fills["side"] > 0.0, "buy", "sell")
    fills["hour"] = fills["ts"].dt.hour

    summary = (
        fills.groupby("direction", as_index=False)
        .agg(
            fill_count=("qty", "count"),
            avg_arrival_cost_bps=("arrival_cost_bps", "mean"),
            total_spread_cost=("spread_cost", "sum"),
            total_slippage_cost=("slippage_cost", "sum"),
            total_impact_cost=("impact_cost", "sum"),
            total_fee=("fee", "sum"),
            total_cost=("total_cost", "sum"),
        )
        .sort_values("direction")
        .reset_index(drop=True)
    )

    by_hour = (
        fills.groupby("hour", as_index=False)
        .agg(
            fill_count=("qty", "count"),
            avg_arrival_cost_bps=("arrival_cost_bps", "mean"),
            total_cost=("total_cost", "sum"),
            avg_spread_cost=("spread_cost", "mean"),
            avg_slippage_cost=("slippage_cost", "mean"),
            avg_impact_cost=("impact_cost", "mean"),
        )
        .sort_values("hour")
        .reset_index(drop=True)
    )

    intra_day = _build_intra_day(fills=fills, bars=bars, ticks=ticks)
    post_trade = _build_post_trade(
        fills=fills,
        orders=orders,
        ticks=ticks,
        pre_trade=pre_trade,
        contract_multiplier=float(contract_multiplier),
    )

    if not post_trade.empty:
        direction_post = (
            post_trade.groupby("direction", as_index=False)
            .agg(
                avg_is_bps=("implementation_shortfall_bps", "mean"),
                avg_vwap_cost_bps=("vwap_cost_bps", "mean"),
                avg_rpm=("rpm", "mean"),
                avg_zscore=("tca_zscore", "mean"),
            )
            .sort_values("direction")
        )
        summary = summary.merge(direction_post, on="direction", how="left")

    kpis = pd.DataFrame(
        [
            {
                "fills": int(len(fills)),
                "arrival_cost_bps_mean": float(fills["arrival_cost_bps"].mean()),
                "arrival_cost_bps_std": float(fills["arrival_cost_bps"].std(ddof=0)) if len(fills) > 1 else 0.0,
                "implementation_shortfall_bps_mean": float(post_trade["implementation_shortfall_bps"].mean()) if not post_trade.empty else 0.0,
                "vwap_cost_bps_mean": float(post_trade["vwap_cost_bps"].mean()) if not post_trade.empty else 0.0,
                "rpm_mean": float(post_trade["rpm"].mean()) if not post_trade.empty else 50.0,
                "timing_risk_bps_mean": float(pre_trade["timing_risk_bps"].mean()) if not pre_trade.empty else 0.0,
                "predicted_total_cost_bps_mean": float(pre_trade["predicted_total_cost_bps"].mean()) if not pre_trade.empty else 0.0,
                "z_score_mean": float(post_trade["tca_zscore"].mean()) if not post_trade.empty else 0.0,
            }
        ]
    )

    return {
        "summary": summary,
        "by_hour": by_hour,
        "pre_trade": pre_trade,
        "intra_day": intra_day,
        "post_trade": post_trade,
        "kpis": kpis,
    }
