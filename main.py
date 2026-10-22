"""Report API: slow work leaves the request and runs as a background job (FlyRank Backend track, A7)."""
import logging
import uuid

import inngest
import inngest.fast_api
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from jobs import functions, inngest_client
from store import REPORTS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")  # show the heartbeat line
app = FastAPI(title="Report API", version="1.0")


class ReportRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=100)


@app.exception_handler(RequestValidationError)
async def bad_input(_request: Request, exc: RequestValidationError):
    # a wrong *input* is rejected at the door with 400, and no event is sent, so no job and no retries
    first = exc.errors()[0]
    field = ".".join(str(x) for x in first["loc"] if x != "body") or "body"
    return JSONResponse(status_code=400, content={"error": f"{field}: {first['msg']}"})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/reports", status_code=202)
async def create_report(body: ReportRequest):
    report_id = uuid.uuid4().hex[:8]
    REPORTS[report_id] = {"id": report_id, "topic": body.topic, "status": "pending"}
    # hand the slow work to the background: send an event and answer right away, with no waiting
    await inngest_client.send(inngest.Event(name="report/requested", data={"id": report_id, "topic": body.topic}))
    return {"id": report_id, "status": "pending"}


@app.get("/reports/{report_id}")
def get_report(report_id: str):
    if report_id not in REPORTS:
        return JSONResponse(status_code=404, content={"error": f"Report {report_id} not found"})
    return REPORTS[report_id]


# The Dev Server finds and calls our functions through this one path: /api/inngest
inngest.fast_api.serve(app, inngest_client, functions)
