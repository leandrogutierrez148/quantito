# Quantito Strategy Engine

**Quantito** is a Python quantitative analysis and strategy execution engine. It provides a modular Strategy architecture as well as a FastAPI HTTP server for dynamic strategy evaluation and real-time trade signal generation.

> **Note**: Data ingestion pipelines are managed by [`quantito-pipe`](file:///Users/lgutierrez/Proyectos/quantito-pipe), and experiment orchestration, signal persistence, and dispatching are handled by [`quantito-engine`](file:///Users/lgutierrez/Proyectos/quantito-engine).

---

## Features

- **Strategy Engine (`quantito`)**: Extensible registry pattern (`StrategyRegistry`) supporting pluggable quantitative strategies (e.g. 50-Day Moving Average, Price Momentum, RSI, etc.).
- **FastAPI HTTP Execution API**: REST endpoints for dynamic strategy discovery and on-demand signal evaluation.
- **Strict Typing & Linting**: Built on Python 3.12+ with native typing, full Ruff linting compliance, and 100% unit test coverage.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` / `/api/v1/health` | Healthcheck and UTC timestamp |
| `GET` | `/api/v1/strategies` | List registered quantitative strategies |
| `POST` | `/api/v1/strategies/{name}/evaluate` | Evaluate market data with a named strategy |

---

## Local Development & Execution

```bash
# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run Ruff linter and formatter checks
ruff check . && ruff format --check .

# Run unit tests
python -m unittest discover tests

# Start the Strategy Execution Server
python main.py --host 0.0.0.0 --port 8080
```

---

## Docker Execution

The project provides an optimized, unprivileged `Dockerfile` based on `python:3.12-slim`:

```bash
# Build the image
docker build -t quantito-engine:latest .

# Run the container
docker run -p 8080:8080 quantito-engine:latest
```
