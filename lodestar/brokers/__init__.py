from lodestar.brokers.base import BaseBroker
from lodestar.brokers.paper import PaperBroker

# RobinhoodBroker is imported lazily because robin_stocks pulls in
# cryptography and other heavy dependencies at import time.


def __getattr__(name: str):
    if name == "RobinhoodBroker":
        from lodestar.brokers.robinhood import RobinhoodBroker

        return RobinhoodBroker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["BaseBroker", "RobinhoodBroker", "PaperBroker"]
