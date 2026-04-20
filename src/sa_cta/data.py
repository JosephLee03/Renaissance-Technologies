from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import pandas as pd


def list_trading_days(data_root: Path, subdir: str) -> List[str]:
    day_root = data_root / subdir
    if not day_root.exists():
        return []
    return sorted([p.name for p in day_root.iterdir() if p.is_dir() and p.name.isdigit()])


def _day_file(data_root: Path, subdir: str, day: str) -> Path:
    folder = data_root / subdir / day
    files = list(folder.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No parquet found under {folder}")
    return files[0]


def load_min1_day(data_root: Path, subdir: str, day: str) -> pd.DataFrame:
    file_path = _day_file(data_root, subdir, day)
    df = pd.read_parquet(file_path)
    if "datetime" not in df.columns:
        raise ValueError(f"Missing datetime column in {file_path}")

    out = df.copy()
    out["ts"] = pd.to_datetime(out["datetime"])
    out = out.sort_values("ts").drop_duplicates(subset=["ts"]).reset_index(drop=True)
    out["trade_day"] = day

    if "close" not in out.columns:
        raise ValueError(f"Missing close column in {file_path}")

    for col in ["close", "volume", "turnover", "open_interest", "diff", "hhmm"]:
        if col not in out.columns:
            out[col] = 0.0

    return out[["trade_day", "ts", "close", "volume", "turnover", "open_interest", "diff", "hhmm"]]


def load_ticks_day(data_root: Path, subdir: str, day: str) -> pd.DataFrame:
    file_path = _day_file(data_root, subdir, day)
    df = pd.read_parquet(file_path)
    if "datetime" not in df.columns:
        raise ValueError(f"Missing datetime column in {file_path}")

    out = df.copy()
    out["ts"] = pd.to_datetime(out["datetime"])
    out = out.sort_values("ts").drop_duplicates(subset=["ts"]).reset_index(drop=True)
    out["trade_day"] = day

    for col in [
        "price",
        "bid_price_0",
        "ask_price_0",
        "bid_qty_0",
        "ask_qty_0",
        "total_volume",
        "volume",
        "total_turnover",
        "turn_over",
        "open_interest",
        "diff_interest",
        "code",
    ]:
        if col not in out.columns:
            out[col] = 0.0 if col != "code" else ""

    return out[
        [
            "trade_day",
            "ts",
            "price",
            "bid_price_0",
            "ask_price_0",
            "bid_qty_0",
            "ask_qty_0",
            "total_volume",
            "volume",
            "total_turnover",
            "turn_over",
            "open_interest",
            "diff_interest",
            "code",
        ]
    ]


def load_min1_days(data_root: Path, subdir: str, days: Iterable[str]) -> pd.DataFrame:
    frames = [load_min1_day(data_root, subdir, day) for day in days]
    if not frames:
        return pd.DataFrame(columns=["trade_day", "ts", "close", "volume", "turnover", "open_interest", "diff", "hhmm"])
    return pd.concat(frames, axis=0, ignore_index=True)


def load_ticks_days(data_root: Path, subdir: str, days: Iterable[str]) -> pd.DataFrame:
    frames = [load_ticks_day(data_root, subdir, day) for day in days]
    if not frames:
        return pd.DataFrame(
            columns=[
                "trade_day",
                "ts",
                "price",
                "bid_price_0",
                "ask_price_0",
                "bid_qty_0",
                "ask_qty_0",
                "total_volume",
                "volume",
                "total_turnover",
                "turn_over",
                "open_interest",
                "diff_interest",
                "code",
            ]
        )
    return pd.concat(frames, axis=0, ignore_index=True)
