"""log-sentinel: Logging and metrics collection for scientific computing infrastructure."""

from .aggregator import LogAggregator
from .alerting import AlertDispatcher, AlertEvaluator
from .config import SentinelConfig, load_config
from .metrics import Counter, Gauge, Histogram, MetricsRegistry, MetricsServer
from .structured_logger import ContextLogger, StructuredFormatter, get_logger

__version__ = "0.1.0"

__all__ = [
    "get_logger",
    "StructuredFormatter",
    "ContextLogger",
    "MetricsRegistry",
    "MetricsServer",
    "Counter",
    "Gauge",
    "Histogram",
    "LogAggregator",
    "AlertEvaluator",
    "AlertDispatcher",
    "load_config",
    "SentinelConfig",
]
