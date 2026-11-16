# BedQuake entry point, runs on boot. Wires the shaker and the network together.
import machine
import time

import net
import shaker

LOOP_MS = 10    # how often the shaker and the network are serviced
RETRY_S = 5     # wait before restarting after an error

status = {"online": True, "playing": None, "patterns": list(shaker.PATTERNS), "alarm": None}

try:
    net.connect(status)
    print("Ready. Ctrl-C to stop.")
    while True:
        shaker.update()
        net.check()
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
