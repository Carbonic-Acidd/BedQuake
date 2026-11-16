# BedQuake step 1: loop the buzz pattern on the shaker (no network yet).
from machine import Pin, PWM
import time

SHAKER_PIN = 15
FREQ_HZ = 45            # low tone suited to a bass shaker
DUTY_ON = 32768         # 50% of 65535: the strongest a square wave gets
PATTERN = [(300, 300), (300, 300), (1500, 1000)]  # (buzz_ms, pause_ms), repeats

pwm = PWM(Pin(SHAKER_PIN))
pwm.freq(FREQ_HZ)
pwm.duty_u16(0)

print("Buzzing. Press Ctrl-C to stop.")
try:
    while True:
        for buzz_ms, pause_ms in PATTERN:
            pwm.duty_u16(DUTY_ON)
            time.sleep_ms(buzz_ms)
            pwm.duty_u16(0)
            time.sleep_ms(pause_ms)
finally:
    # PWM keeps running after a script stops, so always switch it off.
    pwm.duty_u16(0)
    pwm.deinit()
    Pin(SHAKER_PIN, Pin.OUT, value=0)
    print("Shaker off")
