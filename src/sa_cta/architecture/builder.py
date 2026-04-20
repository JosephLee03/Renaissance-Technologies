from __future__ import annotations

from typing import List

from .events import EventBus, EventObserver, EventRecorder
from .facade import TradingSystemFacade
from .template import IntradayCTAPipeline


class TradingSystemBuilder:
    def __init__(self):
        self._observers: List[EventObserver] = []

    def with_observer(self, observer: EventObserver) -> "TradingSystemBuilder":
        self._observers.append(observer)
        return self

    def build(self) -> TradingSystemFacade:
        event_bus = EventBus()
        event_recorder = EventRecorder()

        event_bus.subscribe(event_recorder)
        for observer in self._observers:
            event_bus.subscribe(observer)

        pipeline = IntradayCTAPipeline(event_bus=event_bus, event_recorder=event_recorder)
        return TradingSystemFacade(pipeline=pipeline)
