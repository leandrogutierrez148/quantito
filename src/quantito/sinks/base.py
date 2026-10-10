from abc import ABC, abstractmethod

from quantito.models import Signal


class BaseSignalSink(ABC):
    """Abstract interface for receiving and persisting or dispatching generated signals."""

    @abstractmethod
    def send(self, signals: list[Signal]) -> None:
        """Process and send/store signals."""
