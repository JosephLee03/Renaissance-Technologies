# Design Patterns in SA Intraday CTA

This document maps design principles and patterns to the refactored implementation.

## 1. Core Principles

### 1.1 Composition Over Inheritance

How it is used:

- TradingSystemBuilder assembles objects through composition.
- IntradayCTAPipeline delegates work to ports and adapters rather than inheriting behavior trees.
- Factory creates composable components per run.

Benefits in this project:

- High deletability: remove or replace one adapter without touching orchestration skeleton.
- Better locality: signal/execution/persistence concerns are in separate modules.
- Improved testability: each adapter can be tested in isolation.

Trade-offs:

- More classes/files than a monolithic script.
- Requires clear contracts to avoid wiring mistakes.

### 1.2 Duck Typing

How it is used:

- Port contracts in architecture/contracts.py are protocol-based.
- Concrete classes are accepted if they provide required methods.

Benefits:

- Easier integration of alternate implementations.
- Lightweight polymorphism without rigid inheritance trees.

Trade-offs:

- Runtime errors if a replacement object violates expected method shape.

## 2. Implemented Creational Patterns

### 2.1 Factory Method + Abstract Factory

Location:

- src/sa_cta/architecture/factory.py

Usage:

- DefaultComponentFactory creates a related family of components:
  - market data adapter
  - strategy signal adapter
  - backtest adapter
  - metrics/tca/audit adapters
  - artifact and persistence adapters

Benefits:

- Consistent component family per config.
- Centralized object creation logic.

Trade-offs:

- Factory grows as the product family expands.

### 2.2 Builder

Location:

- src/sa_cta/architecture/builder.py

Usage:

- TradingSystemBuilder wires event bus, recorder, optional observers, and concrete pipeline into a facade.

Benefits:

- Clear assembly process.
- Easy to add optional wiring steps.

Trade-offs:

- Extra abstraction for very small projects.

## 3. Implemented Structural Patterns

### 3.1 Adapter

Location:

- src/sa_cta/architecture/adapters.py

Usage:

- Wrap existing module functions/classes behind stable ports.
- Examples:
  - ParquetMarketDataAdapter for filesystem/parquet access
  - SQLitePersistenceAdapter for DB write contracts
  - BacktestAdapter and TCAAdapter for core engine adaptation

Benefits:

- Legacy engines stay unchanged while orchestration evolves.
- Clear anti-corruption boundary between orchestration and implementation details.

Trade-offs:

- Boilerplate mapping code.

### 3.2 Facade

Location:

- src/sa_cta/architecture/facade.py

Usage:

- TradingSystemFacade exposes one simple method run_pipeline for clients.

Benefits:

- Simplifies script/API surface.
- Hides command/template/factory internals.

Trade-offs:

- Risks becoming a god-interface if overloaded.

### 3.3 Bridge (Pragmatic)

Location:

- contracts.py + adapters.py + template.py

Usage:

- Abstractions (ports and template flow) are separated from implementations (adapters and engines).

Benefits:

- Abstraction and implementation can evolve independently.

Trade-offs:

- Requires disciplined interface maintenance.

## 4. Implemented Behavioral Patterns

### 4.1 Template Method

Location:

- src/sa_cta/architecture/template.py

Usage:

- PipelineTemplate defines fixed run skeleton.
- IntradayCTAPipeline overrides stage implementations.

Benefits:

- Stable lifecycle with explicit extension points.

Trade-offs:

- Changes to skeleton affect all subclasses.

### 4.2 Command

Location:

- src/sa_cta/architecture/commands.py

Usage:

- RunPipelineCommand encapsulates request and execution.

Benefits:

- Decouples invocation from execution.
- Supports future queuing/retry/audit extension.

Trade-offs:

- Adds indirection for simple direct calls.

### 4.3 Observer

Location:

- src/sa_cta/architecture/events.py

Usage:

- EventBus publishes stage events.
- EventRecorder subscribes and records lifecycle events.

Benefits:

- Non-invasive observability.
- Additional listeners can be added without editing pipeline logic.

Trade-offs:

- Event flow is asynchronous in concept and can be harder to trace if overused.

## 5. MVC Mapping in This Project

- Model:
  - signal.py, backtest.py, execution.py, tca.py, metrics.py, storage.py
- View:
  - src/sa_cta/gui/app.py
- Controller:
  - scripts/run_pipeline.py, scripts/run_gui.py, scripts/run_data_audit.py
  - plus orchestration in template/facade layers

## 6. Patterns Intentionally Not Introduced Yet

- Singleton:
  - Avoided to reduce hidden global state and testing friction.
- Deep inheritance trees:
  - Avoided in favor of composition and protocol-based ports.
- Multi-level decorators/proxies:
  - Not required by current complexity; can be added later for caching/auth/rate control.

## 7. Practical Pros and Cons Summary

Pros achieved:

- Better modularity and replacement flexibility.
- Cleaner responsibilities and clearer extension points.
- Improved observability via lifecycle events.

Current costs:

- More architecture files and concepts to onboard.
- Slightly higher cognitive load than a single-script orchestrator.

## 8. Extension Recipes

- Add strategy:
  - Add adapter implementation for new signal logic.
  - Register creation logic in DefaultComponentFactory.create_signal.
- Add storage backend:
  - Implement PersistencePort and wire via factory.
- Add runtime telemetry:
  - Implement EventObserver and register through TradingSystemBuilder.with_observer.
- Add execution model family:
  - Create new backtest/execution adapters and select via factory config.
