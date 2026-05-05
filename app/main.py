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
    CHAIN_CALLS,
    CHAIN_DURATION,
    CHAIN_IN_PROGRESS,
    ITEMS_LOOKUP,
    TASKS_FINISHED,
    item_bucket,
    trace_id_exemplar,
)
from telemetry import PrometheusMiddleware, metrics, setting_otlp

APP_NAME = os.environ.get("APP_NAME", "app")
EXPOSE_PORT = os.environ.get("EXPOSE_PORT", 8000)
OTLP_GRPC_ENDPOINT = os.environ.get("OTLP_GRPC_ENDPOINT", "http://otel-collector:4317")

TARGET_ONE_HOST = os.environ.get("TARGET_ONE_HOST", "app-b")
TARGET_TWO_HOST = os.environ.get("TARGET_TWO_HOST", "app-c")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Single httpx.AsyncClient shared across requests — enables connection
    # pooling instead of opening fresh sockets per call in /chain.
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


@app.get("/items/{item_id}")
async def read_item(item_id: int, q: Optional[str] = None):
    ITEMS_LOOKUP.labels(app_name=APP_NAME, bucket=item_bucket(item_id)).inc()
    logging.info("items")
    return {"item_id": item_id, "q": q}


@app.get("/io_task")
async def io_task():
    await asyncio.sleep(1)
    TASKS_FINISHED.labels(app_name=APP_NAME, task_type="io").inc()
    logging.info("io task")
    return "IO bound task finish!"


@app.get("/cpu_task")
async def cpu_task():
    for i in range(1000):
        _ = i * i * i
    TASKS_FINISHED.labels(app_name=APP_NAME, task_type="cpu").inc()
    logging.info("cpu task")
    return "CPU bound task finish!"


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


@app.get("/chain")
async def chain(request: Request):
    headers: dict = {}
    inject(headers)  # inject trace info to header
    logging.info("chain headers: %s", headers)

    CHAIN_IN_PROGRESS.labels(app_name=APP_NAME).inc()
    start = time.perf_counter()
    outcome = "success"
    try:
        client: httpx.AsyncClient = request.app.state.httpx
        await client.get("http://localhost:8000/", headers=headers)
        await client.get(f"http://{TARGET_ONE_HOST}:8000/io_task", headers=headers)
        await client.get(f"http://{TARGET_TWO_HOST}:8000/cpu_task", headers=headers)
        logging.info("Chain Finished")
        return {"path": "/chain"}
    except Exception:
        outcome = "error"
        raise
    finally:
        CHAIN_IN_PROGRESS.labels(app_name=APP_NAME).dec()
        CHAIN_CALLS.labels(app_name=APP_NAME, outcome=outcome).inc()
        CHAIN_DURATION.labels(app_name=APP_NAME).observe(
            time.perf_counter() - start, exemplar=trace_id_exemplar()
        )


if __name__ == "__main__":
    # update uvicorn access logger format
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"][
        "fmt"
    ] = "%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] [trace_id=%(otelTraceID)s span_id=%(otelSpanID)s resource.service.name=%(otelServiceName)s] - %(message)s"
    uvicorn.run(app, host="0.0.0.0", port=EXPOSE_PORT, log_config=log_config)
