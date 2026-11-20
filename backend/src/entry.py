# The Cloudflare Worker. Static files in web/dist are served before this runs;
# only /api/* requests reach this code. Endpoints publish to the Pico through EMQX, and the
# website's settings are kept in Workers KV (the SETTINGS binding in wrangler.jsonc).
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

# The backend's settings, Worker secrets (uploaded from .env by `make secrets`). ICS_URL and
# ALARM_OFFSET_MIN are only fallbacks now: the website's Settings panel saves its own.
CONFIG_KEYS = ["EMQX_API_URL", "EMQX_API_KEY", "EMQX_API_SECRET", "DEVICE_ID", "APP_PASSWORD"]
DEFAULT_DEVICE_ID = "bed1"
PICO_CLIENT_PREFIX = "shakeawake-"   # the Pico's MQTT client id is this + DEVICE_ID (pico/net.py)
MAX_TEST_S = 90           # the Pico won't play a test longer than this either
PAYLOAD_VERSION = 1       # the "v" field in alarm messages, bumped if their shape changes
SETTINGS_KEY = "settings" # the one KV entry: {"ics_url", "offset_min", "sync_hour", "max_run_s", "try_s", "pattern"}
DEFAULT_OFFSET_MIN = 60   # wake this long before the first event, unless set
DEFAULT_SYNC_HOUR = 3     # the daily calendar check runs at 3 am (calendar_job.ZONE), unless set
DEFAULT_MAX_RUN_S = 90    # an alarm stops itself after this long, unless set
DEFAULT_TRY_S = 10        # Try plays this long, unless set (the website uses it; the Pico caps it)
MAX_RUN_RANGE = (10, 600) # the Pico enforces the same limits
LINK_STARTS = ("https://", "http://", "webcal://")

app = FastAPI()


class Test(BaseModel):
    pattern: str = Field(min_length=1, max_length=20)
    seconds: int = Field(default=10, ge=1, le=MAX_TEST_S)


class Alarm(BaseModel):
    time: int             # UTC Unix seconds
    pattern: str = Field(min_length=1, max_length=20)


class AlarmType(BaseModel):
    pattern: str = Field(min_length=1, max_length=20)


class Settings(BaseModel):
    ics_url: str = Field(default="", max_length=2000)   # "" = use ICS_URL from .env, if any
    offset_min: int = Field(default=DEFAULT_OFFSET_MIN, ge=0, le=720)
    sync_hour: int = Field(default=DEFAULT_SYNC_HOUR, ge=0, le=23)
    max_run_s: int = Field(default=DEFAULT_MAX_RUN_S, ge=MAX_RUN_RANGE[0], le=MAX_RUN_RANGE[1])
    try_s: int = Field(default=DEFAULT_TRY_S, ge=1, le=MAX_TEST_S)
    pattern: str | None = Field(default=None, max_length=20)   # the device's alarm type, if not saved yet


async def load_settings(env):
    """The saved settings (a dict, maybe empty). No KV binding just means none saved."""
    kv = getattr(env, "SETTINGS", None)
    raw = await kv.get(SETTINGS_KEY) if kv else None
    try:
        return json.loads(raw) if raw else {}
    except ValueError:
        return {}


async def save_settings(env, settings):
    kv = getattr(env, "SETTINGS", None)
    if not kv:
        raise HTTPException(500, "Settings storage isn't set up (SETTINGS in wrangler.jsonc)")
    await kv.put(SETTINGS_KEY, json.dumps(settings))


async def send_pico_settings(env, settings):
    # The Pico's own settings, retained so it gets them whenever it connects: the alarm type
    # every alarm plays (null = each alarm's own) and how long an alarm plays before stopping.
    return await send(env, "settings", {"v": PAYLOAD_VERSION, "pattern": settings.get("pattern"),
                                        "max_run_s": settings.get("max_run_s", DEFAULT_MAX_RUN_S)}, retain=True)


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
    Uses the saved link and lead time, else ICS_URL and ALARM_OFFSET_MIN from .env.
    On any error nothing is published, so the Pico keeps the last good list."""
    settings = await load_settings(env)
    url = settings.get("ics_url") or getattr(env, "ICS_URL", None)
    offset = settings.get("offset_min", getattr(env, "ALARM_OFFSET_MIN", None) or DEFAULT_OFFSET_MIN)
    alarms = await calendar_job.alarms(url, int(offset), datetime.now(timezone.utc))
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


# The alarm type every alarm plays, calendar and custom (the Pico checks the name). Saved, and
# sent to the Pico with its other settings.
@app.put("/api/type")
async def set_type(body: AlarmType, request: Request):
    env = request.scope["env"]
    settings = await load_settings(env)
    settings["pattern"] = body.pattern
    await save_settings(env, settings)
    return await send_pico_settings(env, settings)


# The Settings panel. Read on unlock (so every device shows the same), saved from Save.
@app.get("/api/settings")
async def get_settings(request: Request):
    env = request.scope["env"]
    settings = await load_settings(env)
    return {"ok": True, "ics_url": settings.get("ics_url", ""),
            "offset_min": settings.get("offset_min", int(getattr(env, "ALARM_OFFSET_MIN", None) or DEFAULT_OFFSET_MIN)),
            "sync_hour": settings.get("sync_hour", DEFAULT_SYNC_HOUR),
            "max_run_s": settings.get("max_run_s", DEFAULT_MAX_RUN_S), "try_s": settings.get("try_s", DEFAULT_TRY_S),
            "pattern": settings.get("pattern")}


@app.put("/api/settings")
async def put_settings(body: Settings, request: Request):
    link = body.ics_url.strip()
    if link and not link.lower().startswith(LINK_STARTS):
        raise HTTPException(400, "The calendar link should start with https:// or webcal://")
    env = request.scope["env"]
    settings = await load_settings(env)
    settings.update(ics_url=link, offset_min=body.offset_min, sync_hour=body.sync_hour, max_run_s=body.max_run_s,
                    try_s=body.try_s)
    if body.pattern and not settings.get("pattern"):   # so saving never clears the Pico's alarm type
        settings["pattern"] = body.pattern
    await save_settings(env, settings)
    return await send_pico_settings(env, settings)


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

    # The hourly Cron Trigger (see wrangler.jsonc): syncs the calendar once a day, in the hour
    # chosen in Settings (local time). An error here shows in Workers Logs.
    # Uses self.env like fetch does: in testing, the env argument didn't hold the secrets.
    async def scheduled(self, controller, env, ctx):
        settings = await load_settings(self.env)
        if datetime.now(calendar_job.ZONE).hour != settings.get("sync_hour", DEFAULT_SYNC_HOUR):
            return
        alarms = await sync_calendar(self.env)
        print("Calendar sync:", len(alarms), "alarms")
