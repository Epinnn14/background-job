"""The worker in the other room: the Inngest client and the background functions."""
import datetime
from pathlib import Path

import inngest

from store import REPORTS

# is_production=False → talk to the local Inngest Dev Server (localhost:8288), no keys needed.
inngest_client = inngest.Inngest(app_id="report-api", is_production=False)
OUTBOX = Path("outbox")


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


@inngest_client.create_function(fn_id="say-hello", trigger=inngest.TriggerEvent(event="test/hello"))
async def say_hello(ctx: inngest.Context) -> str:
    await ctx.step.sleep("wait-a-moment", datetime.timedelta(seconds=5))
    return "Hello from the background!"


async def mark_failed(ctx: inngest.Context) -> None:
    # runs once, after the last retry has failed: record it so clients (and the heartbeat) can see it
    original = ctx.event.data["event"]["data"]
    error = ctx.event.data.get("error", {}).get("message", "unknown error")
    REPORTS[original["id"]] = {"id": original["id"], "topic": original["topic"], "status": "failed", "error": error}


@inngest_client.create_function(
    fn_id="make-report",
    trigger=inngest.TriggerEvent(event="report/requested"),
    retries=2,              # 1 attempt + 2 retries = 3 attempts, then the run is Failed
    on_failure=mark_failed,
    concurrency=[inngest.Concurrency(limit=2)],  # stretch: at most 2 reports build at the same moment
)
async def make_report(ctx: inngest.Context) -> dict:
    report_id, topic = ctx.event.data["id"], ctx.event.data["topic"]

    def already_built() -> dict | None:
        current = REPORTS.get(report_id)
        return current if current and current["status"] == "done" else None

    async def check() -> dict | None:
        return already_built()

    # stretch, idempotency: the same event delivered twice must not build (or "email") twice.
    # It's a *step* on purpose: Inngest re-enters this function after every step, and code outside a step runs
    # again each time. A bare `if` here would see the report this very run just built and skip the email.
    if (done := await ctx.step.run("check-not-built-yet", check)) is not None:
        return {"skipped": "already built", **done}

    # stand-in for the real slow work (an AI call, a big export): the request is long gone by now
    await ctx.step.sleep("do-the-slow-work", datetime.timedelta(seconds=8))

    async def build() -> dict:
        if (done := already_built()) is not None:      # check again: a twin run may have finished meanwhile
            return {"skipped": "already built", **done}
        if topic == "fail":
            raise RuntimeError("The report oven is broken!")  # a wrong *moment*: worth retrying
        result = f"Report on '{topic}': 3 key facts, 2 charts, 1 conclusion."
        # written from the event, not read from the store: if the API restarted mid-job, the record comes back
        REPORTS[report_id] = {"id": report_id, "topic": topic, "status": "done", "result": result,
                              "finished_at": now_iso()}
        return REPORTS[report_id]

    report = await ctx.step.run("build-report", build)

    async def send_email() -> str:
        # extra: the "email". A real product would send mail here; a file in outbox/ stands in for it.
        OUTBOX.mkdir(exist_ok=True)
        path = OUTBOX / f"{report_id}.txt"
        path.write_text(f"To: you@example.com\nSubject: Your report on '{topic}' is ready\n\n{report['result']}\n"
                        f"Status: GET /reports/{report_id}\n", encoding="utf-8")
        return str(path)

    if "skipped" not in report:
        await ctx.step.run("send-email", send_email)
    return report


@inngest_client.create_function(fn_id="heartbeat", trigger=inngest.TriggerCron(cron="* * * * *"))
async def heartbeat(ctx: inngest.Context) -> dict:
    # no endpoint and no event: the clock is the only trigger (every minute, for testing; a real one runs daily)
    counts = {status: sum(r["status"] == status for r in REPORTS.values()) for status in ("pending", "done", "failed")}
    line = f"heartbeat: {counts['pending']} pending, {counts['done']} done, {counts['failed']} failed"
    ctx.logger.info(line)
    return {"summary": line, **counts}


@inngest_client.create_function(fn_id="cleanup", trigger=inngest.TriggerCron(cron="*/5 * * * *"))
async def cleanup(ctx: inngest.Context) -> dict:
    # extra: cron's most common real job is taking out the trash. Every 5 minutes, forget done reports > 10 min old.
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)
    old = [rid for rid, r in REPORTS.items()
           if r["status"] == "done" and datetime.datetime.fromisoformat(r["finished_at"]) < cutoff]
    for rid in old:
        REPORTS.pop(rid, None)
    ctx.logger.info(f"cleanup: removed {len(old)} old report(s)")
    return {"removed": old}


functions = [say_hello, make_report, heartbeat, cleanup]
