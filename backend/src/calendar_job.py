# Turns the calendar (ICS_URL) into alarms: for each of the next DAYS days, the first timed
# event's start minus ALARM_OFFSET_MIN. All-day events are ignored; empty days get no alarm.
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import icalendar
import recurring_ical_events
from workers import fetch

ZONE = ZoneInfo("America/New_York")   # whose "days" count, and the zone for floating times
DAYS = 7
DEFAULT_OFFSET_MIN = 60
PATTERN = "pulse"                     # what calendar alarms play


async def alarms(env, now):
    """Returns [[UTC Unix seconds, pattern], ...] in time order, only alarms after now."""
    url = getattr(env, "ICS_URL", None)
    if not url:
        raise RuntimeError("ICS_URL is not set")
    url = url.replace("webcal://", "https://", 1)   # calendar apps often hand out webcal:// links
    try:
        response = await fetch(url)
        text = await response.text()
    except Exception as e:
        raise RuntimeError(f"Couldn't fetch the calendar: {e}")
    if response.status != 200:
        raise RuntimeError(f"Calendar fetch said {response.status}")
    offset = timedelta(minutes=int(getattr(env, "ALARM_OFFSET_MIN", None) or DEFAULT_OFFSET_MIN))
    try:
        return compute(text, now, offset)
    except Exception as e:
        raise RuntimeError(f"Couldn't read the calendar: {e!r}")


def compute(ics_text, now, offset):
    today = now.astimezone(ZONE).date()
    days = [today + timedelta(days=n) for n in range(DAYS)]
    window_start = datetime.combine(days[0], time(0), ZONE)
    window_end = datetime.combine(days[-1] + timedelta(days=1), time(0), ZONE)

    first = {}   # local date -> earliest timed event start that day
    calendar = icalendar.Calendar.from_ical(ics_text)
    for event in recurring_ical_events.of(calendar).between(window_start, window_end):
        start = event["DTSTART"].dt
        if not isinstance(start, datetime) or event.get("STATUS") == "CANCELLED":
            continue   # all-day events are dates, not datetimes
        if start.tzinfo is None:
            start = start.replace(tzinfo=ZONE)   # "floating" time: means local time
        start = start.astimezone(ZONE)
        day = start.date()
        if day in days and (day not in first or start < first[day]):
            first[day] = start

    result = []
    for day in sorted(first):
        alarm = int((first[day] - offset).timestamp())
        if alarm > now.timestamp():
            result.append([alarm, PATTERN])
    return result
