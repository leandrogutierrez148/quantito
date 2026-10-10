import json
import logging

from quantito.models import Signal
from quantito.sinks.base import BaseSignalSink

logger = logging.getLogger(__name__)


class ConsoleSignalSink(BaseSignalSink):
    """Prints generated signals to stdout in a clean, readable format."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def send(self, signals: list[Signal]) -> None:
        if not signals:
            logger.info("[ConsoleSignalSink] No signals to display.")
            return

        print(
            f"\n==================== SIGNAL ENGINE OUTPUT ({len(signals)} SIGNALS) ===================="
        )
        for idx, sig in enumerate(signals, 1):
            metadata_str = json.dumps(sig.metadata)
            print(
                f"[{idx:02d}] {sig.signal_type.value:<4} | {sig.symbol:<10} | Price: ${sig.price:<9.2f} | "
                f"Strategy: {sig.strategy_name:<16} | Conf: {sig.confidence:.2f} | Meta: {metadata_str}"
            )
        print("========================================================================\n")
