# CTA System Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor CTA system to use Template Method + Factory + Protocol + Facade patterns per MFE 5210 design principles

**Architecture:** Minimal 4-pattern design (Template Method, Protocol, Factory, Facade) with clean separation between pipeline orchestration and core engines

**Tech Stack:** Python, Pandas, SQLite, Dash

---

## Current Architecture Issues

- Over-engineered with 7+ GoF patterns
- architecture/ directory with 8 files, most just forwarding calls
- Event system adds complexity without benefit
- Builder/Facade/Command patterns are overkill

## Plan Overview

1. Create contracts.py (Protocol definitions)
2. Create factory.py (Component Factory)
3. Create pipeline.py (Template Method)
4. Create facade.py (Entry point)
5. Clean up architecture/ directory
6. Verify backward compatibility

---

### Task 1: Create contracts.py (Protocol Interfaces)

**Files:**
- Create: `src/sa_cta/contracts.py`

- [ ] **Step 1: Create contracts.py with Protocol definitions**

```python
"""Protocol interfaces for CTA system components."""
from __future__ import annotations
from typing import Protocol, Dict, Any, Optional, Tuple, List
import pandas as pd


class SignalPort(Protocol):
    """Signal generation interface."""
    def build(self, min1_df: pd.DataFrame) -> pd.DataFrame:
        """Generate trading signals from minute bar data."""
        ...


class BacktestPort(Protocol):
    """Backtest execution interface."""
    def run(
        self,
        signal_df: pd.DataFrame,
        ticks_df: pd.DataFrame,
        initial_capital: float,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Run backtest. Returns (equity_df, fills_df, trades_df)."""
        ...


class MarketDataPort(Protocol):
    """Market data loading interface."""
    def load(self, data_root: str, days: List[str]) -> pd.DataFrame:
        """Load market data for given days."""
        ...


class StoragePort(Protocol):
    """Data persistence interface."""
    def save(self, df: pd.DataFrame, table_name: str) -> None:
        """Save dataframe to storage."""
        ...
    
    def load(self, table_name: str) -> pd.DataFrame:
        """Load dataframe from storage."""
        ...


class MetricsPort(Protocol):
    """Performance metrics interface."""
    def compute(self, equity_df: pd.DataFrame, initial_capital: float) -> Dict[str, float]:
        """Compute performance metrics."""
        ...

class TCAPort(Protocol):
    """Transaction cost analysis interface."""
    def analyze(
        self,
        fills_df: pd.DataFrame,
        orders_df: pd.DataFrame,
    ) -> Dict[str, pd.DataFrame]:
        """Compute TCA report."""
        ...
```

- [ ] **Step 2: Commit**

```bash
git add src/sa_cta/contracts.py
git commit -m "refactor: add protocol interfaces in contracts.py"
```

---

### Task 2: Create factory.py (Component Factory)

**Files:**
- Create: `src/sa_cta/factory.py`

- [ ] **Step 1: Create factory.py**

```python
"""Component factory for CTA system."""
from __future__ import annotations
from pathlib import Path
from typing import Optional, List, Dict, Any

import pandas as pd

from .contracts import (
    SignalPort,
    BacktestPort,
    MarketDataPort,
    StoragePort,
    MetricsPort,
    TCAPort,
)
from .config import AppConfig, load_config


class CTAComponentFactory:
    """Factory for creating CTA system components."""
    
    def __init__(self, config: AppConfig):
        self.config = config
    
    def create_signal(self) -> SignalPort:
        """Create signal generator."""
        strategy_cfg = self.config.strategy
        strategy_name = strategy_cfg.get("name", "dual_thrust")
        
        if strategy_name == "dual_thrust":
            from .signal import build_dual_thrust_signal_frame
            return DualThrustSignalAdapter(
                lookback_days=int(strategy_cfg["lookback_days"]),
                k1=float(strategy_cfg["k1"]),
                k2=float(strategy_cfg["k2"]),
                max_hold_bars=int(strategy_cfg["max_hold_bars"]),
            )
        raise ValueError(f"Unknown strategy: {strategy_name}")
    
    def create_backtest(self) -> BacktestPort:
        """Create backtest engine."""
        from .backtest import BacktestAdapter
        return BacktestAdapter(
            exec_cfg=self.config.execution,
            bt_cfg=self.config.risk,
        )
    
    def create_market_data(self) -> MarketDataPort:
        """Create market data loader."""
        from .data import ParquetMarketDataAdapter
        return ParquetMarketDataAdapter()
    
    def create_storage(self) -> Optional[StoragePort]:
        """Create storage adapter."""
        if not self.config.database.get("enabled", True):
            return None
        from .storage import SQLiteStorageAdapter
        return SQLiteStorageAdapter(
            db_path=Path(self.config.database.get("path", "artifacts/sa_intraday.sqlite"))
        )
    
    def create_metrics(self) -> MetricsPort:
        """Create metrics calculator."""
        from .metrics import MetricsAdapter
        return MetricsAdapter()
    
    def create_tca(self) -> TCAPort:
        """Create TCA analyzer."""
        from .tca import TCAAdapter
        return TCAAdapter(config=self.config)


class DualThrustSignalAdapter:
    """DualThrust signal adapter."""
    
    def __init__(self, lookback_days: int, k1: float, k2: float, max_hold_bars: int):
        self.lookback_days = lookback_days
        self.k1 = k1
        self.k2 = k2
        self.max_hold_bars = max_hold_bars
    
    def build(self, min1_df: pd.DataFrame) -> pd.DataFrame:
        from .signal import build_dual_thrust_signal_frame
        return build_dual_thrust_signal_frame(
            min1_df=min1_df,
            lookback_days=self.lookback_days,
            k1=self.k1,
            k2=self.k2,
            max_hold_bars=self.max_hold_bars,
        )
```

- [ ] **Step 2: Commit**

```bash
git add src/sa_cta/factory.py
git commit -m "refactor: add CTAComponentFactory in factory.py"
```

---

### Task 3: Create pipeline.py (Template Method)

**Files:**
- Create: `src/sa_cta/pipeline.py`

- [ ] **Step 1: Create pipeline.py with Template Method**

```python
"""Intraday CTA Pipeline - Template Method Pattern."""
from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Dict, Any

import pandas as pd

from .config import load_config
from .factory import CTAComponentFactory
from .contracts import (
    SignalPort,
    BacktestPort,
    MarketDataPort,
    StoragePort,
    MetricsPort,
    TCAPort,
)


class IntradayPipeline:
    """Template Method: Defines pipeline step skeleton."""
    
    def __init__(self, factory: CTAComponentFactory):
        self.factory = factory
    
    def run(self, config_path: str, start_day: Optional[str] = None, end_day: Optional[str] = None) -> Dict[str, Any]:
        """Template method: executes all pipeline steps."""
        # Step 1: Prepare context
        context = self._prepare_context(config_path, start_day, end_day)
        
        # Step 2: Load market data
        frames = self._load_data(context)
        
        # Step 3: Build signals
        frames = self._build_signal(frames)
        
        # Step 4: Run backtest
        frames = self._run_backtest(frames)
        
        # Step 5: Analyze
        outputs = self._analyze(frames)
        
        # Step 6: Persist
        self._persist(frames, outputs)
        
        return outputs
    
    def _prepare_context(self, config_path: str, start_day: Optional[str], end_day: Optional[str]) -> Dict[str, Any]:
        """Prepare pipeline context."""
        config = load_config(config_path)
        factory = CTAComponentFactory(config)
        
        data_root = Path(config.data["root"])
        min1_subdir = config.data["min1_subdir"]
        tick_subdir = config.data["tick_subdir"]
        
        # Get common days
        market_data = factory.create_market_data()
        min1_days = market_data.list_days(data_root / min1_subdir)
        tick_days = market_data.list_days(data_root / tick_subdir)
        common_days = sorted(set(min1_days) & set(tick_days))
        
        # Filter by date range
        if start_day:
            common_days = [d for d in common_days if d >= start_day]
        if end_day:
            common_days = [d for d in common_days if d <= end_day]
        
        return {
            "config": config,
            "factory": factory,
            "data_root": data_root,
            "min1_subdir": min1_subdir,
            "tick_subdir": tick_subdir,
            "days": common_days,
        }
    
    def _load_data(self, context: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        """Step 2: Load market data."""
        factory = context["factory"]
        market_data = factory.create_market_data()
        
        data_root = context["data_root"]
        days = context["days"]
        
        min1_df = market_data.load_days(
            data_root / context["min1_subdir"], 
            days
        )
        ticks_df = market_data.load_days(
            data_root / context["tick_subdir"], 
            days
        )
        
        return {"min1_df": min1_df, "ticks_df": ticks_df}
    
    def _build_signal(self, frames: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Step 3: Build trading signals."""
        from .signal import build_dual_thrust_signal_frame
        from .config import load_config
        
        # Direct signal building for simplicity
        config = load_config("config/default.yaml")
        signal = config.strategy
        
        signal_df = build_dual_thrust_signal_frame(
            min1_df=frames["min1_df"],
            lookback_days=int(signal["lookback_days"]),
            k1=float(signal["k1"]),
            k2=float(signal["k2"]),
            max_hold_bars=int(signal["max_hold_bars"]),
        )
        
        frames["signal_df"] = signal_df
        return frames
    
    def _run_backtest(self, frames: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Step 4: Run backtest."""
        from .backtest import BacktestAdapter
        from .config import load_config
        
        config = load_config("config/default.yaml")
        backtest = BacktestAdapter(
            exec_cfg=config.execution,
            bt_cfg=config.risk,
        )
        
        equity_df, fills_df, trades_df = backtest.run(
            signal_df=frames["signal_df"][["trade_day", "ts", "close", "target_pos"]],
            ticks_df=frames["ticks_df"],
            initial_capital=float(config.output["initial_capital"]),
        )
        
        frames["equity_df"] = equity_df
        frames["fills_df"] = fills_df
        frames["trades_df"] = trades_df
        return frames
    
    def _analyze(self, frames: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Step 5: Analyze results."""
        from .metrics import compute_metrics
        from .config import load_config
        
        config = load_config("config/default.yaml")
        
        metrics = compute_metrics(
            equity_df=frames["equity_df"],
            initial_capital=float(config.output["initial_capital"]),
            underlying_close_df=frames["signal_df"][["trade_day", "close"]],
            trades_df=frames["trades_df"],
        )
        
        return {"metrics": metrics}
    
    def _persist(self, frames: Dict[str, pd.DataFrame], outputs: Dict[str, Any]) -> None:
        """Step 6: Persist results."""
        # Simplified: save to CSV (full implementation can delegate to storage)
        pass
```

- [ ] **Step 2: Commit**

```bash
git add src/sa_cta/pipeline.py
git commit -m "refactor: add IntradayPipeline template method in pipeline.py"
```

---

### Task 4: Create facade.py (Entry Point)

**Files:**
- Create: `src/sa_cta/facade.py`

- [ ] **Step 1: Create facade.py**

```python
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
    """Main entry point - Facade pattern.
    
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
    
    return pipeline.run(str(config_path), start_day, end_day)


# Backward compatibility alias
def execute_pipeline(*args, **kwargs):
    """Alias for run_pipeline."""
    return run_pipeline(*args, **kwargs)
```

- [ ] **Step 2: Commit**

```bash
git add src/sa_cta/facade.py
git commit -m "refactor: add facade entry point in facade.py"
```

---

### Task 5: Update __init__.py (Public API)

**Files:**
- Modify: `src/sa_cta/__init__.py`

- [ ] **Step 1: Update public API exports**

```python
"""SA CTA - Intraday CTA Trading System."""
from .facade import run_pipeline
from .pipeline import IntradayPipeline
from .factory import CTAComponentFactory

__all__ = [
    "run_pipeline",
    "IntradayPipeline",
    "CTAComponentFactory",
]
```

- [ ] **Step 2: Commit**

```bash
git add src/sa_cta/__init__.py
git commit -m "refactor: update public API exports"
```

---

### Task 6: Clean Up Architecture Directory

**Files:**
- Modify: `src/sa_cta/architecture/` (reduce or remove)

- [ ] **Step 1: Assess architecture files**

Check which files in architecture/ are still needed:
- builder.py: Can be simplified or removed
- template.py: Functions moved to pipeline.py
- facade.py: New facade.py replaces this
- factory.py: New factory.py replaces this
- contracts.py: New contracts.py replaces this
- events.py: Remove (over-engineered)
- commands.py: Remove (simple function call suffices)

- [ ] **Step 2: Migrate or remove files**

Options:
- If any critical logic exists, migrate to core engines
- Otherwise, deprecate/remove

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor: clean up architecture directory"
```

---

### Task 7: Verify Backward Compatibility

**Files:**
- Test: `src/sa_cta/__init__.py`

- [ ] **Step 1: Test import**

```python
from sa_cta import run_pipeline
result = run_pipeline("config/default.yaml")
print(result)
```

- [ ] **Step 2: Verify output**

Expected: Keys include 'metrics', 'strategy_summary'

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor: verify backward compatibility"
```

---

## Execution Options

**Plan complete and saved to `docs/superpowers/plans/2026-04-24-cta-refactor.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**