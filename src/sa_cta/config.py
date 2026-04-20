from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml


@dataclass
class AppConfig:
    raw: Dict[str, Any]

    @property
    def data(self) -> Dict[str, Any]:
        return self.raw["data"]

    @property
    def strategy(self) -> Dict[str, Any]:
        return self.raw["strategy"]

    @property
    def risk(self) -> Dict[str, Any]:
        return self.raw["risk"]

    @property
    def execution(self) -> Dict[str, Any]:
        return self.raw["execution"]

    @property
    def database(self) -> Dict[str, Any]:
        return self.raw["database"]

    @property
    def output(self) -> Dict[str, Any]:
        return self.raw["output"]


def load_config(config_path: str | Path) -> AppConfig:
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError("Invalid config format: expected a dictionary at top level.")

    return AppConfig(raw=raw)
