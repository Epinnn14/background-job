"""The worker in the other room: the Inngest client and the background functions."""
import datetime

import inngest

# is_production=False → talk to the local Inngest Dev Server (localhost:8288), no keys needed.
inngest_client = inngest.Inngest(app_id="report-api", is_production=False)


@inngest_client.create_function(fn_id="say-hello", trigger=inngest.TriggerEvent(event="test/hello"))
async def say_hello(ctx: inngest.Context) -> str:
    await ctx.step.sleep("wait-a-moment", datetime.timedelta(seconds=5))
    return "Hello from the background!"


functions = [say_hello]
