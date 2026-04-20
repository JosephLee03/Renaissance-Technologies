from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from .commands import RunPipelineCommand
from .contracts import PipelineRequest
from .template import PipelineTemplate


class TradingSystemFacade:
    def __init__(self, pipeline: PipelineTemplate):
        self.pipeline = pipeline

    def run_pipeline(
        self,
        config_path: str | Path,
        start_day: Optional[str] = None,
        end_day: Optional[str] = None,
    ) -> Dict[str, object]:
        command = RunPipelineCommand(
            pipeline=self.pipeline,
            request=PipelineRequest(
                config_path=Path(config_path),
                start_day=start_day,
                end_day=end_day,
            ),
        )
        return command.execute()
