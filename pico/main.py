# BedQuake entry point, runs on boot. Wires the shaker (and later the network) together.
import time
import shaker

PATTERN = "heartbeat"   # any name in shaker.PATTERNS
LOOP_MS = 10        # how often the shaker is updated

print("Patterns:", ", ".join(shaker.PATTERNS))
print("Shaker:", PATTERN, "- Ctrl-C to stop.")
shaker.start(PATTERN)
try:
    while True:
        shaker.update()
        time.sleep_ms(LOOP_MS)
finally:
    # PWM keeps running after a script stops, so always switch it off.
    shaker.stop()
    print("Shaker off")
