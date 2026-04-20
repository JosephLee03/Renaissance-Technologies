from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

import pandas as pd

from ..config import AppConfig


@dataclass
class PipelineRequest:
    config_path: Path
    start_day: Optional[str] = None
    end_day: Optional[str] = None


@dataclass
class PipelineContext:
    project_root: Path
    config: AppConfig
    run_id: str
    selected_days: List[str]
    backtest_days: List[str] = field(default_factory=list)
    data_root: Path = Path(".")
    min1_subdir: str = "min1"
    tick_subdir: str = "ticks"
    artifacts_dir: Path = Path("artifacts")
    logger_name: str = "sa_cta"
    log_file_path: str = ""
    backtest_heartbeat_bars: int = 1200


@dataclass
class PipelineFrames:
    min1_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    ticks_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    signal_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    orders_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    equity_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    fills_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    trades_df: pd.DataFrame = field(default_factory=pd.DataFrame)


@dataclass
class PipelineOutputs:
    metrics: Dict[str, float] = field(default_factory=dict)
    strategy_summary: Dict[str, object] = field(default_factory=dict)
    execution_summary: Dict[str, object] = field(default_factory=dict)
    tca_report: Dict[str, pd.DataFrame] = field(default_factory=dict)
    data_audit: Dict[str, Dict[str, float]] = field(default_factory=dict)
    file_paths: Dict[str, str] = field(default_factory=dict)


class MarketDataPort(Protocol):
    def list_common_days(self, data_root: Path, min1_subdir: str, tick_subdir: str) -> List[str]:
        ...

    def load_min1_days(self, data_root: Path, subdir: str, days: List[str]) -> pd.DataFrame:
        ...

    def load_ticks_days(self, data_root: Path, subdir: str, days: List[str]) -> pd.DataFrame:
        ...


class SignalPort(Protocol):
    def build(self, min1_df: pd.DataFrame) -> pd.DataFrame:
        ...


class OrderPort(Protocol):
    def build(self, signal_df: pd.DataFrame) -> pd.DataFrame:
        ...


class BacktestPort(Protocol):
    def run(
        self,
        signal_df: pd.DataFrame,
        ticks_df: pd.DataFrame,
        initial_capital: float,
        event_hook: Optional[Callable[[str, Dict[str, object]], None]] = None,
        heartbeat_bars: int = 1200,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        ...


class MetricsPort(Protocol):
    def compute(
        self,
        equity_df: pd.DataFrame,
        initial_capital: float,
        underlying_close_df: pd.DataFrame,
        trades_df: pd.DataFrame,
    ) -> Dict[str, float]:
        ...


class TCAPort(Protocol):
    def build(
        self,
        fills_df: pd.DataFrame,
        orders_df: pd.DataFrame,
        min1_df: pd.DataFrame,
        ticks_df: pd.DataFrame,
    ) -> Dict[str, pd.DataFrame]:
        ...


class ExecutionSummaryPort(Protocol):
    def build(self, fills_df: pd.DataFrame, trades_df: pd.DataFrame) -> Dict[str, object]:
        ...


class AuditPort(Protocol):
    def build(self, min1_df: pd.DataFrame, ticks_df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
        ...


class ArtifactPort(Protocol):
    def write(
        self,
        artifacts_dir: Path,
        run_id: str,
        frames: PipelineFrames,
        outputs: PipelineOutputs,
    ) -> Dict[str, str]:
        ...


class PersistencePort(Protocol):
    def persist(self, run_id: str, frames: PipelineFrames, outputs: PipelineOutputs) -> None:
        ...


class ComponentFactoryPort(Protocol):
    def create_market_data(self) -> MarketDataPort:
        ...

    def create_signal(self) -> SignalPort:
        ...

    def create_order_builder(self) -> OrderPort:
        ...

    def create_backtest(self) -> BacktestPort:
        ...

    def create_metrics(self) -> MetricsPort:
        ...

    def create_tca(self) -> TCAPort:
        ...

    def create_execution_summary(self) -> ExecutionSummaryPort:
        ...

    def create_audit(self) -> AuditPort:
        ...

    def create_artifact_writer(self) -> ArtifactPort:
        ...

    def create_persistence(self) -> Optional[PersistencePort]:
        ...

    def initial_capital(self) -> float:
        ...


@dataclass
class PipelineResponse:
    run_id: str
    selected_days: List[str]
    backtest_days: List[str]
    data_audit: Dict[str, Dict[str, float]]
    metrics: Dict[str, float]
    strategy_summary: Dict[str, object]
    execution_summary: Dict[str, object]
    artifacts_dir: str
    metrics_path: str
    strategy_summary_path: str
    execution_summary_path: str
    log_file_path: str = ""
    lifecycle_events: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "selected_days": self.selected_days,
            "backtest_days": self.backtest_days,
            "data_audit": self.data_audit,
            "metrics": self.metrics,
            "strategy_summary": self.strategy_summary,
            "execution_summary": self.execution_summary,
            "artifacts_dir": self.artifacts_dir,
            "metrics_path": self.metrics_path,
            "strategy_summary_path": self.strategy_summary_path,
            "execution_summary_path": self.execution_summary_path,
            "log_file_path": self.log_file_path,
            "lifecycle_events": self.lifecycle_events,
        }
