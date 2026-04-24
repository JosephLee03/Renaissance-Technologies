"""Facade entry point for CTA system."""
from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, Any

from .config import load_config
from .pipeline import IntradayPipeline
from .factory import CTAComponentFactory


def run_pipeline(
    config_path: str | Path = "config/default.yaml",
    start_day: Optional[str] = None,
    end_day: Optional[str] = None,
) -> Dict[str, Any]:
    """Main entry point for CTA system - Facade pattern.
    
    Args:
        config_path: Path to configuration file
        start_day: Start date (YYYYMMDD)
        end_day: End date (YYYYMMDD)
    
    Returns:
        Dict with metrics and results
    """
    config = load_config(config_path)
    factory = CTAComponentFactory(config)
    pipeline = IntradayPipeline(factory)
    
    return pipeline.run(config_path, start_day, end_day)


# Backward compatibility alias
def execute_pipeline(*args, **kwargs):
    """Alias for run_pipeline."""
    return run_pipeline(*args, **kwargs)