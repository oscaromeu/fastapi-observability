"""Domain (business) metrics — separate from the HTTP/RED metrics emitted by
the PrometheusMiddleware in utils.py.

Naming follows Prometheus conventions:
- snake_case
- Counters end in _total
- Histograms carry the unit (_seconds)
- Prefix with the application/domain name (app_) to avoid collisions when
  multiple exporters scrape into the same Prometheus.
"""

from typing import Dict

from opentelemetry import trace
from prometheus_client import Counter, Gauge, Histogram

ITEMS_LOOKUP = Counter(
    "app_items_lookup_total",
    "Total items looked up by id bucket.",
    ["app_name", "bucket"],
)

CHAIN_CALLS = Counter(
    "app_chain_calls_total",
    "Total /chain invocations by outcome.",
    ["app_name", "outcome"],
)

CHAIN_DURATION = Histogram(
    "app_chain_duration_seconds",
    "End-to-end duration of /chain in seconds (with trace exemplar).",
    ["app_name"],
)

CHAIN_IN_PROGRESS = Gauge(
    "app_chain_in_progress",
    "Number of /chain calls currently in flight.",
    ["app_name"],
)

TASKS_FINISHED = Counter(
    "app_tasks_finished_total",
    "Tasks finished, by type (io / cpu).",
    ["app_name", "task_type"],
)


def trace_id_exemplar() -> Dict[str, str]:
    """Return {'TraceID': <hex>} for the current span, or {} if no active span.

    The empty-dict fallback is important: Histogram.observe(..., exemplar={})
    silently skips the exemplar instead of recording trace_id=00000... which
    would point Grafana to a nonexistent trace.
    """
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if not ctx or ctx.trace_id == 0:
        return {}
    return {"TraceID": trace.format_trace_id(ctx.trace_id)}


def item_bucket(item_id: int) -> str:
    """Bucket an item id into a low-cardinality label value.

    Keeping cardinality bounded (3 distinct values) prevents the metric series
    from exploding — a separate series per literal item_id would melt
    Prometheus.
    """
    if item_id <= 100:
        return "low"
    if item_id <= 1000:
        return "mid"
    return "high"
