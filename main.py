import json
import logging
import time
import uuid
from collections import deque
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

app = FastAPI()

# This counter is shared by the endpoints in this single app process.
REQUESTS = Counter("http_requests_total", "Total HTTP requests")

# Start time is saved once when this Python process imports the app.
START_TIME = time.monotonic()

# Keep recent log entries in memory for /logs/tail.
recent_logs = deque(maxlen=1000)

# Print each log entry as one JSON object.
logger = logging.getLogger("request_logs")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())

    try:
        response = await call_next(request)
        return response
    finally:
        # Count every request, including requests to /metrics and /healthz.
        REQUESTS.inc()

        entry = {
            "level": "INFO",
            "ts": datetime.now(timezone.utc).isoformat(),
            "path": request.url.path,
            "request_id": request_id,
            "method": request.method,
        }

        recent_logs.append(entry)
        logger.info(json.dumps(entry))


@app.get("/work")
async def work(n: int = 1):
    # Avoid accidentally doing an excessive amount of work.
    n = max(0, min(n, 100000))

    # A simple, repeatable amount of CPU work per unit.
    total = sum(range(n))
    _ = total

    # Replace this with the email address required by your assignment.
    return {"email": "24f3003806@ds.study.iitm.ac.in", "done": n}


@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/healthz")
async def healthz():
    uptime = max(0.0, time.monotonic() - START_TIME)
    return {"status": "ok", "uptime_s": float(uptime)}


@app.get("/logs/tail")
async def logs_tail(limit: int = 100):
    limit = max(0, min(limit, 1000))
    if limit == 0:
        return []
    return list(recent_logs)[-limit:]