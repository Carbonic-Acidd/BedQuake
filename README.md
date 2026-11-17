# Shake Awake

A silent bed-shaker alarm. A Raspberry Pi Pico WH drives a bass shaker through an
amp, and (soon) a phone web app controls it over MQTT through an EMQX Serverless broker.

## Prerequisites
Python 3, Node LTS, and Make. On Windows: `winget install GnuWin32.Make`, or use Git Bash.

## First-time setup
```
cp .env.example .env     # then fill it in (blanks are fine for Step 1)
make setup               # Python tools + web packages
make pico-setup          # once per Pico, with the Pico plugged in
```

## Daily commands
- `make run`: copy the code to the Pico and run it. Ctrl-C stops it, then Ctrl-] exits.
- `make stop`: stop whatever is running on the Pico.
- `make logs`: open the Pico's REPL.
- `make dev`: run the website at http://localhost:5173.
- `make help`: list all commands.

## Files
- `Makefile`: every command above.
- `.env.example`: the config keys; copy it to `.env` (never committed) for real values.
- `requirements.txt`: laptop Python tools (mpremote, python-dotenv).
- `PLAN.md`: the roadmap and the MQTT topics contract.
- `scripts/gen_pico_env.py`: turns `.env` into `pico/env.py`, because the Pico can't read `.env`.
- `pico/main.py`: runs on boot and wires the shaker and network together.
- `pico/shaker.py`: drives the shaker; vibration patterns are defined at the top.
- `pico/net.py`: Wi-Fi, clock (NTP) and MQTT.
- `pico/env.py`: generated from `.env`, never edited or committed.
- `web/package.json`: web dependencies (Vite, mqtt).
- `web/vite.config.js`: makes Vite read the root `.env`.
- `web/index.html`: the page.
- `web/src/main.js`: the page's code.
- `web/src/mqtt.js`: talks to the broker.
- `web/public/manifest.webmanifest`: lets the phone install the site as an app.
- `web/public/sw.js`: service worker; opens the last loaded page when offline.
- `web/public/*.png`: the logo (page header) and app icons (home screen and install).
