# Publishes MQTT messages through EMQX Cloud's REST API (POST {EMQX_API_URL}/publish).
# No MQTT library: one HTTPS request per message, with the deployment's API key.
import base64
import json

from workers import fetch

OK_STATUSES = (200, 202)   # 202 = "no matching subscribers", e.g. the Pico is offline. Still published.


async def publish(env, topic, payload, retain=False, qos=0):
    """Publishes payload (a dict, sent as JSON) to topic. Raises RuntimeError if EMQX refuses."""
    for key in ("EMQX_API_URL", "EMQX_API_KEY", "EMQX_API_SECRET"):
        if not getattr(env, key, None):
            raise RuntimeError(key + " is not set")
    login = base64.b64encode(f"{env.EMQX_API_KEY}:{env.EMQX_API_SECRET}".encode()).decode()
    try:
        response = await fetch(
            env.EMQX_API_URL.rstrip("/") + "/publish",
            method="POST",
            headers={"Authorization": "Basic " + login, "Content-Type": "application/json"},
            body=json.dumps({"topic": topic, "payload": json.dumps(payload, separators=(",", ":")),
                             "qos": qos, "retain": retain}),
        )
    except Exception as e:   # network failure: no response at all
        raise RuntimeError(f"Couldn't reach EMQX: {e}")
    if response.status not in OK_STATUSES:
        raise RuntimeError(f"EMQX said {response.status}: {await response.text()}")
