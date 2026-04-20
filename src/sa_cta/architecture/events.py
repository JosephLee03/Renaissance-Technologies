from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Protocol


@dataclass
class PipelineEvent:
    stage: str
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat(timespec="seconds") + "Z")


class EventObserver(Protocol):
    def on_event(self, event: PipelineEvent) -> None:
        ...


class EventBus:
    def __init__(self):
        self._observers: List[EventObserver] = []

    def subscribe(self, observer: EventObserver) -> None:
        self._observers.append(observer)

    def publish(self, stage: str, payload: Dict[str, Any] | None = None) -> None:
        event = PipelineEvent(stage=stage, payload=payload or {})
        for observer in list(self._observers):
            observer.on_event(event)


class EventRecorder:
    def __init__(self):
        self.events: List[PipelineEvent] = []

    def on_event(self, event: PipelineEvent) -> None:
        self.events.append(event)

    def to_payload(self) -> List[Dict[str, Any]]:
        return [
            {
                "stage": item.stage,
                "created_at": item.created_at,
                "payload": item.payload,
            }
            for item in self.events
        ]
