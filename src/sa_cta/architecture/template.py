from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
import logging
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from ..config import load_config
from ..logging_system import PipelineLoggingObserver, build_backtest_event_hook, configure_run_logger
from .contracts import (
    ComponentFactoryPort,
    PipelineContext,
    PipelineFrames,
    PipelineOutputs,
    PipelineRequest,
    PipelineResponse,
)
from .events import EventBus, EventRecorder
from .factory import DefaultComponentFactory


class PipelineTemplate(ABC):
    def __init__(self, event_bus: EventBus, event_recorder: EventRecorder):
        self.event_bus = event_bus
        self.event_recorder = event_recorder

    def run(self, request: PipelineRequest) -> Dict[str, object]:
        context = self.prepare_context(request)
        logger = logging.getLogger(context.logger_name)
        self.event_bus.subscribe(PipelineLoggingObserver(logger))

        self.event_bus.publish(
            "pipeline.started",
            {
                "config_path": str(request.config_path),
                "run_id": context.run_id,
                "log_file_path": context.log_file_path,
            },
        )
        factory = self.create_factory(context)

        frames = self.load_market_data(context, factory)
        self.event_bus.publish(
            "data.loaded",
            {
                "selected_day_count": len(context.selected_days),
                "min1_rows": int(len(frames.min1_df)),
            },
        )

        self.build_signal(context, frames, factory)
        self.event_bus.publish(
            "signal.built",
            {
                "signal_rows": int(len(frames.signal_df)),
            },
        )

        self.load_ticks(context, frames, factory)
        self.event_bus.publish(
            "ticks.loaded",
            {
                "tick_rows": int(len(frames.ticks_df)),
                "backtest_day_count": len(context.backtest_days),
            },
        )

        self.run_backtest(context, frames, factory)
        self.event_bus.publish(
            "backtest.completed",
            {
                "equity_rows": int(len(frames.equity_df)),
                "fill_rows": int(len(frames.fills_df)),
                "trade_rows": int(len(frames.trades_df)),
            },
        )

        outputs = self.analyze(context, frames, factory)
        self.event_bus.publish("analysis.completed", {"metric_keys": list(outputs.metrics.keys())})

        self.write_outputs(context, frames, outputs, factory)
        self.event_bus.publish("artifacts.written", {"artifacts_dir": str(context.artifacts_dir)})

        self.persist_outputs(context, frames, outputs, factory)
        self.event_bus.publish("persistence.completed", {"database_enabled": bool(context.config.database["enabled"])})

        response = self.build_response(context, outputs)
        summary = self.build_run_summary(context, frames, outputs, response)
        self.event_bus.publish("pipeline.completed", {"run_id": context.run_id, "summary": summary})
        response.lifecycle_events = self.event_recorder.to_payload()
        response.run_summary = summary
        return response.to_dict()

    @abstractmethod
    def prepare_context(self, request: PipelineRequest) -> PipelineContext:
        raise NotImplementedError

    @abstractmethod
    def create_factory(self, context: PipelineContext) -> ComponentFactoryPort:
        raise NotImplementedError

    @abstractmethod
    def load_market_data(self, context: PipelineContext, factory: ComponentFactoryPort) -> PipelineFrames:
        raise NotImplementedError

    @abstractmethod
    def build_signal(self, context: PipelineContext, frames: PipelineFrames, factory: ComponentFactoryPort) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_ticks(self, context: PipelineContext, frames: PipelineFrames, factory: ComponentFactoryPort) -> None:
        raise NotImplementedError

    @abstractmethod
    def run_backtest(self, context: PipelineContext, frames: PipelineFrames, factory: ComponentFactoryPort) -> None:
        raise NotImplementedError

    @abstractmethod
    def analyze(
        self,
        context: PipelineContext,
        frames: PipelineFrames,
        factory: ComponentFactoryPort,
    ) -> PipelineOutputs:
        raise NotImplementedError

    @abstractmethod
    def write_outputs(
        self,
        context: PipelineContext,
        frames: PipelineFrames,
        outputs: PipelineOutputs,
        factory: ComponentFactoryPort,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def persist_outputs(
        self,
        context: PipelineContext,
        frames: PipelineFrames,
        outputs: PipelineOutputs,
        factory: ComponentFactoryPort,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def build_response(self, context: PipelineContext, outputs: PipelineOutputs) -> PipelineResponse:
        raise NotImplementedError

    def build_run_summary(
        self,
        context: PipelineContext,
        frames: PipelineFrames,
        outputs: PipelineOutputs,
        response: PipelineResponse,
    ) -> Dict[str, object]:
        equity_df = frames.equity_df
        final_equity = float(equity_df["equity"].iloc[-1]) if not equity_df.empty and "equity" in equity_df else float(context.config.output["initial_capital"])
        total_return = float(response.metrics.get("total_return", 0.0))
        max_drawdown = float(response.metrics.get("max_drawdown", 0.0))
        total_trades = int(len(frames.trades_df))
        total_fills = int(len(frames.fills_df))
        total_days = int(len(context.backtest_days))

        return {
            "run_id": context.run_id,
            "selected_day_count": int(len(context.selected_days)),
            "backtest_day_count": total_days,
            "signal_rows": int(len(frames.signal_df)),
            "order_rows": int(len(frames.orders_df)),
            "fill_rows": total_fills,
            "trade_rows": total_trades,
            "final_equity": final_equity,
            "total_return": total_return,
            "max_drawdown": max_drawdown,
            "artifacts_dir": str(context.artifacts_dir),
            "log_file_path": context.log_file_path,
        }


class IntradayCTAPipeline(PipelineTemplate):
    def __init__(self, event_bus: EventBus, event_recorder: EventRecorder):
        super().__init__(event_bus=event_bus, event_recorder=event_recorder)

    @staticmethod
    def _resolve_path(base: Path, raw_path: str) -> Path:
        path = Path(raw_path)
        if path.is_absolute():
            return path
        return (base / path).resolve()

    @staticmethod
    def _filter_days(days: List[str], start_day: Optional[str], end_day: Optional[str]) -> List[str]:
        out = []
        for day in days:
            if start_day is not None and day < start_day:
                continue
            if end_day is not None and day > end_day:
                continue
            out.append(day)
        return out

    def prepare_context(self, request: PipelineRequest) -> PipelineContext:
        cfg_path = request.config_path.resolve()
        project_root = cfg_path.parent.parent
        config = load_config(cfg_path)
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        data_root = self._resolve_path(project_root, str(config.data["root"]))
        min1_subdir = str(config.data["min1_subdir"])
        tick_subdir = str(config.data["tick_subdir"])

        probe_factory = DefaultComponentFactory(config=config, project_root=project_root)
        market_data = probe_factory.create_market_data()
        common_days = market_data.list_common_days(data_root, min1_subdir, tick_subdir)
        selected_days = self._filter_days(common_days, request.start_day, request.end_day)

        if not selected_days:
            raise ValueError("No trading days selected. Check date range and data root.")

        artifacts_dir = self._resolve_path(project_root, str(config.output["artifacts_dir"]))
        logger_name, log_file_path, heartbeat_bars = configure_run_logger(project_root, config, run_id)
        return PipelineContext(
            project_root=project_root,
            config=config,
            run_id=run_id,
            selected_days=selected_days,
            data_root=data_root,
            min1_subdir=min1_subdir,
            tick_subdir=tick_subdir,
            artifacts_dir=artifacts_dir,
            logger_name=logger_name,
            log_file_path=log_file_path,
            backtest_heartbeat_bars=heartbeat_bars,
        )

    def create_factory(self, context: PipelineContext) -> ComponentFactoryPort:
        return DefaultComponentFactory(config=context.config, project_root=context.project_root)

    def load_market_data(self, context: PipelineContext, factory: ComponentFactoryPort) -> PipelineFrames:
        market_data = factory.create_market_data()
        min1_df = market_data.load_min1_days(context.data_root, context.min1_subdir, context.selected_days)
        return PipelineFrames(min1_df=min1_df)

    def build_signal(self, context: PipelineContext, frames: PipelineFrames, factory: ComponentFactoryPort) -> None:
        signal_builder = factory.create_signal()
        signal_df = signal_builder.build(frames.min1_df)
        if signal_df.empty:
            raise ValueError("Signal frame is empty after strategy generation.")

        order_builder = factory.create_order_builder()
        orders_df = order_builder.build(
            signal_df[["trade_day", "ts", "close", "dual_thrust_upper", "dual_thrust_lower", "target_pos"]]
        )

        frames.signal_df = signal_df
        frames.orders_df = orders_df

    def load_ticks(self, context: PipelineContext, frames: PipelineFrames, factory: ComponentFactoryPort) -> None:
        context.backtest_days = sorted(frames.signal_df["trade_day"].astype(str).unique().tolist())
        market_data = factory.create_market_data()
        frames.ticks_df = market_data.load_ticks_days(context.data_root, context.tick_subdir, context.backtest_days)

    def run_backtest(self, context: PipelineContext, frames: PipelineFrames, factory: ComponentFactoryPort) -> None:
        backtester = factory.create_backtest()
        logger = logging.getLogger(context.logger_name)
        backtest_hook = build_backtest_event_hook(logger)
        equity_df, fills_df, trades_df = backtester.run(
            signal_df=frames.signal_df[["trade_day", "ts", "close", "target_pos"]],
            ticks_df=frames.ticks_df,
            initial_capital=factory.initial_capital(),
            event_hook=backtest_hook,
            heartbeat_bars=int(context.backtest_heartbeat_bars),
        )
        frames.equity_df = equity_df
        frames.fills_df = fills_df
        frames.trades_df = trades_df

    def analyze(
        self,
        context: PipelineContext,
        frames: PipelineFrames,
        factory: ComponentFactoryPort,
    ) -> PipelineOutputs:
        metrics = factory.create_metrics().compute(
            equity_df=frames.equity_df,
            initial_capital=factory.initial_capital(),
            underlying_close_df=frames.signal_df[["trade_day", "close"]],
            trades_df=frames.trades_df,
        )
        tca_report = factory.create_tca().build(
            fills_df=frames.fills_df,
            orders_df=frames.orders_df,
            min1_df=frames.min1_df,
            ticks_df=frames.ticks_df,
        )
        execution_summary = factory.create_execution_summary().build(frames.fills_df, frames.trades_df)
        data_audit = factory.create_audit().build(frames.min1_df, frames.ticks_df)

        active_signal_ratio = float((frames.signal_df["target_pos"].astype(int) != 0).mean())
        active_days = int(frames.signal_df.groupby("trade_day")["target_pos"].apply(lambda x: (x != 0).any()).sum())

        strategy_cfg = context.config.strategy
        strategy_summary = {
            "strategy": str(strategy_cfg.get("name", "dual_thrust")),
            "lookback_days": int(strategy_cfg["lookback_days"]),
            "k1": float(strategy_cfg["k1"]),
            "k2": float(strategy_cfg["k2"]),
            "max_hold_bars": int(strategy_cfg["max_hold_bars"]),
            "active_signal_ratio": active_signal_ratio,
            "active_days": active_days,
            "total_days": int(len(context.backtest_days)),
            "avg_holding_minutes": float(execution_summary["avg_holding_minutes"]),
            "max_holding_minutes": float(execution_summary["max_holding_minutes"]),
            "holding_less_than_1day": bool(execution_summary["holding_less_than_1day"]),
        }

        if not bool(strategy_summary["holding_less_than_1day"]):
            raise ValueError("Holding period constraint violated: found holding time >= 1 day.")

        return PipelineOutputs(
            metrics=metrics,
            strategy_summary=strategy_summary,
            execution_summary=execution_summary,
            tca_report=tca_report,
            data_audit=data_audit,
        )

    def write_outputs(
        self,
        context: PipelineContext,
        frames: PipelineFrames,
        outputs: PipelineOutputs,
        factory: ComponentFactoryPort,
    ) -> None:
        artifact_writer = factory.create_artifact_writer()
        outputs.file_paths = artifact_writer.write(
            artifacts_dir=context.artifacts_dir,
            run_id=context.run_id,
            frames=frames,
            outputs=outputs,
        )

    def persist_outputs(
        self,
        context: PipelineContext,
        frames: PipelineFrames,
        outputs: PipelineOutputs,
        factory: ComponentFactoryPort,
    ) -> None:
        persistence = factory.create_persistence()
        if persistence is not None:
            persistence.persist(run_id=context.run_id, frames=frames, outputs=outputs)

    def build_response(self, context: PipelineContext, outputs: PipelineOutputs) -> PipelineResponse:
        return PipelineResponse(
            run_id=context.run_id,
            selected_days=context.selected_days,
            backtest_days=context.backtest_days,
            data_audit=outputs.data_audit,
            metrics=outputs.metrics,
            strategy_summary=outputs.strategy_summary,
            execution_summary=outputs.execution_summary,
            artifacts_dir=str(context.artifacts_dir),
            metrics_path=outputs.file_paths.get("metrics_path", ""),
            strategy_summary_path=outputs.file_paths.get("strategy_summary_path", ""),
            execution_summary_path=outputs.file_paths.get("execution_summary_path", ""),
            log_file_path=context.log_file_path,
        )
