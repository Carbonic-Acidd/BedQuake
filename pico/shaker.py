# Drives the bass shaker through the amp. Knows nothing about Wi-Fi or MQTT.
# Use: start("pulse"), then call update() every ~10 ms. stop() silences it.
from machine import Pin, PWM
import math
import time

PIN = 15              # GP15 -> amp IN+ (Pico GND -> amp IN-)
MAX_STRENGTH = 1.0    # 1.0 = 50% duty, the strongest. Lower it if the amp's protection trips.

# name -> PWM frequency (Hz) and steps (start_strength, end_strength, ms), looped.
# Strength is 0..1. A step whose start and end differ eases smoothly between them.
PATTERNS = {
    "pulse":     {"freq": 45, "steps": [(1, 1, 300), (0, 0, 300), (1, 1, 300), (0, 0, 300), (1, 1, 1500), (0, 0, 1000)]},
    "breathe":   {"freq": 60, "steps": [(0, 1, 2000), (1, 0, 2000)]},
    "steady":    {"freq": 45, "steps": [(1, 1, 1000)]},
    "heartbeat": {"freq": 45, "steps": [(1, 1, 150), (0, 0, 100), (1, 1, 150), (0, 0, 800)]},
}

_pwm = PWM(Pin(PIN))
_pwm.duty_u16(0)
_steps = None   # steps of the playing pattern; None when silent
_length = 0     # total ms of one loop of the pattern
_start = 0      # ticks_ms when the pattern started


def start(name):
    global _steps, _length, _start
    pattern = PATTERNS[name]
    _pwm.freq(pattern["freq"])
    _steps = pattern["steps"]
    _length = sum(step[2] for step in _steps)
    _start = time.ticks_ms()
    update()


def stop():
    global _steps
    _steps = None
    _pwm.duty_u16(0)


def update():
    if _steps is None:
        return
    t = time.ticks_diff(time.ticks_ms(), _start) % _length
    for begin, end, ms in _steps:
        if t < ms:
            break
        t -= ms
    eased = (1 - math.cos(math.pi * t / ms)) / 2   # goes 0 -> 1 smoothly over the step
    _pwm.duty_u16(_duty(begin + (end - begin) * eased))


def _duty(strength):
    # Felt strength follows sin(pi * duty), peaking at 50% duty, so invert that.
    strength = max(0.0, min(MAX_STRENGTH, strength))
    return int(math.asin(strength) / math.pi * 65535)
