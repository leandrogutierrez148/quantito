# AGENTS.md - Quantito Development & Implementation Standards

This file serves as the central reference for AI agents and developers working on the **Quantito** repository. It documents the system architecture, programming standards, and linting/formatting best practices.

---

## 1. General Project Architecture

Quantito is the quantitative strategy evaluation and signal generation microservice within the **Quantito Financial Platform**. Built with Python 3.12+ and FastAPI, it evaluates market data with quantitative algorithms and emits standardized trading signals via REST API.

### Ecosystem Overview
1. **`quantito-pipe`**: Ingests market quotes (EOD, Delayed, Real-time) from EODHD into Google Cloud BigQuery.
2. **`quantito`** *(this repository)*: Pure, stateless quantitative strategy computation service (`src/quantito`).
3. **`quantito-engine`**: Orchestrator (Go / Echo / MySQL) managing experiments, concurrency locks, signal ledgers, and dispatching.

### Directory Structure

```
quantito/
├── src/
│   └── quantito/                # Core quantitative package (PEP 518/621 src-layout)
│       ├── __init__.py          # Exports public API (Signal, SignalType, BaseStrategy, StrategyRegistry)
│       ├── api.py               # FastAPI application, routes, and Pydantic schemas
│       ├── core.py              # SignalEngine orchestrator (Strategy pattern)
│       ├── models.py            # Data models: Signal (dataclass), SignalType (StrEnum)
│       └── strategies/          # Quantitative strategy implementations
│           ├── __init__.py      # Auto-registration of available strategies
│           ├── base.py          # Abstract BaseStrategy class
│           ├── registry.py      # StrategyRegistry (decorator & dynamic factory)
│           ├── fifty_day_avg.py # 50-day moving average strategy
│           └── price_momentum.py# Price momentum / percentage change strategy
├── tests/                       # Unit test suite (unittest)
├── main.py                      # CLI entrypoint and Uvicorn server launcher
└── pyproject.toml               # Project configuration, dependencies, and Ruff rules
```

---

## 2. Programming and Linting Standards (Ruff / Python 3.12+)

All new or modified code must pass **Ruff** validation without warnings or errors.

### 2.1. Import Management (`isort` / `I001`)
- Import blocks must be sorted alphabetically and organized into three groups separated by a single blank line:
  1. Python standard library (`datetime`, `json`, `logging`, `os`, `sys`, etc.).
  2. Third-party libraries (`fastapi`, `pydantic`, `uvicorn`, etc.).
  3. Local project modules (`quantito`).
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

## 3. Engine Extension Patterns (`quantito.strategies`)

### 3.1. How to Add a New Strategy
1. Create the file in `src/quantito/strategies/<strategy_name>.py`.
2. Inherit from `BaseStrategy` and implement `name` and `generate_signals(market_data: list[dict[str, Any]]) -> list[Signal]`.
3. Decorate the class with `@StrategyRegistry.register("<strategy_name>")`.
4. Import and expose the strategy in `src/quantito/strategies/__init__.py`.

Example:
```python
import datetime
from typing import Any

from quantito.models import Signal, SignalType
from quantito.strategies.base import BaseStrategy
from quantito.strategies.registry import StrategyRegistry


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
.venv/bin/python -m unittest discover tests
```

---

## 5. Git Workflow & Branch Management

All AI agents and developers must adhere to the mandatory branch and worktree policy before implementing changes:

- **Dedicated Branching**: Always create a new branch or worktree for any requirement. Direct commits to `main` or `master` are strictly forbidden.
- **Naming Pattern**: `<type>/<short-kebab-case-description>` (e.g., `fix/dockerfile-with-pyproject`, `feat/rsi-indicator`, `docs/update-architecture`).
- **Commit Messages**: Plain, concise descriptions without `<type>(scope):` prefixes.
- **Full Specification**: Detailed rule definition is located in [`.agents/rules/git-workflow.md`](file:///.agents/rules/git-workflow.md).
