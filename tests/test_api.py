"""API-side checkpoints. The Inngest client's send() is replaced by a recorder, so these run without the Dev Server.
The background functions themselves were verified end-to-end against the Dev Server (see README)."""
import time

import pytest
from fastapi.testclient import TestClient

import main
from store import REPORTS


@pytest.fixture
def sent(monkeypatch):
    events = []

    async def fake_send(event, **_):
        events.append(event)
        return ["evt-1"]

    monkeypatch.setattr(main.inngest_client, "send", fake_send)
    REPORTS.clear()
    return events


client = TestClient(main.app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_post_is_202_fast_and_sends_one_event(sent):
    start = time.perf_counter()
    r = client.post("/reports", json={"topic": "cats"})
    assert time.perf_counter() - start < 1
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "pending" and body["id"]
    assert len(sent) == 1
    assert sent[0].name == "report/requested"
    assert sent[0].data == {"id": body["id"], "topic": "cats"}


def test_status_is_pending_until_the_job_writes_done(sent):
    rid = client.post("/reports", json={"topic": "cats"}).json()["id"]
    assert client.get(f"/reports/{rid}").json()["status"] == "pending"
    REPORTS[rid].update(status="done", result="...")  # what the build-report step does
    assert client.get(f"/reports/{rid}").json()["status"] == "done"


def test_unknown_id_is_404(sent):
    r = client.get("/reports/nope")
    assert r.status_code == 404 and r.json() == {"error": "Report nope not found"}


@pytest.mark.parametrize("payload", [{}, {"topic": ""}, {"subject": "cats"}, None])
def test_bad_input_is_400_and_starts_no_job(sent, payload):
    r = client.post("/reports", json=payload) if payload is not None else client.post("/reports")
    assert r.status_code == 400 and "error" in r.json()
    assert sent == []
    assert REPORTS == {}


def test_list_reports(sent):
    client.post("/reports", json={"topic": "a"})
    client.post("/reports", json={"topic": "b"})
    assert [r["topic"] for r in client.get("/reports").json()] == ["a", "b"]


def test_functions_are_registered():
    ids = {f.local_id for f in main.functions}
    assert ids >= {"say-hello", "make-report", "heartbeat", "cleanup"}
