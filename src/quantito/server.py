import argparse
import datetime
import logging
import sys
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from quantito.models import Signal
from quantito.strategies.registry import StrategyRegistry

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Quantito Strategy Engine API",
    version="0.1.0",
    description="HTTP API for quant strategy discovery and signal execution.",
)


class EvaluateRequest(BaseModel):
    symbol: str | None = Field(
        default=None, description="Optional default symbol for market data records."
    )
    params: dict[str, Any] = Field(
        default_factory=dict, description="Strategy configuration parameters."
    )
    market_data: list[dict[str, Any]] = Field(
        default_factory=list, description="Historical or real-time market data quotes/candles."
    )


class SignalResponse(BaseModel):
    symbol: str
    signal_type: str
    price: float
    timestamp: str
    strategy_name: str
    confidence: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluateResponse(BaseModel):
    strategy: str
    signals: list[SignalResponse]


class StrategiesResponse(BaseModel):
    strategies: list[str]


class HealthResponse(BaseModel):
    status: str
    timestamp: str


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check endpoint",
    tags=["System"],
)
@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    summary="API v1 Health check endpoint",
    tags=["System"],
)
def health_check() -> HealthResponse:
    """Return health status and current UTC timestamp."""
    now = datetime.datetime.now(datetime.UTC)
    return HealthResponse(status="ok", timestamp=now.isoformat())


@app.get(
    "/api/v1/strategies",
    response_model=StrategiesResponse,
    summary="List registered strategies",
    tags=["Strategies"],
)
def list_strategies() -> StrategiesResponse:
    """Introspect and list all strategies registered in StrategyRegistry."""
    return StrategiesResponse(strategies=StrategyRegistry.list_strategies())


@app.post(
    "/api/v1/strategies/{strategy_name}/evaluate",
    response_model=EvaluateResponse,
    summary="Evaluate market data using a named strategy",
    tags=["Strategies"],
)
def evaluate_strategy(strategy_name: str, payload: EvaluateRequest) -> EvaluateResponse:
    """
    Instantiate the specified strategy dynamically and evaluate provided market data to generate signals.
    """
    market_data = payload.market_data
    if payload.symbol:
        enriched_market_data: list[dict[str, Any]] = []
        for row in market_data:
            if isinstance(row, dict) and "symbol" not in row and "code" not in row:
                enriched_row = dict(row)
                enriched_row["symbol"] = payload.symbol
                enriched_market_data.append(enriched_row)
            else:
                enriched_market_data.append(row)
        market_data = enriched_market_data

    try:
        strategy = StrategyRegistry.create(strategy_name, **payload.params)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except TypeError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid strategy parameters: {e}",
        ) from e
    except Exception as e:
        logger.error(
            f"Unexpected error instantiating strategy '{strategy_name}': {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}",
        ) from e

    try:
        signals: list[Signal] = strategy.generate_signals(market_data)
        return EvaluateResponse(
            strategy=strategy.name,
            signals=[
                SignalResponse(
                    symbol=s.symbol,
                    signal_type=s.signal_type.value
                    if hasattr(s.signal_type, "value")
                    else str(s.signal_type),
                    price=s.price,
                    timestamp=s.timestamp.isoformat()
                    if isinstance(s.timestamp, datetime.datetime)
                    else str(s.timestamp),
                    strategy_name=s.strategy_name,
                    confidence=s.confidence,
                    metadata=s.metadata,
                )
                for s in signals
            ],
        )
    except Exception as e:
        logger.error(
            f"Unexpected error executing strategy '{strategy_name}': {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating signals: {e}",
        ) from e


def run_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Run the FastAPI Strategy Server using Uvicorn."""
    logger.info(f"Starting Quantito FastAPI Strategy Server on {host}:{port}...")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    parser = argparse.ArgumentParser(description="Quantito Strategy Execution FastAPI Server")
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host address to bind (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port number to listen on (default: 8080)",
    )

    args = parser.parse_args()
    run_server(host=args.host, port=args.port)
