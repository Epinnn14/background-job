"""The worker in the other room: the Inngest client and the background functions."""
import datetime

import inngest

from store import REPORTS

# is_production=False → talk to the local Inngest Dev Server (localhost:8288), no keys needed.
inngest_client = inngest.Inngest(app_id="report-api", is_production=False)


@inngest_client.create_function(fn_id="say-hello", trigger=inngest.TriggerEvent(event="test/hello"))
async def say_hello(ctx: inngest.Context) -> str:
    await ctx.step.sleep("wait-a-moment", datetime.timedelta(seconds=5))
    return "Hello from the background!"


@inngest_client.create_function(fn_id="make-report", trigger=inngest.TriggerEvent(event="report/requested"))
async def make_report(ctx: inngest.Context) -> dict:
    report_id, topic = ctx.event.data["id"], ctx.event.data["topic"]

    # stand-in for the real slow work (an AI call, a big export): the request is long gone by now
    await ctx.step.sleep("do-the-slow-work", datetime.timedelta(seconds=8))

    async def build() -> dict:
        result = f"Report on '{topic}': 3 key facts, 2 charts, 1 conclusion."
        finished = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        REPORTS[report_id] = {"id": report_id, "topic": topic, "status": "done", "result": result,
                              "finished_at": finished}
        return REPORTS[report_id]

    return await ctx.step.run("build-report", build)


functions = [say_hello, make_report]
