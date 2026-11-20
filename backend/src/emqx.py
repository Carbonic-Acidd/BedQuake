# Talks to EMQX Cloud's REST API ({EMQX_API_URL}/...) with the deployment's API key:
# publishes MQTT messages, and asks whether a client (the Pico) is connected.
# No MQTT library: one HTTPS request each.
import base64
import json
from urllib.parse import quote

from workers import fetch

OK_STATUSES = (200, 202)   # 202 = "no matching subscribers", e.g. the Pico is offline. Still published.


async def _request(env, method, path, body=None):
    for key in ("EMQX_API_URL", "EMQX_API_KEY", "EMQX_API_SECRET"):
        if not getattr(env, key, None):
            raise RuntimeError(key + " is not set")
    login = base64.b64encode(f"{env.EMQX_API_KEY}:{env.EMQX_API_SECRET}".encode()).decode()
    headers = {"Authorization": "Basic " + login}
    if body is not None:
        headers["Content-Type"] = "application/json"
    try:
        return await fetch(env.EMQX_API_URL.rstrip("/") + path, method=method, headers=headers,
                           body=json.dumps(body) if body is not None else None)
    except Exception as e:   # network failure: no response at all
        raise RuntimeError(f"Couldn't reach EMQX: {e}")


async def publish(env, topic, payload, retain=False, qos=0):
    """Publishes payload (a dict, sent as JSON) to topic. Returns True if a subscriber (the Pico)
    got it, False if nobody is subscribed right now. Raises RuntimeError if EMQX refuses."""
    response = await _request(env, "POST", "/publish", {
        "topic": topic, "payload": json.dumps(payload, separators=(",", ":")), "qos": qos, "retain": retain})
    if response.status not in OK_STATUSES:
        raise RuntimeError(f"EMQX said {response.status}: {await response.text()}")
    return response.status == 200


async def connected(env, client_id):
    """True if the MQTT client with this id is connected right now (EMQX's Clients API).
    Raises RuntimeError if EMQX can't be asked."""
    response = await _request(env, "GET", "/clients/" + quote(client_id, safe=""))
    if response.status == 404:   # EMQX has never seen it, or has forgotten it: not connected
        return False
    if response.status != 200:
        raise RuntimeError(f"EMQX said {response.status}: {await response.text()}")
    data = json.loads(await response.text())
    if isinstance(data.get("data"), list):   # the docs show both a bare object and {"data": [...]}
        data = data["data"][0] if data["data"] else {}
    return bool(data.get("connected"))
