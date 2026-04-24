"""Component factory for CTA system."""
from __future__ import annotations
from pathlib import Path
from typing import Optional
import pandas as pd

from .config import AppConfig, load_config
from .contracts import (
    SignalPort,
    BacktestPort,
    MarketDataPort,
    StoragePort,
    MetricsPort,
    TCAPort,
)


class CTAComponentFactory:
    """Factory for creating CTA system components."""
    
    def __init__(self, config: AppConfig):
        self.config = config
    
    def create_signal(self) -> SignalPort:
        """Create signal generator (DualThrust only for now)."""
        strategy_cfg = self.config.strategy
        strategy_name = strategy_cfg.get("name", "dual_thrust")
        
        if strategy_name != "dual_thrust":
            raise ValueError(f"Unknown strategy: {strategy_name}")
        
        from .signal import build_dual_thrust_signal_frame
        return DualThrustSignalAdapter(
            lookback_days=int(strategy_cfg["lookback_days"]),
            k1=float(strategy_cfg["k1"]),
            k2=float(strategy_cfg["k2"]),
            max_hold_bars=int(strategy_cfg["max_hold_bars"]),
        )
    
    def create_backtest(self) -> BacktestPort:
        """Create backtest engine."""
        from .backtest import BacktestAdapter
        from .execution import ExecutionConfig
        
        exec_cfg = ExecutionConfig(
            contract_multiplier=float(self.config.execution["contract_multiplier"]),
            tick_size=float(self.config.execution["tick_size"]),
            fee_rate=float(self.config.execution["fee_rate"]),
            slippage_ticks=float(self.config.execution["slippage_ticks"]),
            impact_coeff=float(self.config.execution["impact_coeff"]),
        )
        from .backtest import BacktestConfig
        bt_cfg = BacktestConfig(
            max_position=int(self.config.risk["max_position"]),
            max_daily_loss=float(self.config.risk["max_daily_loss"]),
            force_flat_time=str(self.config.risk["force_flat_time"]),
            max_consecutive_losses=int(self.config.risk["max_consecutive_losses"]),
            cooldown_minutes=int(self.config.risk["cooldown_minutes"]),
            contract_multiplier=float(self.config.execution["contract_multiplier"]),
        )
        return BacktestAdapter(exec_cfg=exec_cfg, bt_cfg=bt_cfg)
    
    def create_market_data(self) -> MarketDataPort:
        """Create market data loader."""
        return ParquetMarketDataAdapter()
    
    def create_storage(self) -> Optional[StoragePort]:
        """Create storage adapter."""
        if not self.config.database.get("enabled", True):
            return None
        db_path = Path(self.config.database.get("path", "artifacts/sa_intraday.sqlite"))
        return SQLiteStorageAdapter(db_path=db_path)
    
    def create_metrics(self) -> MetricsPort:
        """Create metrics calculator."""
        from .metrics import MetricsAdapter
        return MetricsAdapter()
    
    def create_tca(self) -> TCAPort:
        """Create TCA analyzer."""
        from .tca import TCAAdapter
        tca_cfg = self.config.raw.get("tca", {}) if isinstance(self.config.raw, dict) else {}
        return TCAAdapter(
            contract_multiplier=float(self.config.execution["contract_multiplier"]),
            compare_algorithms=list(tca_cfg.get("compare_algorithms", ["DIRECT", "VWAP", "TWAP", "POV"])),
            compare_horizon_minutes=int(tca_cfg.get("compare_horizon_minutes", 20)),
        )
    
    def initial_capital(self) -> float:
        """Get initial capital."""
        return float(self.config.output["initial_capital"])


class DualThrustSignalAdapter:
    """DualThrust signal adapter."""
    
    def __init__(self, lookback_days: int, k1: float, k2: float, max_hold_bars: int):
        self.lookback_days = lookback_days
        self.k1 = k1
        self.k2 = k2
        self.max_hold_bars = max_hold_bars
    
    def build(self, min1_df: pd.DataFrame) -> pd.DataFrame:
        from .signal import build_dual_thrust_signal_frame
        return build_dual_thrust_signal_frame(
            min1_df=min1_df,
            lookback_days=self.lookback_days,
            k1=self.k1,
            k2=self.k2,
            max_hold_bars=self.max_hold_bars,
        )


class ParquetMarketDataAdapter:
    """Market data loader adapter."""

    def load(self, path: str, days: list) -> pd.DataFrame:
        from .data import load_min1_days, load_ticks_days
        p = Path(path)
        data_root = p.parent
        subdir = p.name
        # Try min1 first, fallback to ticks
        try:
            return load_min1_days(data_root, subdir, days)
        except Exception:
            return load_ticks_days(data_root, subdir, days)

    def list_days(self, path: str) -> list:
        from .data import list_trading_days
        p = Path(path)
        data_root = p.parent
        subdir = p.name
        return list_trading_days(data_root, subdir)


class SQLiteStorageAdapter:
    """SQLite storage adapter."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
    
    def save(self, df: pd.DataFrame, table_name: str) -> None:
        from .storage import SQLiteStore
        store = SQLiteStore(self.db_path)
        store.write_frame(df, table_name)
    
    def load(self, table_name: str) -> pd.DataFrame:
        from .storage import SQLiteStore
        store = SQLiteStore(self.db_path)
        return store.read_frame(table_name)