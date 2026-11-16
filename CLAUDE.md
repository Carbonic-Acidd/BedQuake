# BedQuake

Silent bed-shaker alarm. Pico WH (MicroPython) -> TPA3116 amp -> bass shaker.
PWA website (Vite, plain JS, hosted on Vercel) <-> EMQX Serverless MQTT broker (TLS only) <-> Pico.
Team final project for Northeastern's Cornerstone of Engineering.
Roadmap and MQTT topics contract: PLAN.md. See README.md for every file's job.

## Style
- Least code that fully works. Flat, readable, one job per file, no classes or frameworks.
- Tunable values as named constants at the top of each file.
- Ask before adding any file, dependency, or feature.
- Build one PLAN.md step at a time; stop after each so the human tests on hardware.
- Never guess wiring. Ask.

## Commands
- make setup / make pico-setup / make run / make stop / make logs / make dev
- make run uses `mpremote ... run --no-follow pico/main.py + repl`: plain
  `mpremote run` doesn't pass Ctrl-C to the Pico, which leaves the shaker running.

## Config and secrets (the repo is public)
- One root .env (gitignored; template .env.example) holds everything.
- Pico: scripts/gen_pico_env.py writes pico/env.py (gitignored) from .env.
- Website: Vite reads the root .env (envDir '..'); only VITE_ vars reach the browser.
  The website's broker password is typed into the page (localStorage), never a VITE_ var.

## Hardware facts (don't change without asking)
- Power: 24 V adapter -> amp VCC, and buck converter (5 V) -> Pico.
- GP15: PWM to amp IN+; Pico GND to amp IN-. No amp enable pin.
- Shaker: Dayton BST-2, 4 ohm, 10-80 Hz. Strength peaks at 50% duty
  (strength ~ sin(pi * duty)); shaker.py inverts this with asin.
- The amp/supply protection trips at high output; shaker.MAX_STRENGTH caps it.

## Safety
- Any code that drives PWM turns it off in a `finally` block.
