# Sine "breathing" pattern: rumble strength rises and falls smoothly.
# Frequency stays fixed at 60 Hz; only the duty cycle changes.
from machine import Pin, PWM
import math
import time

SHAKER_PIN = 15
FREQ_HZ = 60
BREATH_SECONDS = 4.0    # one full cycle: off -> strongest -> off
MAX_STRENGTH = 1.0      # 0.0 to 1.0; 1.0 = 50% duty, the strongest a square wave gets
UPDATE_MS = 20          # update the duty 50 times per second (smooth enough to feel continuous)
PRINT_MS = 250          # print the strength bar 4 times per second
MAX_DUTY = 65535        # duty_u16 is 16-bit: 0 = always off, 65535 = always on


def strength_to_duty(strength):
    """Return the duty value that gives this strength (0.0 to 1.0).

    Your sweep showed strength is NOT proportional to duty: it follows
    sin(pi * duty), peaking at 50%. This inverts that relationship:
    duty = asin(strength) / pi, which always lands between 0% and 50%.
    """
    strength = max(0.0, min(1.0, strength))     # clamp, never trust inputs
    return int(math.asin(strength) / math.pi * MAX_DUTY)


pwm = PWM(Pin(SHAKER_PIN))
pwm.freq(FREQ_HZ)
pwm.duty_u16(0)

start = time.ticks_ms()
last_print = start

try:
    while True:
        now = time.ticks_ms()
        t = time.ticks_diff(now, start) / 1000      # seconds since start

        # A sine wave shifted up so it goes 0 -> 1 -> 0 instead of -1 -> 1
        target = (1 - math.cos(2 * math.pi * t / BREATH_SECONDS)) / 2
        strength = target * MAX_STRENGTH
        duty = strength_to_duty(strength)
        pwm.duty_u16(duty)

        if time.ticks_diff(now, last_print) >= PRINT_MS:
            last_print = now
            percent = duty / MAX_DUTY * 100
            print("{:5.1f}% duty |{}".format(percent, "#" * int(strength * 30)))

        time.sleep_ms(UPDATE_MS)
finally:
    # Always leave the shaker off, even if you press Stop.
    pwm.duty_u16(0)
    pwm.deinit()
    Pin(SHAKER_PIN, Pin.OUT, value=0)
    print("Shaker off")