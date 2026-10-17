import json
import logging
import os
import time
import uuid
from collections import deque
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

app = FastAPI()

EMAIL = os.getenv("EMAIL", "your-email@example.com")
START_TIME = time.monotonic()

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests"
)

LOG_ENTRIES = deque(maxlen=1000)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("observability")


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    REQUEST_COUNT.inc()

    try:
        response = await call_next(request)
    except Exception:
        entry = {
            "level": "ERROR",
            "ts": datetime.now(timezone.utc).isoformat(),
            "path": request.url.path,
            "request_id": request_id,
        }
        LOG_ENTRIES.append(entry)
        logger.error(json.dumps(entry))
        raise

    entry = {
        "level": "INFO",
        "ts": datetime.now(timezone.utc).isoformat(),
        "path": request.url.path,
        "request_id": request_id,
    }

    LOG_ENTRIES.append(entry)
    logger.info(json.dumps(entry))
    response.headers["X-Request-ID"] = request_id

    return response


@app.get("/work")
async def work(n: int = 1):
    n = max(0, min(n, 100000))
    total = 0

    for i in range(n):
        total += i

    return {"email": EMAIL, "done": n}


@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.get("/healthz")
async def healthz():
    return {
        "status": "ok",
        "uptime_s": float(max(0, time.monotonic() - START_TIME))
    }


@app.get("/logs/tail")
async def logs_tail(limit: int = 10):
    limit = max(0, min(limit, 1000))
    return list(LOG_ENTRIES)[-limit:] if limit else []
