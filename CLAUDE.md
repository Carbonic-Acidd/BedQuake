# BedQuake

Silent bed-shaker alarm. Pico WH (MicroPython) -> TPA3116 amp -> bass shaker.
GitHub Pages site -> public MQTT broker (broker.hivemq.com) -> Pico.
Team final project for Northeastern's Cornerstone of Engineering.

## Style
- Least code that fully works. Flat, readable, no classes or frameworks.
- Tunable values as named constants at the top of each file.
- Ask before adding any file, dependency, or feature.
- Build one step at a time; stop after each so the human can test on hardware.
- Never guess wiring. Ask.

## Layout
- pico/  code for the Pico. secrets.py is gitignored (template: secrets.example.py).

## Commands (mpremote; no Thonny)
- Run without saving: mpremote run --no-follow pico/main.py + repl
  (Ctrl-C stops it on the Pico, Ctrl-] exits. Plain `mpremote run` only quits
  mpremote on Ctrl-C and leaves the program, and PWM, running on the Pico.)
- Save and reboot: mpremote cp pico/main.py pico/secrets.py : + reset

## Hardware facts (don't change without asking)
- Power: 24 V adapter -> amp VCC, and buck converter (5 V) -> Pico.
- GP15: PWM to amp IN+; Pico GND to amp IN-.
- Shaker: Dayton BST-2, 4 ohm, 10-80 Hz. Strength peaks at 50% duty
  (strength ~ sin(pi * duty)).
- The amp/supply protection trips at high output.

## Safety
- Any code that drives PWM turns it off in a `finally` block.

## Secrets (the repo is public)
- Never commit secrets. The MQTT topic is secret: Pico reads it from secrets.py,
  the site reads it from the URL hash.
