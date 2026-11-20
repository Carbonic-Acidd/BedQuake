# Drives the bass shaker through the amp. Knows nothing about Wi-Fi or MQTT.
# Use: start("classic"), then call update() every ~10 ms. stop() silences it.
# start(name, test=True) plays a type's "test_steps" if it has them (Rise climbs faster in a test).
from machine import Pin, PWM
import math
import time

PIN = 15              # GP15 -> amp IN+ (Pico GND -> amp IN-)
MAX_STRENGTH = 1.0    # 1.0 = 50% duty, the strongest. Lower it if the amp's protection trips.

# Alarm types: name -> PWM frequency (Hz) and steps (start_strength, end_strength, ms), looped.
# Strength is 0..1. A step whose start and end differ eases smoothly between them.
# Keep web/src/main.js's TYPES in sync (names and steps).
PATTERNS = {
    "classic": {"freq": 45, "steps": [(1, 1, 300), (0, 0, 300), (1, 1, 300), (0, 0, 300), (1, 1, 1500), (0, 0, 1000)]},
    "waves":   {"freq": 60, "steps": [(0, 1, 2000), (1, 0, 2000)]},
    # Rise: silent to full over 20 s, then holds (to 10 min, the longest an alarm can run).
    "rise":    {"freq": 45, "steps": [(0, 1, 20000), (1, 1, 580000)],
                "test_steps": [(0, 1, 10000), (1, 1, 590000)]},              # a test climbs over 10 s
    "knock":   {"freq": 45, "steps": [(1, 1, 120), (0, 0, 120), (1, 1, 120), (0, 0, 120), (1, 1, 120), (0, 0, 900)]},
}
DEFAULT = "classic"   # played if an alarm names a type this code doesn't know

_pwm = PWM(Pin(PIN))
_pwm.duty_u16(0)
_steps = None   # steps of the playing pattern; None when silent
_length = 0     # total ms of one loop of the pattern
_start = 0      # ticks_ms when the pattern started


def start(name, test=False):
    global _steps, _length, _start
    pattern = PATTERNS[name]
    _pwm.freq(pattern["freq"])
    _steps = pattern.get("test_steps", pattern["steps"]) if test else pattern["steps"]
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
