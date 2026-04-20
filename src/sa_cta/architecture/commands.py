from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Protocol

from .contracts import PipelineRequest
from .template import PipelineTemplate


class Command(Protocol):
    def execute(self) -> Dict[str, object]:
        ...


@dataclass
class RunPipelineCommand:
    pipeline: PipelineTemplate
    request: PipelineRequest

    def execute(self) -> Dict[str, object]:
        return self.pipeline.run(self.request)
