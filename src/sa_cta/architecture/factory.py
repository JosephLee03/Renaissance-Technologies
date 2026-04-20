from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from ..backtest import BacktestConfig
from ..config import AppConfig
from ..execution import ExecutionConfig
from .adapters import (
    ArtifactWriterAdapter,
    BacktestAdapter,
    DataAuditAdapter,
    DualThrustSignalAdapter,
    ExecutionSummaryAdapter,
    MetricsAdapter,
    OrderRequestBuilderAdapter,
    ParquetMarketDataAdapter,
    SQLitePersistenceAdapter,
    TCAAdapter,
)
from .contracts import (
    ArtifactPort,
    AuditPort,
    BacktestPort,
    ComponentFactoryPort,
    ExecutionSummaryPort,
    MarketDataPort,
    MetricsPort,
    OrderPort,
    PersistencePort,
    SignalPort,
    TCAPort,
)


class ComponentFactory(ABC):
    @abstractmethod
    def create_market_data(self) -> MarketDataPort:
        raise NotImplementedError

    @abstractmethod
    def create_signal(self) -> SignalPort:
        raise NotImplementedError

    @abstractmethod
    def create_order_builder(self) -> OrderPort:
        raise NotImplementedError

    @abstractmethod
    def create_backtest(self) -> BacktestPort:
        raise NotImplementedError

    @abstractmethod
    def create_metrics(self) -> MetricsPort:
        raise NotImplementedError

    @abstractmethod
    def create_tca(self) -> TCAPort:
        raise NotImplementedError

    @abstractmethod
    def create_execution_summary(self) -> ExecutionSummaryPort:
        raise NotImplementedError

    @abstractmethod
    def create_audit(self) -> AuditPort:
        raise NotImplementedError

    @abstractmethod
    def create_artifact_writer(self) -> ArtifactPort:
        raise NotImplementedError

    @abstractmethod
    def create_persistence(self) -> Optional[PersistencePort]:
        raise NotImplementedError

    @abstractmethod
    def initial_capital(self) -> float:
        raise NotImplementedError


class DefaultComponentFactory(ComponentFactory, ComponentFactoryPort):
    def __init__(self, config: AppConfig, project_root: Path):
        self.config = config
        self.project_root = project_root

    def create_market_data(self) -> MarketDataPort:
        return ParquetMarketDataAdapter()

    def create_signal(self) -> SignalPort:
        strategy_cfg = self.config.strategy
        strategy_name = str(strategy_cfg.get("name", "dual_thrust")).lower()
        if strategy_name != "dual_thrust":
            raise ValueError(f"Unsupported strategy name: {strategy_name}")

        return DualThrustSignalAdapter(
            lookback_days=int(strategy_cfg["lookback_days"]),
            k1=float(strategy_cfg["k1"]),
            k2=float(strategy_cfg["k2"]),
            max_hold_bars=int(strategy_cfg["max_hold_bars"]),
        )

    def create_order_builder(self) -> OrderPort:
        return OrderRequestBuilderAdapter()

    def create_backtest(self) -> BacktestPort:
        exec_cfg = ExecutionConfig(
            contract_multiplier=float(self.config.execution["contract_multiplier"]),
            tick_size=float(self.config.execution["tick_size"]),
            fee_rate=float(self.config.execution["fee_rate"]),
            slippage_ticks=float(self.config.execution["slippage_ticks"]),
            impact_coeff=float(self.config.execution["impact_coeff"]),
        )
        bt_cfg = BacktestConfig(
            max_position=int(self.config.risk["max_position"]),
            max_daily_loss=float(self.config.risk["max_daily_loss"]),
            force_flat_time=str(self.config.risk["force_flat_time"]),
            max_consecutive_losses=int(self.config.risk["max_consecutive_losses"]),
            cooldown_minutes=int(self.config.risk["cooldown_minutes"]),
            contract_multiplier=float(self.config.execution["contract_multiplier"]),
        )
        return BacktestAdapter(exec_cfg=exec_cfg, bt_cfg=bt_cfg)

    def create_metrics(self) -> MetricsPort:
        return MetricsAdapter()

    def create_tca(self) -> TCAPort:
        return TCAAdapter(contract_multiplier=float(self.config.execution["contract_multiplier"]))

    def create_execution_summary(self) -> ExecutionSummaryPort:
        return ExecutionSummaryAdapter(contract_multiplier=float(self.config.execution["contract_multiplier"]))

    def create_audit(self) -> AuditPort:
        return DataAuditAdapter()

    def create_artifact_writer(self) -> ArtifactPort:
        return ArtifactWriterAdapter()

    def create_persistence(self) -> Optional[PersistencePort]:
        if not bool(self.config.database["enabled"]):
            return None
        db_path = self.project_root / str(self.config.database["path"])
        return SQLitePersistenceAdapter(db_path=db_path)

    def initial_capital(self) -> float:
        return float(self.config.output["initial_capital"])
