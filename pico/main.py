# BedQuake entry point, runs on boot. Wires the shaker and the network together.
import json
import machine
import time

import net
import shaker

LOOP_MS = 10            # how often the shaker and the network are serviced
RETRY_S = 5             # wait before restarting after an error
DEFAULT_TEST_S = 10     # test length when the message doesn't say
MAX_RUN_S = 600         # safety: nothing plays longer than this

status = {"online": True, "playing": None, "patterns": list(shaker.PATTERNS), "alarm": None}
stop_at = None          # ticks_ms when the playing pattern stops; None when silent


def play(name, seconds):
    global stop_at
    shaker.start(name)
    stop_at = time.ticks_add(time.ticks_ms(), int(seconds * 1000))
    status["playing"] = name
    print("Playing", name, "for", seconds, "s")
    net.publish_status(status)


def silence():
    global stop_at
    shaker.stop()
    stop_at = None
    if status["playing"]:
        status["playing"] = None
        print("Stopped")
        net.publish_status(status)


def on_message(topic, payload):
    if topic == net.STOP_TOPIC:
        silence()   # stop never depends on the payload
    elif topic == net.TEST_TOPIC:
        try:
            data = json.loads(payload)
            name = data["pattern"]
            seconds = max(0, min(float(data.get("seconds", DEFAULT_TEST_S)), MAX_RUN_S))
            shaker.PATTERNS[name]   # raises KeyError if the name is unknown
        except Exception as e:
            print("Ignored bad test message:", payload, repr(e))
            return
        play(name, seconds)


try:
    net.connect(status, on_message)
    print("Ready. Ctrl-C to stop.")
    while True:
        shaker.update()
        net.check()
        if stop_at is not None and time.ticks_diff(time.ticks_ms(), stop_at) >= 0:
            silence()
        time.sleep_ms(LOOP_MS)
except Exception as e:   # Ctrl-C isn't an Exception, so it skips this and just stops
    shaker.stop()
    print("Error:", repr(e), "- restarting in", RETRY_S, "s")
    time.sleep(RETRY_S)
    machine.reset()
finally:
    # PWM keeps running after a script stops, so always switch it off.
    shaker.stop()
    print("Shaker off")
