from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd

from ..backtest import BacktestConfig, run_backtest
from ..data import list_trading_days, load_min1_days, load_ticks_days
from ..execution import ExecutionConfig
from ..metrics import compute_metrics
from ..quality import audit_min1, audit_ticks
from ..signal import build_dual_thrust_signal_frame
from ..storage import SQLiteStore
from ..tca import build_tca_report
from .contracts import PipelineFrames, PipelineOutputs


class ParquetMarketDataAdapter:
    def list_common_days(self, data_root: Path, min1_subdir: str, tick_subdir: str) -> List[str]:
        min1_days = list_trading_days(data_root, min1_subdir)
        tick_days = list_trading_days(data_root, tick_subdir)
        return sorted(set(min1_days).intersection(set(tick_days)))

    def load_min1_days(self, data_root: Path, subdir: str, days: List[str]) -> pd.DataFrame:
        return load_min1_days(data_root, subdir, days)

    def load_ticks_days(self, data_root: Path, subdir: str, days: List[str]) -> pd.DataFrame:
        return load_ticks_days(data_root, subdir, days)


class DualThrustSignalAdapter:
    def __init__(self, lookback_days: int, k1: float, k2: float, max_hold_bars: int):
        self.lookback_days = int(lookback_days)
        self.k1 = float(k1)
        self.k2 = float(k2)
        self.max_hold_bars = int(max_hold_bars)

    def build(self, min1_df: pd.DataFrame) -> pd.DataFrame:
        return build_dual_thrust_signal_frame(
            min1_df=min1_df,
            lookback_days=self.lookback_days,
            k1=self.k1,
            k2=self.k2,
            max_hold_bars=self.max_hold_bars,
        )


class OrderRequestBuilderAdapter:
    def build(self, signal_df: pd.DataFrame) -> pd.DataFrame:
        if signal_df.empty:
            return pd.DataFrame(
                columns=[
                    "order_id",
                    "trade_day",
                    "ts",
                    "side",
                    "qty",
                    "pos_before",
                    "pos_after",
                    "close",
                    "dual_thrust_upper",
                    "dual_thrust_lower",
                ]
            )

        rows: List[Dict[str, object]] = []
        current_day = ""
        prev_pos = 0

        ordered = signal_df.sort_values(["trade_day", "ts"]).reset_index(drop=True)
        for row in ordered.itertuples(index=False):
            day = str(row.trade_day)
            if day != current_day:
                current_day = day
                prev_pos = 0

            desired = int(row.target_pos)
            if desired == prev_pos:
                continue

            qty = desired - prev_pos
            rows.append(
                {
                    "trade_day": day,
                    "ts": pd.Timestamp(row.ts),
                    "side": "BUY" if qty > 0 else "SELL",
                    "qty": int(abs(qty)),
                    "pos_before": int(prev_pos),
                    "pos_after": int(desired),
                    "close": float(row.close),
                    "dual_thrust_upper": float(row.dual_thrust_upper),
                    "dual_thrust_lower": float(row.dual_thrust_lower),
                }
            )
            prev_pos = desired

        out = pd.DataFrame(rows)
        if out.empty:
            out["order_id"] = pd.Series(dtype=int)
            return out
        out.insert(0, "order_id", range(1, len(out) + 1))
        return out


class BacktestAdapter:
    def __init__(self, exec_cfg: ExecutionConfig, bt_cfg: BacktestConfig):
        self.exec_cfg = exec_cfg
        self.bt_cfg = bt_cfg

    def run(
        self,
        signal_df: pd.DataFrame,
        ticks_df: pd.DataFrame,
        initial_capital: float,
        event_hook: Optional[Callable[[str, Dict[str, object]], None]] = None,
        heartbeat_bars: int = 1200,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        return run_backtest(
            signal_df=signal_df,
            ticks_df=ticks_df,
            exec_cfg=self.exec_cfg,
            bt_cfg=self.bt_cfg,
            initial_capital=initial_capital,
            event_hook=event_hook,
            heartbeat_bars=heartbeat_bars,
        )


class MetricsAdapter:
    def compute(
        self,
        equity_df: pd.DataFrame,
        initial_capital: float,
        underlying_close_df: pd.DataFrame,
        trades_df: pd.DataFrame,
    ) -> Dict[str, float]:
        return compute_metrics(
            equity_df=equity_df,
            initial_capital=initial_capital,
            underlying_close_df=underlying_close_df,
            trades_df=trades_df,
        )


class TCAAdapter:
    def __init__(self, contract_multiplier: float):
        self.contract_multiplier = float(contract_multiplier)

    def build(
        self,
        fills_df: pd.DataFrame,
        orders_df: pd.DataFrame,
        min1_df: pd.DataFrame,
        ticks_df: pd.DataFrame,
    ) -> Dict[str, pd.DataFrame]:
        return build_tca_report(
            fills_df=fills_df,
            orders_df=orders_df,
            min1_df=min1_df,
            ticks_df=ticks_df,
            contract_multiplier=self.contract_multiplier,
        )


class ExecutionSummaryAdapter:
    def __init__(self, contract_multiplier: float):
        self.contract_multiplier = float(contract_multiplier)

    def build(self, fills_df: pd.DataFrame, trades_df: pd.DataFrame) -> Dict[str, object]:
        if fills_df.empty:
            return {
                "fill_count": 0,
                "order_qty_total": 0.0,
                "notional_total": 0.0,
                "spread_cost_total": 0.0,
                "slippage_cost_total": 0.0,
                "impact_cost_total": 0.0,
                "fee_total": 0.0,
                "total_cost": 0.0,
                "avg_cost_per_fill": 0.0,
                "implementation_shortfall": 0.0,
                "avg_holding_minutes": 0.0,
                "max_holding_minutes": 0.0,
                "holding_less_than_1day": True,
            }

        qty_abs = fills_df["qty"].astype(float).abs()
        fill_px = fills_df["fill_price"].astype(float)
        decision_px = fills_df["decision_price"].astype(float)
        side = fills_df["side"].astype(float)

        total_cost = float(fills_df["total_cost"].astype(float).sum())
        summary = {
            "fill_count": int(len(fills_df)),
            "order_qty_total": float(qty_abs.sum()),
            "notional_total": float((qty_abs * fill_px * self.contract_multiplier).sum()),
            "spread_cost_total": float(fills_df["spread_cost"].astype(float).sum()),
            "slippage_cost_total": float(fills_df["slippage_cost"].astype(float).sum()),
            "impact_cost_total": float(fills_df["impact_cost"].astype(float).sum()),
            "fee_total": float(fills_df["fee"].astype(float).sum()),
            "total_cost": total_cost,
            "avg_cost_per_fill": float(total_cost / max(len(fills_df), 1)),
            "implementation_shortfall": float(((fill_px - decision_px) * side * qty_abs * self.contract_multiplier).sum()),
            "avg_holding_minutes": 0.0,
            "max_holding_minutes": 0.0,
            "holding_less_than_1day": True,
        }

        if not trades_df.empty:
            holding = trades_df["holding_minutes"].astype(float)
            summary["avg_holding_minutes"] = float(holding.mean())
            summary["max_holding_minutes"] = float(holding.max())
            summary["holding_less_than_1day"] = bool(float(holding.max()) < 1440.0)

        return summary


class DataAuditAdapter:
    def build(self, min1_df: pd.DataFrame, ticks_df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
        return {
            "min1": audit_min1(min1_df),
            "ticks": audit_ticks(ticks_df),
        }


class ArtifactWriterAdapter:
    def write(
        self,
        artifacts_dir: Path,
        run_id: str,
        frames: PipelineFrames,
        outputs: PipelineOutputs,
    ) -> Dict[str, str]:
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        signal_path = artifacts_dir / f"dual_thrust_signals_{run_id}.csv"
        orders_path = artifacts_dir / f"orders_{run_id}.csv"
        equity_path = artifacts_dir / f"equity_curve_{run_id}.csv"
        fills_path = artifacts_dir / f"fills_{run_id}.csv"
        trades_path = artifacts_dir / f"trades_{run_id}.csv"

        frames.signal_df.to_csv(signal_path, index=False)
        frames.orders_df.to_csv(orders_path, index=False)
        frames.equity_df.to_csv(equity_path, index=False)
        frames.fills_df.to_csv(fills_path, index=False)
        frames.trades_df.to_csv(trades_path, index=False)

        metrics_path = artifacts_dir / f"metrics_{run_id}.json"
        strategy_summary_path = artifacts_dir / f"strategy_summary_{run_id}.json"
        execution_summary_path = artifacts_dir / f"execution_summary_{run_id}.json"

        with metrics_path.open("w", encoding="utf-8") as f:
            json.dump(outputs.metrics, f, ensure_ascii=True, indent=2)
        with strategy_summary_path.open("w", encoding="utf-8") as f:
            json.dump(outputs.strategy_summary, f, ensure_ascii=True, indent=2)
        with execution_summary_path.open("w", encoding="utf-8") as f:
            json.dump(outputs.execution_summary, f, ensure_ascii=True, indent=2)

        tca_file_map = {
            "summary": artifacts_dir / f"tca_summary_{run_id}.csv",
            "by_hour": artifacts_dir / f"tca_by_hour_{run_id}.csv",
            "pre_trade": artifacts_dir / f"tca_pre_trade_{run_id}.csv",
            "intra_day": artifacts_dir / f"tca_intra_day_{run_id}.csv",
            "post_trade": artifacts_dir / f"tca_post_trade_{run_id}.csv",
            "kpis": artifacts_dir / f"tca_kpis_{run_id}.csv",
        }

        for key, path in tca_file_map.items():
            frame = outputs.tca_report.get(key, pd.DataFrame())
            if isinstance(frame, pd.DataFrame) and not frame.empty:
                frame.to_csv(path, index=False)

        return {
            "signal_path": str(signal_path),
            "orders_path": str(orders_path),
            "equity_path": str(equity_path),
            "fills_path": str(fills_path),
            "trades_path": str(trades_path),
            "metrics_path": str(metrics_path),
            "strategy_summary_path": str(strategy_summary_path),
            "execution_summary_path": str(execution_summary_path),
            "tca_summary_path": str(tca_file_map["summary"]),
            "tca_by_hour_path": str(tca_file_map["by_hour"]),
            "tca_pre_trade_path": str(tca_file_map["pre_trade"]),
            "tca_intra_day_path": str(tca_file_map["intra_day"]),
            "tca_post_trade_path": str(tca_file_map["post_trade"]),
            "tca_kpis_path": str(tca_file_map["kpis"]),
        }


class SQLitePersistenceAdapter:
    def __init__(self, db_path: Path):
        self.store = SQLiteStore(db_path)

    def persist(self, run_id: str, frames: PipelineFrames, outputs: PipelineOutputs) -> None:
        signal_to_db = frames.signal_df.copy()
        signal_to_db["run_id"] = run_id

        orders_to_db = frames.orders_df.copy()
        orders_to_db["run_id"] = run_id

        eq_to_db = frames.equity_df.copy()
        eq_to_db["run_id"] = run_id

        fills_to_db = frames.fills_df.copy()
        fills_to_db["run_id"] = run_id

        trades_to_db = frames.trades_df.copy()
        trades_to_db["run_id"] = run_id

        self.store.write_frame("strategy_signals", signal_to_db, if_exists="append")
        if not orders_to_db.empty:
            self.store.write_frame("orders", orders_to_db, if_exists="append")
        self.store.write_frame("equity_curve", eq_to_db, if_exists="append")
        if not fills_to_db.empty:
            self.store.write_frame("fills", fills_to_db, if_exists="append")
        if not trades_to_db.empty:
            self.store.write_frame("trades", trades_to_db, if_exists="append")

        tca_table_map = {
            "summary": "tca_summary",
            "by_hour": "tca_by_hour",
            "pre_trade": "tca_pre_trade",
            "intra_day": "tca_intra_day",
            "post_trade": "tca_post_trade",
            "kpis": "tca_kpis",
        }
        for key, table_name in tca_table_map.items():
            frame = outputs.tca_report.get(key, pd.DataFrame())
            if isinstance(frame, pd.DataFrame) and not frame.empty:
                payload = frame.copy()
                payload["run_id"] = run_id
                self.store.write_frame(table_name, payload, if_exists="append")

        strategy_to_db = pd.DataFrame([outputs.strategy_summary])
        strategy_to_db["run_id"] = run_id
        self.store.write_frame("strategy_summary", strategy_to_db, if_exists="append")

        exec_to_db = pd.DataFrame([outputs.execution_summary])
        exec_to_db["run_id"] = run_id
        self.store.write_frame("execution_summary", exec_to_db, if_exists="append")
