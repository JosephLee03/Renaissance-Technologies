from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .execution import ExecutionConfig, TickExecutionSimulator


@dataclass
class BacktestConfig:
    max_position: int
    max_daily_loss: float
    force_flat_time: str
    max_consecutive_losses: int
    cooldown_minutes: int
    contract_multiplier: float


def _parse_force_flat_time(value: str) -> time:
    hh, mm, ss = value.split(":")
    return time(int(hh), int(mm), int(ss))


def run_backtest(
    signal_df: pd.DataFrame,
    ticks_df: pd.DataFrame,
    exec_cfg: ExecutionConfig,
    bt_cfg: BacktestConfig,
    initial_capital: float,
    event_hook: Optional[Callable[[str, Dict[str, object]], None]] = None,
    heartbeat_bars: int = 1200,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if signal_df.empty:
        raise ValueError("signal_df is empty.")

    df = signal_df.sort_values("ts").reset_index(drop=True).copy()
    df["target_pos"] = df["target_pos"].clip(-bt_cfg.max_position, bt_cfg.max_position).astype(int)

    simulator = TickExecutionSimulator(ticks_df=ticks_df, config=exec_cfg)
    force_flat_clock = _parse_force_flat_time(bt_cfg.force_flat_time)

    fills: List[Dict[str, float]] = []
    trades: List[Dict[str, float]] = []
    records: List[Dict[str, float]] = []

    position = 0
    prev_close: Optional[float] = None
    cum_pnl = 0.0

    current_day: Optional[str] = None
    day_pnl = 0.0
    day_trading_blocked = False
    consecutive_losses = 0
    cooldown_until: Optional[pd.Timestamp] = None

    open_trade: Optional[Dict[str, float]] = None

    def emit(event_name: str, payload: Dict[str, object]) -> None:
        if event_hook is not None:
            event_hook(event_name, payload)

    emit(
        "backtest_start",
        {
            "bars": int(len(df)),
            "days": int(df["trade_day"].astype(str).nunique()),
            "max_position": int(bt_cfg.max_position),
        },
    )

    def execute_single(order_ts: pd.Timestamp, qty: int, pos_before: int) -> Tuple[int, float]:
        nonlocal open_trade
        nonlocal consecutive_losses
        nonlocal cooldown_until

        fill = simulator.simulate(order_ts=order_ts, qty=qty)
        fill["pos_before"] = float(pos_before)
        fill["pos_after"] = float(pos_before + qty)
        fills.append(fill)

        emit(
            "order_fill",
            {
                "ts": str(fill["ts"]),
                "qty": float(qty),
                "side": float(np.sign(qty)),
                "fill_price": float(fill["fill_price"]),
                "total_cost": float(fill["total_cost"]),
                "pos_before": float(pos_before),
                "pos_after": float(pos_before + qty),
            },
        )

        pos_after = pos_before + qty
        fill_cost = float(fill["total_cost"])

        if pos_before == 0 and pos_after != 0:
            open_trade = {
                "entry_ts": pd.Timestamp(fill["ts"]),
                "entry_price": float(fill["fill_price"]),
                "side": float(np.sign(pos_after)),
                "qty": float(abs(pos_after)),
                "entry_cost": float(fill_cost),
            }
        elif pos_before != 0 and pos_after == 0 and open_trade is not None:
            side = float(open_trade["side"])
            qty_abs = float(open_trade["qty"])
            gross = (float(fill["fill_price"]) - float(open_trade["entry_price"])) * side * qty_abs * bt_cfg.contract_multiplier
            net = gross - float(open_trade["entry_cost"]) - fill_cost
            trades.append(
                {
                    "entry_ts": open_trade["entry_ts"],
                    "exit_ts": pd.Timestamp(fill["ts"]),
                    "side": side,
                    "qty": qty_abs,
                    "gross_pnl": float(gross),
                    "net_pnl": float(net),
                    "holding_minutes": float((pd.Timestamp(fill["ts"]) - open_trade["entry_ts"]).total_seconds() / 60.0),
                }
            )
            emit(
                "trade_closed",
                {
                    "entry_ts": str(open_trade["entry_ts"]),
                    "exit_ts": str(fill["ts"]),
                    "side": float(side),
                    "net_pnl": float(net),
                    "holding_minutes": float((pd.Timestamp(fill["ts"]) - open_trade["entry_ts"]).total_seconds() / 60.0),
                },
            )
            if net < 0.0:
                consecutive_losses += 1
                if consecutive_losses >= bt_cfg.max_consecutive_losses:
                    cooldown_until = pd.Timestamp(fill["ts"]) + pd.Timedelta(minutes=bt_cfg.cooldown_minutes)
                    emit(
                        "risk_cooldown_start",
                        {
                            "ts": str(fill["ts"]),
                            "cooldown_until": str(cooldown_until),
                            "cooldown_minutes": int(bt_cfg.cooldown_minutes),
                        },
                    )
                    consecutive_losses = 0
            else:
                consecutive_losses = 0
            open_trade = None

        return pos_after, fill_cost

    for i, row in enumerate(df.itertuples(index=False), start=1):
        ts = pd.Timestamp(row.ts)
        trade_day = str(row.trade_day)
        close = float(row.close)

        if current_day != trade_day:
            if current_day is not None:
                emit(
                    "day_end",
                    {
                        "trade_day": str(current_day),
                        "day_pnl": float(day_pnl),
                        "cum_pnl": float(cum_pnl),
                    },
                )
            current_day = trade_day
            day_pnl = 0.0
            day_trading_blocked = False
            consecutive_losses = 0
            cooldown_until = None
            emit("day_start", {"trade_day": trade_day})

        blocked_before = day_trading_blocked
        if day_pnl <= -bt_cfg.max_daily_loss:
            day_trading_blocked = True
        if day_trading_blocked and not blocked_before:
            emit(
                "risk_daily_loss_block",
                {
                    "trade_day": trade_day,
                    "day_pnl": float(day_pnl),
                    "limit": float(-bt_cfg.max_daily_loss),
                },
            )

        desired = int(row.target_pos)

        if day_trading_blocked:
            desired = 0
        if cooldown_until is not None and ts < cooldown_until:
            desired = 0
        if ts.time() >= force_flat_clock:
            desired = 0

        pnl_gross = 0.0
        if prev_close is not None:
            pnl_gross = position * (close - prev_close) * bt_cfg.contract_multiplier

        trade_cost = 0.0

        if desired != position:
            if position != 0 and desired != 0 and np.sign(position) != np.sign(desired):
                position, cost_close = execute_single(ts, -position, position)
                trade_cost += cost_close
                position, cost_open = execute_single(ts, desired, position)
                trade_cost += cost_open
            else:
                qty = desired - position
                position, cost_single = execute_single(ts, qty, position)
                trade_cost += cost_single

        pnl_net = pnl_gross - trade_cost
        day_pnl += pnl_net
        cum_pnl += pnl_net

        records.append(
            {
                "ts": ts,
                "trade_day": trade_day,
                "close": close,
                "target_pos": float(desired),
                "position": float(position),
                "pnl_gross": float(pnl_gross),
                "trade_cost": float(trade_cost),
                "pnl_net": float(pnl_net),
                "day_pnl": float(day_pnl),
                "cum_pnl": float(cum_pnl),
            }
        )

        if heartbeat_bars > 0 and i % heartbeat_bars == 0:
            emit(
                "heartbeat",
                {
                    "bar_index": int(i),
                    "ts": str(ts),
                    "trade_day": trade_day,
                    "position": float(position),
                    "day_pnl": float(day_pnl),
                    "cum_pnl": float(cum_pnl),
                },
            )

        prev_close = close

    if current_day is not None:
        emit(
            "day_end",
            {
                "trade_day": str(current_day),
                "day_pnl": float(day_pnl),
                "cum_pnl": float(cum_pnl),
            },
        )

    equity_df = pd.DataFrame(records)
    if equity_df.empty:
        equity_df = pd.DataFrame(
            columns=[
                "ts",
                "trade_day",
                "close",
                "target_pos",
                "position",
                "pnl_gross",
                "trade_cost",
                "pnl_net",
                "day_pnl",
                "cum_pnl",
                "equity",
                "drawdown",
            ]
        )
    else:
        equity_df["equity"] = initial_capital + equity_df["cum_pnl"]
        equity_df["running_peak"] = equity_df["equity"].cummax()
        equity_df["drawdown"] = equity_df["equity"] - equity_df["running_peak"]
        equity_df = equity_df.drop(columns=["running_peak"])

    fills_df = pd.DataFrame(fills)
    trades_df = pd.DataFrame(trades)
    emit(
        "backtest_end",
        {
            "equity_rows": int(len(equity_df)),
            "fills": int(len(fills_df)),
            "trades": int(len(trades_df)),
            "final_cum_pnl": float(cum_pnl),
        },
    )
    return equity_df, fills_df, trades_df
