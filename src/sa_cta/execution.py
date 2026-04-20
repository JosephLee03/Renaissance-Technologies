from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np
import pandas as pd


@dataclass
class ExecutionConfig:
    contract_multiplier: float
    tick_size: float
    fee_rate: float
    slippage_ticks: float
    impact_coeff: float


class TickExecutionSimulator:
    def __init__(self, ticks_df: pd.DataFrame, config: ExecutionConfig):
        if ticks_df.empty:
            raise ValueError("ticks_df is empty, cannot run execution simulation.")
        self.ticks = ticks_df.sort_values("ts").reset_index(drop=True)
        self.ts_values = self.ticks["ts"].to_numpy(dtype="datetime64[ns]")
        self.config = config

    def simulate(self, order_ts: pd.Timestamp, qty: int) -> Dict[str, float]:
        if qty == 0:
            raise ValueError("qty cannot be 0 in simulate().")

        side = 1 if qty > 0 else -1
        ts = np.datetime64(order_ts)
        idx = int(np.searchsorted(self.ts_values, ts, side="left"))
        if idx >= len(self.ticks):
            idx = len(self.ticks) - 1

        tick = self.ticks.iloc[idx]
        decision_price = float(tick["price"])
        arrival_price = decision_price

        bid = float(tick.get("bid_price_0", np.nan))
        ask = float(tick.get("ask_price_0", np.nan))

        if np.isnan(bid) or bid <= 0.0:
            bid = decision_price - self.config.tick_size
        if np.isnan(ask) or ask <= 0.0:
            ask = decision_price + self.config.tick_size

        spread = max(ask - bid, self.config.tick_size)

        if side > 0:
            base_fill = ask
        else:
            base_fill = bid

        impact_ticks = self.config.impact_coeff * abs(qty) / max(float(tick.get("volume", 1.0)), 1.0)
        impact_px = impact_ticks * self.config.tick_size

        fill_price = base_fill + side * self.config.slippage_ticks * self.config.tick_size + side * impact_px

        notional = abs(qty) * fill_price * self.config.contract_multiplier
        fee = notional * self.config.fee_rate

        spread_cost = abs(qty) * 0.5 * spread * self.config.contract_multiplier
        slippage_cost = abs(qty) * self.config.slippage_ticks * self.config.tick_size * self.config.contract_multiplier
        impact_cost = abs(qty) * abs(impact_px) * self.config.contract_multiplier
        total_cost = fee + spread_cost + slippage_cost + impact_cost

        return {
            "ts": pd.Timestamp(tick["ts"]),
            "decision_ts": pd.Timestamp(order_ts),
            "side": float(side),
            "qty": float(qty),
            "decision_price": float(decision_price),
            "arrival_price": float(arrival_price),
            "fill_price": float(fill_price),
            "spread": float(spread),
            "spread_cost": float(spread_cost),
            "slippage_cost": float(slippage_cost),
            "impact_cost": float(impact_cost),
            "fee": float(fee),
            "total_cost": float(total_cost),
        }
