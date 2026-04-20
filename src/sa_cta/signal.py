from __future__ import annotations

from typing import List

import pandas as pd


def build_dual_thrust_signal_frame(
    min1_df: pd.DataFrame,
    lookback_days: int,
    k1: float,
    k2: float,
    max_hold_bars: int,
) -> pd.DataFrame:
    """Build intraday DualThrust target positions on 1-minute bars.

    The implementation uses previous N trading days to compute a daily breakout range:
    range_t = max(close over history) - min(close over history)
    upper_t = open_t + k1 * range_t
    lower_t = open_t - k2 * range_t
    """
    if min1_df.empty:
        return pd.DataFrame(
            columns=[
                "trade_day",
                "ts",
                "close",
                "day_open",
                "dual_thrust_range",
                "dual_thrust_upper",
                "dual_thrust_lower",
                "target_pos",
            ]
        )

    if lookback_days <= 0:
        raise ValueError(f"lookback_days must be positive, got {lookback_days}")
    hold_limit = max(1, int(max_hold_bars))

    bars = min1_df[["trade_day", "ts", "close"]].copy()
    bars["trade_day"] = bars["trade_day"].astype(str)
    bars["ts"] = pd.to_datetime(bars["ts"])
    bars["close"] = pd.to_numeric(bars["close"], errors="coerce")
    bars = bars.dropna(subset=["ts", "close"]).sort_values(["trade_day", "ts"]).reset_index(drop=True)

    daily = bars.groupby("trade_day", as_index=True)["close"].agg(day_open="first", day_high="max", day_low="min")
    hist_high = daily["day_high"].shift(1).rolling(lookback_days, min_periods=lookback_days).max()
    hist_low = daily["day_low"].shift(1).rolling(lookback_days, min_periods=lookback_days).min()

    dual_range = (hist_high - hist_low).clip(lower=0.0)
    daily["dual_thrust_range"] = dual_range
    daily["dual_thrust_upper"] = daily["day_open"] + float(k1) * dual_range
    daily["dual_thrust_lower"] = daily["day_open"] - float(k2) * dual_range

    out = bars.merge(
        daily[["day_open", "dual_thrust_range", "dual_thrust_upper", "dual_thrust_lower"]],
        left_on="trade_day",
        right_index=True,
        how="left",
    )

    target: List[int] = []
    current_day = ""
    pos = 0
    hold_bars = 0

    for row in out.itertuples(index=False):
        day = str(row.trade_day)
        close_px = float(row.close)
        upper = row.dual_thrust_upper
        lower = row.dual_thrust_lower

        if day != current_day:
            current_day = day
            pos = 0
            hold_bars = 0

        if pd.isna(upper) or pd.isna(lower):
            pos = 0
            hold_bars = 0
            target.append(0)
            continue

        upper_f = float(upper)
        lower_f = float(lower)

        if pos == 0:
            if close_px >= upper_f:
                pos = 1
                hold_bars = 0
            elif close_px <= lower_f:
                pos = -1
                hold_bars = 0
        else:
            hold_bars += 1
            if pos > 0 and close_px <= lower_f:
                pos = -1
                hold_bars = 0
            elif pos < 0 and close_px >= upper_f:
                pos = 1
                hold_bars = 0
            elif hold_bars >= hold_limit:
                pos = 0
                hold_bars = 0

        target.append(int(pos))

    out["target_pos"] = pd.Series(target, index=out.index, dtype=int)
    return out
