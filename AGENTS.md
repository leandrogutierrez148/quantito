# AGENTS.md - Quantito Development & Implementation Standards

This file serves as the central reference for AI agents and developers working on the **Quantito** repository. It documents the system architecture, programming standards, and linting/formatting best practices.

---

## 1. General Project Architecture

Quantito is a Python (3.12+) platform for financial market data ingestion, processing, quantitative analysis, and signal generation.

### Directory Structure

```
quantito/
├── engine/                      # Central signal generation and dispatching engine
│   ├── __init__.py              # Exports clean public API (SignalEngine, Signal, etc.)
│   ├── models.py                # Data models: Signal (dataclass), SignalType (StrEnum)
│   ├── core.py                  # SignalEngine orchestrator (Strategy pattern, hot-swapping)
│   ├── strategies/              # Quantitative strategies
│   │   ├── __init__.py          # Auto-registration of available strategies
│   │   ├── base.py              # Abstract BaseStrategy class
│   │   ├── registry.py          # StrategyRegistry (decorator & dynamic factory)
│   │   ├── fifty_day_avg.py     # 50-day moving average strategy
│   │   └── price_momentum.py    # Price momentum / percentage change strategy
│   └── sinks/                   # Output signal destinations
│       ├── __init__.py          # Exports available sinks
│       ├── base.py              # Abstract BaseSignalSink class
│       ├── console.py           # Formatted console output
│       └── bigquery.py          # Google Cloud BigQuery persistence
├── pipelines/                   # Ingestion pipelines using EODHD API
│   ├── real_time.py             # Real-time quotes
│   ├── delayed.py               # 15-minute delayed quotes (US quotes)
│   └── eod.py                   # End-of-Day historical data
├── notebooks/                   # Jupyter Notebooks for analysis and backtesting
├── tests/                       # Unit test suite (unittest)
├── main.py                      # CLI/Docker entry point and orchestrator
└── pyproject.toml               # Project configuration, dependencies, and Ruff rules
```

---

## 2. Programming and Linting Standards (Ruff / Python 3.12+)

All new or modified code must pass **Ruff** validation without warnings or errors.

### 2.1. Import Management (`isort` / `I001`)
- Import blocks must be sorted alphabetically and organized into three groups separated by a single blank line:
  1. Python standard library (`datetime`, `json`, `logging`, `os`, `sys`, etc.).
  2. Third-party libraries (`requests`, `google.cloud.bigquery`, etc.).
  3. Local project modules (`engine`, `pipelines`).
- Imported members (`from typing import Any, ClassVar`) must be sorted alphabetically.

### 2.2. Static Typing (Python 3.12 Generics & Built-ins)
- **Use native types**: Use `list[...]`, `dict[...]`, `tuple[...]`, `set[...]`, `type[...]` instead of legacy types from `typing` (`List`, `Dict`, `Tuple`, etc.).
- **Modern union syntax**: Use `A | B` or `A | None` instead of `Union[A, B]` or `Optional[A]`.
- **Mutable class attributes (`RUF012`)**: Annotate mutable class-level dictionaries/lists with `ClassVar`, for example: `_strategies: ClassVar[dict[str, type[BaseStrategy]]] = {}`.
- **String Enums (`UP042`)**: Inherit directly from `enum.StrEnum` instead of `(str, Enum)`.

### 2.3. Date and Timezone Handling (`DTZ003` / `UP017`)
- **Never use `datetime.datetime.utcnow()`** (deprecated in Python 3.12+).
- Always use explicit UTC timezone dates:
  ```python
  import datetime

  # Correct:
  now = datetime.datetime.now(datetime.UTC)
  now_str = now.isoformat()
  ```

### 2.4. Logging (`LOG015`)
- **Do not call the root logger directly** (`logging.info(...)`, `logging.error(...)`).
- Always instantiate a per-module logger:
  ```python
  import logging

  logger = logging.getLogger(__name__)

  logger.info("Informational message")
  logger.warning("Warning message")
  logger.error("Error message")
  ```

### 2.5. Exception Handling and Suppression (`SIM105` / `BLE001`)
- Instead of `try: ... except (ValueError, TypeError): pass`, use `contextlib.suppress`:
  ```python
  import contextlib

  with contextlib.suppress(ValueError, TypeError):
      prices.append(float(close))
  ```
- If catching a generic exception in a dispatcher or orchestrator loop to prevent catastrophic failures, provide justification or mark with `# noqa: BLE001` alongside a descriptive error log.

---

## 3. Engine Extension Patterns (`engine`)

### 3.1. How to Add a New Strategy
1. Create the file in `engine/strategies/<strategy_name>.py`.
2. Inherit from `BaseStrategy` and implement `name` and `generate_signals(market_data: list[dict[str, Any]]) -> list[Signal]`.
3. Decorate the class with `@StrategyRegistry.register("<strategy_name>")`.
4. Import and expose the strategy in `engine/strategies/__init__.py`.

Example:
```python
import datetime
from typing import Any

from engine.models import Signal, SignalType
from engine.strategies.base import BaseStrategy
from engine.strategies.registry import StrategyRegistry


@StrategyRegistry.register("rsi_crossover")
class RSICrossoverStrategy(BaseStrategy):
    def __init__(self, rsi_period: int = 14, **kwargs: Any):
        super().__init__(rsi_period=rsi_period, **kwargs)
        self.rsi_period = rsi_period

    @property
    def name(self) -> str:
        return "rsi_crossover"

    def generate_signals(self, market_data: list[dict[str, Any]]) -> list[Signal]:
        # Signal calculation logic...
        return []
```

### 3.2. How to Add a New Output Sink
1. Create the file in `engine/sinks/<sink_name>.py`.
2. Inherit from `BaseSignalSink` and implement `send(signals: list[Signal]) -> None`.
3. Expose it in `engine/sinks/__init__.py`.

---

## 4. Quality Verification & Testing Commands

Before completing any task, run:

```bash
# 1. Ruff linter check & auto-fix
.venv/bin/ruff check --fix .

# 2. Code formatting with Ruff
.venv/bin/ruff format .

# 3. Verification check (0 errors, proper formatting)
.venv/bin/ruff check . && .venv/bin/ruff format --check .

# 4. Unit test suite execution
PYTHONPATH=. .venv/bin/python -m unittest discover tests
```
