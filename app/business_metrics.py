"""Domain (business) metrics — separate from the HTTP/RED metrics emitted by
the PrometheusMiddleware in telemetry.py.

The toy domain is a tiny e-commerce shop: a checkout that charges a card and
calculates tax. Endpoints in main.py correspond 1:1 to the metrics here so a
reader can map "Checkout RPS" / "Product views by price tier" straight to a
real-world flow they already understand.

Naming follows Prometheus conventions:
- snake_case
- Counters end in _total
- Histograms carry the unit (_seconds)
- Prefix with the application/domain name (shop_) to avoid collisions when
  multiple exporters scrape into the same Prometheus.
"""

from typing import Dict

from opentelemetry import trace
from prometheus_client import Counter, Gauge, Histogram

PRODUCT_VIEWS = Counter(
    "shop_product_views_total",
    "Total product page views by price tier.",
    ["app_name", "tier"],
)

CHECKOUTS_TOTAL = Counter(
    "shop_checkouts_total",
    "Total /checkout invocations by outcome.",
    ["app_name", "outcome"],
)

CHECKOUT_DURATION = Histogram(
    "shop_checkout_duration_seconds",
    "End-to-end duration of /checkout in seconds (with trace exemplar).",
    ["app_name"],
)

CHECKOUTS_IN_PROGRESS = Gauge(
    "shop_checkouts_in_progress",
    "Number of /checkout calls currently in flight.",
    ["app_name"],
)

JOBS_FINISHED = Counter(
    "shop_jobs_finished_total",
    "Background jobs finished, by type (charge / tax).",
    ["app_name", "job_type"],
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


def price_tier(product_id: int) -> str:
    """Bucket a product id into a low-cardinality price tier.

    Putting product_id literally as a label would explode Prometheus once the
    catalogue grows. Three tiers keep the series count bounded while still
    revealing the shape of the traffic (cheap impulse buys vs. premium items).
    """
    if product_id <= 100:
        return "cheap"
    if product_id <= 1000:
        return "mid"
    return "premium"
