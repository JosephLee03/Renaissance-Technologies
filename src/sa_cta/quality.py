from __future__ import annotations

from typing import Dict

import pandas as pd


def audit_min1(df: pd.DataFrame) -> Dict[str, float]:
    if df.empty:
        return {"rows": 0.0}

    ts_diff = df["ts"].diff()
    gap_count = int((ts_diff > pd.Timedelta(minutes=5)).sum())

    return {
        "rows": float(len(df)),
        "null_count": float(df.isnull().sum().sum()),
        "duplicate_ts": float(df["ts"].duplicated().sum()),
        "non_positive_close": float((df["close"] <= 0).sum()),
        "large_time_gaps": float(gap_count),
    }


def audit_ticks(df: pd.DataFrame) -> Dict[str, float]:
    if df.empty:
        return {"rows": 0.0}

    spread = (df["ask_price_0"] - df["bid_price_0"]).fillna(0.0)

    return {
        "rows": float(len(df)),
        "null_count": float(df.isnull().sum().sum()),
        "duplicate_ts": float(df["ts"].duplicated().sum()),
        "non_positive_price": float((df["price"] <= 0).sum()),
        "negative_spread": float((spread < 0).sum()),
    }
