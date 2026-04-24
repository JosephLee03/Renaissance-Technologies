"""Protocol interfaces for CTA system components."""
from __future__ import annotations
from typing import Protocol, Dict, Any, Tuple, List
import pandas as pd


class SignalPort(Protocol):
    """Signal generation interface."""
    def build(self, min1_df: pd.DataFrame) -> pd.DataFrame:
        """Generate trading signals from minute bar data."""
        ...


class BacktestPort(Protocol):
    """Backtest execution interface."""
    def run(
        self,
        signal_df: pd.DataFrame,
        ticks_df: pd.DataFrame,
        initial_capital: float,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Run backtest. Returns (equity_df, fills_df, trades_df)."""
        ...


class MarketDataPort(Protocol):
    """Market data loading interface."""
    def load(self, path: str, days: List[str]) -> pd.DataFrame:
        """Load market data for given days."""
        ...

    def list_days(self, path: str) -> List[str]:
        """List available trading days."""
        ...


class StoragePort(Protocol):
    """Data persistence interface."""
    def save(self, df: pd.DataFrame, table_name: str) -> None:
        """Save dataframe to storage."""
        ...

    def load(self, table_name: str) -> pd.DataFrame:
        """Load dataframe from storage."""
        ...


class MetricsPort(Protocol):
    """Performance metrics interface."""
    def compute(self, equity_df: pd.DataFrame, initial_capital: float) -> Dict[str, float]:
        """Compute performance metrics."""
        ...


class TCAPort(Protocol):
    """Transaction cost analysis interface."""
    def analyze(
        self,
        fills_df: pd.DataFrame,
        orders_df: pd.DataFrame,
    ) -> Dict[str, pd.DataFrame]:
        """Compute TCA report."""
        ...