# The alarm lists, kept in flash so a reboot or power cut doesn't lose them.
# Knows nothing about Wi-Fi, MQTT or the shaker.
#
# Two lists, each from its own retained MQTT topic and saved to its own file:
# "calendar" (from the Worker's nightly sync) and "manual" (set on the website).
# Each alarm is [UTC Unix seconds, pattern name]. due(now) merges both lists.
import json
import os

PAYLOAD_VERSION = 1     # the "v" field the Worker sends
MAX_ALARMS = 20         # per list; a longer list is rejected (the Worker sends at most 7)
LATE_OK_S = 300         # still fire an alarm this late (e.g. power came back just after it)
FILES = {"calendar": "calendar.json", "manual": "manual.json"}
FIRED_FILE = "fired.json"   # time of the last alarm that fired, so a reboot can't refire it

_lists = {"calendar": [], "manual": []}
_last_fired = 0


def load():
    global _last_fired
    for name, path in FILES.items():
        _lists[name] = _read(path, [])
    _last_fired = _read(FIRED_FILE, 0)
    print("Alarms: loaded", _lists, "last fired", _last_fired)


def update(name, payload, patterns):
    """Checks a message's payload and saves its alarms. Raises ValueError if it's bad,
    keeping the old list. Returns True if the list changed."""
    try:
        data = json.loads(payload)
        if data["v"] != PAYLOAD_VERSION or len(data["alarms"]) > MAX_ALARMS:
            raise ValueError
        alarms = sorted([int(t), str(pattern)] for t, pattern in data["alarms"])
    except Exception:
        raise ValueError("bad alarm message")
    for t, pattern in alarms:
        if pattern not in patterns:
            raise ValueError("unknown pattern " + pattern)
    if alarms == _lists[name]:
        return False   # retained messages arrive on every reconnect; don't rewrite flash
    _lists[name] = alarms
    _write(FILES[name], alarms)
    return True


def due(now):
    """Returns [time, pattern] of the alarm to fire at UTC time now, or None.
    Alarms more than LATE_OK_S in the past, or not after the last fired one, are skipped."""
    found = None
    for alarm in _lists["calendar"] + _lists["manual"]:
        if _last_fired < alarm[0] <= now and now - alarm[0] <= LATE_OK_S:
            if found is None or alarm[0] > found[0]:
                found = alarm   # the latest; marking it fired also covers any earlier one
    return found


def mark_fired(t):
    global _last_fired
    _last_fired = t
    _write(FIRED_FILE, t)


def _read(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:   # missing (first boot) or unreadable: start empty
        return default


def _write(path, value):
    # Write a temp file, then rename it over the real one. On the Pico's filesystem (littlefs)
    # rename is atomic, so a power cut leaves either the old file or the new one, never half.
    with open(path + ".tmp", "w") as f:
        json.dump(value, f)
    os.rename(path + ".tmp", path)
