from lodestar.strategies.base import BaseStrategy
from lodestar.strategies.momentum import MomentumStrategy
from lodestar.strategies.mean_reversion import MeanReversionStrategy
from lodestar.strategies.sentiment_strategy import SentimentStrategy

STRATEGY_REGISTRY: dict[str, type[BaseStrategy]] = {
    "momentum": MomentumStrategy,
    "mean_reversion": MeanReversionStrategy,
    "sentiment": SentimentStrategy,
}

__all__ = [
    "BaseStrategy",
    "MomentumStrategy",
    "MeanReversionStrategy",
    "SentimentStrategy",
    "STRATEGY_REGISTRY",
]
