"""Report API: slow work leaves the request and runs as a background job (FlyRank Backend track, A7)."""
import inngest.fast_api
from fastapi import FastAPI

from jobs import functions, inngest_client

app = FastAPI(title="Report API", version="1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


# The Dev Server finds and calls our functions through this one path: /api/inngest
inngest.fast_api.serve(app, inngest_client, functions)
