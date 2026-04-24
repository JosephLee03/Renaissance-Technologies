# CTA System Refactor Design

## 1. Overview

Refactor the SA Intraday CTA trading system to use a minimal, pragmatic design pattern approach based on MFE 5210 principles:
- Composition over inheritance
- YAGNI (You Aren't Gonna Need It)
- Keep it simple but standard-compliant

## 2. Core Design Patterns

| Pattern | Role | Location |
|--------|------|----------|
| **Template Method** | Define pipeline step skeleton | `pipeline.py` |
| **Protocol** | Interface definitions (duck typing) | `contracts.py` |
| **Factory** | Component creation | `factory.py` |
| **Facade** | Entry point | `facade.py` |

## 3. Directory Structure

```
src/sa_cta/
├── __init__.py           # Public API
├── pipeline.py          # Template Method: IntradayPipeline
├── factory.py          # Factory: CTAComponentFactory
├── contracts.py        # Protocol: SignalPort, BacktestPort, etc.
├── facade.py          # Facade: run_pipeline()
├── config.py          # Configuration
├── logging_system.py # Logging
├── (core engines)
│   ├── data.py        # Data loading
│   ├── signal.py      # DualThrust signal
│   ├── backtest.py   # Backtest engine
│   ├── execution.py  # Execution simulator
│   ├── metrics.py   # Performance metrics
│   ├── tca.py      # TCA analysis
│   ├── storage.py  # SQLite storage
│   └── quality.py  # Data quality
├── gui/
│   └── app.py
```

## 4. Pattern Details

### 4.1 Template Method (pipeline.py)

```python
class IntradayPipeline:
    def run(self, config):  # Template method
        frames = self.load_data(config)
        self.build_signal(frames)
        self.run_backtest(frames)
        self.analyze(frames)
        self.persist(frames)
```

### 4.2 Protocol (contracts.py)

```python
class SignalPort(Protocol):
    def build(self, min1_df) -> pd.DataFrame: ...

class BacktestPort(Protocol):
    def run(self, signal_df, ticks_df, initial_capital): ...
```

### 4.3 Factory (factory.py)

```python
class CTAComponentFactory:
    def create_signal(self, strategy_name): ...
    def create_backtest(self): ...
    def create_storage(self): ...
```

### 4.4 Facade (facade.py)

```python
def run_pipeline(config_path, start_day=None, end_day=None):
    factory = CTAComponentFactory(config)
    pipeline = IntradayPipeline(factory)
    return pipeline.run(config)
```

## 5. Removed Patterns

- ❌ Builder pattern (over-engineered for this system)
- ❌ Command pattern (simple function call suffices)
- ❌ Event system (no pub/sub needed for batch CTA)
- ❌ Multiple Adapter layers (direct component use)

## 6. MFE 5210 Principles Applied

| Principle | Implementation |
|-----------|----------------|
| Composition over inheritance | Core engines remain as functions/classes, pipeline composes them |
| Duck typing | Protocol defines interface, implementation flexible |
| YAGNI | Only 4 patterns used, no pre-extension for future |
| Simple first | Linear pipeline fits CTA workload |

## 7. Backward Compatibility

- Keep `sa_cta.run_pipeline()` as public API entry
- Config format unchanged
- Output format unchanged

## 8. Next Steps

1. Implement refactored structure
2. Run tests to verify
3. Update documentation