"""Report API: slow work leaves the request and runs as a background job (FlyRank Backend track, A7)."""
from fastapi import FastAPI

app = FastAPI(title="Report API", version="1.0")


@app.get("/health")
def health():
    return {"status": "ok"}
