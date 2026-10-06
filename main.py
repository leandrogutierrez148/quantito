import argparse
import logging
import os
import sys

from engine.server import run_server

# Configure logging to output to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def main(host: str | None = None, port: int | None = None) -> int:
    """Entry point for the Quantito Strategy Engine Server."""
    host = host or os.getenv("HOST", "0.0.0.0")
    if port is None:
        port = int(os.getenv("PORT", "8080"))

    logger.info("Starting Quantito Strategy Execution Server on %s:%d...", host, port)
    run_server(host=host, port=port)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quantito Strategy Execution Server")
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("HOST", "0.0.0.0"),
        help="Host address for HTTP server (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8080")),
        help="Port number for HTTP server (default: 8080)",
    )

    args = parser.parse_args()
    sys.exit(main(host=args.host, port=args.port))
