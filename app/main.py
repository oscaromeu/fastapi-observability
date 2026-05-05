import asyncio
import logging
import os
import random
import time
from contextlib import asynccontextmanager
from typing import Optional

import httpx
import uvicorn
from fastapi import FastAPI, Request, Response
from opentelemetry.propagate import inject

from business_metrics import (
    CHECKOUT_DURATION,
    CHECKOUTS_IN_PROGRESS,
    CHECKOUTS_TOTAL,
    JOBS_FINISHED,
    PRODUCT_VIEWS,
    price_tier,
    trace_id_exemplar,
)
from telemetry import PrometheusMiddleware, metrics, setting_otlp

APP_NAME = os.environ.get("APP_NAME", "app")
EXPOSE_PORT = os.environ.get("EXPOSE_PORT", 8000)
OTLP_GRPC_ENDPOINT = os.environ.get("OTLP_GRPC_ENDPOINT", "http://otel-collector:4317")

TARGET_ONE_HOST = os.environ.get("TARGET_ONE_HOST", "app-b")
TARGET_TWO_HOST = os.environ.get("TARGET_TWO_HOST", "app-c")

# Chaos injection for /checkout. Defaults to 0.0 (no synthetic failures).
# Set CHECKOUT_ERROR_RATE=0.05 to make ~5% of /checkout calls raise on
# purpose, so the "Checkout Error Ratio" panel shows real data during demos.
CHECKOUT_ERROR_RATE = float(os.environ.get("CHECKOUT_ERROR_RATE", "0.0"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Single httpx.AsyncClient shared across requests — enables connection
    # pooling instead of opening fresh sockets per call in /checkout.
    async with httpx.AsyncClient() as client:
        app.state.httpx = client
        yield


app = FastAPI(lifespan=lifespan)

# Setting metrics middleware
app.add_middleware(PrometheusMiddleware, app_name=APP_NAME)
app.add_route("/metrics", metrics)

# Setting OpenTelemetry exporter
setting_otlp(app, APP_NAME, OTLP_GRPC_ENDPOINT)


class EndpointFilter(logging.Filter):
    # Uvicorn endpoint access log filter
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("GET /metrics") == -1


# Filter out /endpoint
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())


@app.get("/")
async def read_root():
    logging.info("Hello World")
    return {"Hello": "World"}


@app.get("/products/{product_id}")
async def read_product(product_id: int, q: Optional[str] = None):
    PRODUCT_VIEWS.labels(app_name=APP_NAME, tier=price_tier(product_id)).inc()
    logging.info("product view")
    return {"product_id": product_id, "q": q}


@app.get("/charge_card")
async def charge_card():
    # I/O-bound: simulate calling the payment provider over the network.
    await asyncio.sleep(1)
    JOBS_FINISHED.labels(app_name=APP_NAME, job_type="charge").inc()
    logging.info("charge_card job finished")
    return "Card charged!"


@app.get("/calculate_tax")
async def calculate_tax():
    # CPU-bound: simulate computing tax / discounts on the basket.
    for i in range(1000):
        _ = i * i * i
    JOBS_FINISHED.labels(app_name=APP_NAME, job_type="tax").inc()
    logging.info("calculate_tax job finished")
    return "Tax calculated!"


@app.get("/random_status")
async def random_status(response: Response):
    response.status_code = random.choice([200, 200, 300, 400, 500])
    logging.info("random status")
    return {"path": "/random_status"}


@app.get("/random_sleep")
async def random_sleep(response: Response):
    await asyncio.sleep(random.randint(0, 5))
    logging.info("random sleep")
    return {"path": "/random_sleep"}


@app.get("/error_test")
async def error_test(response: Response):
    logging.error("got error!!!!")
    raise ValueError("value error")


@app.get("/checkout")
async def checkout(request: Request):
    headers: dict = {}
    inject(headers)  # inject trace info to header
    logging.info("checkout headers: %s", headers)

    CHECKOUTS_IN_PROGRESS.labels(app_name=APP_NAME).inc()
    start = time.perf_counter()
    outcome = "success"
    try:
        if CHECKOUT_ERROR_RATE > 0 and random.random() < CHECKOUT_ERROR_RATE:
            raise RuntimeError("synthetic checkout failure (CHECKOUT_ERROR_RATE)")
        client: httpx.AsyncClient = request.app.state.httpx
        await client.get("http://localhost:8000/", headers=headers)
        await client.get(f"http://{TARGET_ONE_HOST}:8000/charge_card", headers=headers)
        await client.get(f"http://{TARGET_TWO_HOST}:8000/calculate_tax", headers=headers)
        logging.info("checkout finished")
        return {"path": "/checkout"}
    except Exception:
        outcome = "error"
        raise
    finally:
        CHECKOUTS_IN_PROGRESS.labels(app_name=APP_NAME).dec()
        CHECKOUTS_TOTAL.labels(app_name=APP_NAME, outcome=outcome).inc()
        CHECKOUT_DURATION.labels(app_name=APP_NAME).observe(
            time.perf_counter() - start, exemplar=trace_id_exemplar()
        )


if __name__ == "__main__":
    # update uvicorn access logger format
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"][
        "fmt"
    ] = "%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] [trace_id=%(otelTraceID)s span_id=%(otelSpanID)s resource.service.name=%(otelServiceName)s] - %(message)s"
    uvicorn.run(app, host="0.0.0.0", port=EXPOSE_PORT, log_config=log_config)
