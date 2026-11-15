# BedQuake hardware and behaviour constants.

# GPIO pin driving the shaker motor (PWM output).
SHAKER_PIN = 15

# GPIO pin for the IR sensor input.
IR_PIN = 16

# ADC pin for the strength potentiometer.
POT_PIN = 27

# Lowest shaker vibration frequency, in Hz.
FREQ_MIN_HZ = 20

# Highest shaker vibration frequency, in Hz.
FREQ_MAX_HZ = 80

# Maximum shaker strength as a fraction of full power (0.0 to 1.0).
# Placeholder until calibrated.
MAX_STRENGTH = 0.5

# Safety cap: longest an alarm may run before stopping itself, in seconds.
MAX_ALARM_SECONDS = 600
