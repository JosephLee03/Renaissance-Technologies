from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from .architecture import TradingSystemBuilder


def run_pipeline(
    config_path: str | Path = "config/default.yaml",
    start_day: Optional[str] = None,
    end_day: Optional[str] = None,
) -> Dict[str, object]:
    """Compatibility entrypoint for the refactored architecture.

    The implementation now delegates to the facade created by TradingSystemBuilder.
    """
    system = TradingSystemBuilder().build()
    return system.run_pipeline(
        config_path=config_path,
        start_day=start_day,
        end_day=end_day,
    )
