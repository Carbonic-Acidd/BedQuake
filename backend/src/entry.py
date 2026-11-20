# The Cloudflare Worker. Static files in web/dist are served before this runs;
# only /api/* requests reach this code. Every endpoint publishes to the Pico through EMQX.
# Every request must carry the shared password (APP_PASSWORD) in its Authorization header.
import hmac
import json
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from workers import Response, WorkerEntrypoint, asgi

import calendar_job
import emqx

# The backend's settings, all Worker secrets (uploaded from .env by `make secrets`).
CONFIG_KEYS = ["ICS_URL", "EMQX_API_URL", "EMQX_API_KEY", "EMQX_API_SECRET",
               "ALARM_OFFSET_MIN", "DEVICE_ID", "APP_PASSWORD"]
DEFAULT_DEVICE_ID = "bed1"
PICO_CLIENT_PREFIX = "shakeawake-"   # the Pico's MQTT client id is this + DEVICE_ID (pico/net.py)
MAX_TEST_S = 90           # the Pico won't play a test longer than this either
PAYLOAD_VERSION = 1       # the "v" field in alarm messages, bumped if their shape changes

app = FastAPI()


class Test(BaseModel):
    pattern: str = Field(min_length=1, max_length=20)
    seconds: int = Field(default=10, ge=1, le=MAX_TEST_S)


class Alarm(BaseModel):
    time: int             # UTC Unix seconds
    pattern: str = Field(min_length=1, max_length=20)


class AlarmType(BaseModel):
    pattern: str = Field(min_length=1, max_length=20)


def device_id(env):
    return getattr(env, "DEVICE_ID", None) or DEFAULT_DEVICE_ID


def topic(env, name):
    return f"shakeawake/{device_id(env)}/{name}"


async def send(env, name, payload, retain=False):
    # Retained alarm messages use QoS 1 so the broker confirms it stored them.
    # "delivered" says whether the Pico was listening (if not, it's offline; retained ones wait).
    try:
        delivered = await emqx.publish(env, topic(env, name), payload, retain=retain, qos=1 if retain else 0)
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return {"ok": True, "delivered": delivered}


def alarms_message(alarms):
    return {"v": PAYLOAD_VERSION, "gen": int(time.time()), "alarms": alarms}


async def sync_calendar(env):
    """Reads the calendar and publishes its alarms (retained). Run nightly and by /api/sync.
    On any error nothing is published, so the Pico keeps the last good list."""
    alarms = await calendar_job.alarms(env, datetime.now(timezone.utc))
    await emqx.publish(env, topic(env, "alarms/calendar"), alarms_message(alarms), retain=True, qos=1)
    return alarms


@app.get("/api/health")
async def health(request: Request):
    env = request.scope["env"]
    # Names only, never values, so a missing secret is easy to spot.
    missing = [key for key in CONFIG_KEYS if not getattr(env, key, None)]
    return {"ok": True, "missing_config": missing}


# Whether the Pico is connected to the broker right now. EMQX notices a Pico that lost power
# or Wi-Fi only after its keepalive runs out (about 30 s, see pico/net.py).
@app.get("/api/status")
async def status(request: Request):
    env = request.scope["env"]
    try:
        online = await emqx.connected(env, PICO_CLIENT_PREFIX + device_id(env))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return {"ok": True, "online": online}


@app.post("/api/test")
async def test(body: Test, request: Request):
    return await send(request.scope["env"], "cmd", {"cmd": "test", "pattern": body.pattern, "seconds": body.seconds})


@app.post("/api/stop")
async def stop(request: Request):
    return await send(request.scope["env"], "cmd", {"cmd": "stop"})


# One manual alarm at a time: setting one replaces the last. Retained, so the Pico gets it
# whenever it next connects.
@app.put("/api/alarm")
async def set_alarm(body: Alarm, request: Request):
    if body.time <= time.time():
        raise HTTPException(400, "Pick a time in the future")
    return await send(request.scope["env"], "alarms/manual", alarms_message([[body.time, body.pattern]]), retain=True)


# An empty list, not an empty message: an empty retained message would delete it from the
# broker, and a Pico that was offline would never hear the alarm was cleared.
@app.delete("/api/alarm")
async def clear_alarm(request: Request):
    return await send(request.scope["env"], "alarms/manual", alarms_message([]), retain=True)


# The alarm type every alarm plays, calendar and custom (the Pico checks the name). Retained,
# so the Pico gets it whenever it next connects and keeps it in flash.
@app.put("/api/type")
async def set_type(body: AlarmType, request: Request):
    return await send(request.scope["env"], "settings", {"v": PAYLOAD_VERSION, "pattern": body.pattern}, retain=True)


@app.post("/api/sync")
async def sync(request: Request):
    try:
        alarms = await sync_calendar(request.scope["env"])
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return {"ok": True, "alarms": alarms}


def password_ok(env, request):
    """True if the request's "Authorization: Bearer <password>" matches APP_PASSWORD.
    No APP_PASSWORD set means nobody gets in, rather than everybody."""
    expected = getattr(env, "APP_PASSWORD", None)
    given = (request.headers.get("Authorization") or "").removeprefix("Bearer ")
    # compare_digest takes the same time however much matches, so timing gives no hints.
    return bool(expected) and hmac.compare_digest(given.encode(), expected.encode())


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        if not password_ok(self.env, request):
            return Response(json.dumps({"detail": "Wrong password"}), status=401,
                            headers={"Content-Type": "application/json"})
        return await asgi.fetch(app, request, self.env, self.ctx)

    # The nightly Cron Trigger (see wrangler.jsonc). An error here shows in Workers Logs.
    # Uses self.env like fetch does: in testing, the env argument didn't hold the secrets.
    async def scheduled(self, controller, env, ctx):
        alarms = await sync_calendar(self.env)
        print("Calendar sync:", len(alarms), "alarms")
