from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0.0 or np.isnan(denominator):
        return 0.0
    return float(numerator / denominator)


def compute_metrics(
    equity_df: pd.DataFrame,
    initial_capital: float,
    underlying_close_df: Optional[pd.DataFrame] = None,
    trades_df: Optional[pd.DataFrame] = None,
) -> Dict[str, float]:
    if equity_df.empty:
        return {
            "total_return": 0.0,
            "annualized_return": 0.0,
            "annualized_volatility": 0.0,
            "sharpe": 0.0,
            "information_ratio": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "turnover": 0.0,
            "trade_count": 0.0,
        }

    daily_pnl = equity_df.groupby("trade_day", as_index=True)["pnl_net"].sum()
    daily_ret = daily_pnl / initial_capital

    sharpe = 0.0
    if len(daily_ret) > 1:
        sharpe = np.sqrt(252.0) * _safe_ratio(float(daily_ret.mean()), float(daily_ret.std(ddof=0)))

    info_ratio = 0.0
    if underlying_close_df is not None and not underlying_close_df.empty:
        benchmark_daily = underlying_close_df.groupby("trade_day", as_index=True)["close"].last().pct_change().fillna(0.0)
        aligned = daily_ret.reindex(benchmark_daily.index).fillna(0.0)
        active = aligned - benchmark_daily
        if len(active) > 1:
            info_ratio = np.sqrt(252.0) * _safe_ratio(float(active.mean()), float(active.std(ddof=0)))
    else:
        if len(daily_ret) > 1:
            info_ratio = np.sqrt(252.0) * _safe_ratio(float(daily_ret.mean()), float(daily_ret.std(ddof=0)))

    max_drawdown = float(equity_df["drawdown"].min()) if "drawdown" in equity_df.columns else 0.0
    total_return = float(equity_df["equity"].iloc[-1] / initial_capital - 1.0)
    annualized_return = float(daily_ret.mean() * 252.0) if len(daily_ret) > 0 else 0.0
    annualized_volatility = float(daily_ret.std(ddof=0) * np.sqrt(252.0)) if len(daily_ret) > 1 else 0.0

    win_rate = 0.0
    profit_factor = 0.0
    if trades_df is not None and not trades_df.empty:
        wins = trades_df[trades_df["net_pnl"] > 0.0]
        losses = trades_df[trades_df["net_pnl"] < 0.0]
        win_rate = float(len(wins) / len(trades_df))
        gain = float(wins["net_pnl"].sum())
        loss = float(-losses["net_pnl"].sum())
        profit_factor = _safe_ratio(gain, loss)

    turnover = float(equity_df["position"].diff().abs().fillna(0.0).sum())
    trade_count = float(len(trades_df)) if trades_df is not None and not trades_df.empty else 0.0

    return {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "sharpe": float(sharpe),
        "information_ratio": float(info_ratio),
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "profit_factor": float(profit_factor),
        "turnover": turnover,
        "trade_count": trade_count,
    }
