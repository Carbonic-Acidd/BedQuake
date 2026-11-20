# Shake Awake entry point, runs on boot. Wires the shaker, the alarms and the network together.
# Works offline: saved alarms load from flash, and fire on time once the clock has been set.
import json
import time

import alarms
import net
import shaker

LOOP_MS = 10            # how often the shaker, the network and the alarms are serviced
ERROR_PAUSE_S = 5       # after an unexpected error, wait this long and carry on (never restart)
DEFAULT_TEST_S = 10     # test length when the message doesn't say
MAX_RUN_S = 90          # alarms play this long unless stopped; tests can't be longer

stop_at = None          # ticks_ms when the playing pattern stops; None when silent


def play(name, seconds):
    global stop_at
    shaker.start(name)
    stop_at = time.ticks_add(time.ticks_ms(), int(seconds * 1000))
    print("Playing", name, "for", seconds, "s")


def silence():
    global stop_at
    shaker.stop()
    if stop_at is not None:
        print("Stopped")
    stop_at = None


def on_message(topic, payload):
    if topic == net.CMD_TOPIC:
        try:
            data = json.loads(payload)
            if data["cmd"] == "stop":
                silence()
                return
            if data["cmd"] != "test":
                raise ValueError("unknown command")
            name = data["pattern"]
            seconds = max(0, min(float(data.get("seconds", DEFAULT_TEST_S)), MAX_RUN_S))
            shaker.PATTERNS[name]   # raises KeyError if the name is unknown
        except Exception as e:
            print("Ignored bad command:", payload, repr(e))
            return
        play(name, seconds)
    elif topic in net.ALARM_TOPICS:
        name = net.ALARM_TOPICS[topic]
        try:
            if alarms.update(name, payload, shaker.PATTERNS):
                print("Alarms: new", name, "list", payload)
        except ValueError as e:
            print("Ignored bad", name, "alarms:", payload, repr(e))


def step():
    shaker.update()
    net.service(busy=stop_at is not None)   # busy: skip anything that could freeze the pattern
    if stop_at is not None and time.ticks_diff(time.ticks_ms(), stop_at) >= 0:
        silence()
    # No clock battery: until NTP has worked once since boot, the time is meaningless.
    if net.clock_ok():
        alarm = alarms.due(net.unix_time())
        if alarm:
            alarms.mark_fired(alarm[0])   # saved first, so a reboot mid-alarm doesn't refire it
            print("Alarm!", alarm)
            play(alarm[1], MAX_RUN_S)     # until Stop, or the safety limit


try:
    alarms.load()
    net.start(on_message)
    print("Ready. Ctrl-C to stop.")
    while True:
        try:
            step()
        except Exception as e:   # a bug, not the network (net.py handles that). Ctrl-C isn't an Exception.
            silence()
            print("Error:", repr(e), "- carrying on in", ERROR_PAUSE_S, "s")
            time.sleep(ERROR_PAUSE_S)
        time.sleep_ms(LOOP_MS)
finally:
    # PWM keeps running after a script stops, so always switch it off.
    shaker.stop()
    print("Shaker off")
