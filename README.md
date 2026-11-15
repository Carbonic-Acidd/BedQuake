# BedQuake

BedQuake is a bed-shaker alarm clock. A Raspberry Pi Pico runs MicroPython
firmware that drives a vibration shaker under the mattress, reads local inputs
(an IR sensor and a strength potentiometer), and talks to the outside world over
MQTT so alarms and vibration patterns can be set from a web app and, later,
from calendar events.

## Folders

- `.github/workflows/` - CI workflows (none yet).
- `docs/` - build plan, test log, and architecture decision records (`docs/decisions/`).
- `protocol/` - MQTT topic list and JSON Schemas shared by firmware and web.
- `firmware/` - MicroPython source (`src/`), tests, dev tools, and bench scripts for the Pico.
- `web/` - web app for setting alarms and patterns (scaffolded in milestone M6).
- `jobs/calendar/` - calendar-driven alarm jobs (later phase).
- `hardware/` - schematic, enclosure files, photos, and the bill of materials (`bom.csv`).
