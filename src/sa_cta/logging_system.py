from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

from .architecture.events import PipelineEvent
from .config import AppConfig


class PipelineLoggingObserver:
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def on_event(self, event: PipelineEvent) -> None:
        payload = json.dumps(event.payload, ensure_ascii=True, default=str)
        stage = str(event.stage)
        if stage.endswith(".started") or stage.endswith(".completed"):
            self.logger.info("stage=%s payload=%s", stage, payload)
        elif stage.endswith(".failed"):
            self.logger.error("stage=%s payload=%s", stage, payload)
        else:
            self.logger.warning("stage=%s payload=%s", stage, payload)


def configure_run_logger(project_root: Path, config: AppConfig, run_id: str) -> Tuple[str, str, int]:
    logging_cfg = config.raw.get("logging", {}) if isinstance(config.raw, dict) else {}

    level_name = str(logging_cfg.get("level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    logger_name = f"sa_cta.run.{run_id}"
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if bool(logging_cfg.get("console", True)):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    log_file_path = ""
    if bool(logging_cfg.get("file", True)):
        raw_log_dir = Path(str(logging_cfg.get("log_dir", "artifacts/logs")))
        log_dir = raw_log_dir if raw_log_dir.is_absolute() else (project_root / raw_log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"pipeline_{run_id}.log"

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        log_file_path = str(log_path)

    heartbeat_bars = int(logging_cfg.get("backtest_heartbeat_bars", 1200))
    logger.info("Logger configured. run_id=%s log_file=%s heartbeat_bars=%s", run_id, log_file_path, heartbeat_bars)
    return logger_name, log_file_path, heartbeat_bars


def build_backtest_event_hook(logger: logging.Logger):
    def _hook(event_name: str, payload: Dict[str, object]) -> None:
        message = json.dumps(payload, ensure_ascii=True, default=str)
        if event_name.startswith("risk_"):
            logger.warning("backtest_event=%s payload=%s", event_name, message)
        elif event_name in {"order_fill", "trade_closed", "day_start", "day_end", "backtest_start", "backtest_end", "heartbeat"}:
            logger.info("backtest_event=%s payload=%s", event_name, message)
        else:
            logger.debug("backtest_event=%s payload=%s", event_name, message)

    return _hook
