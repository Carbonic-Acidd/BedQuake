"""Copies the backend's keys from the root .env to where wrangler can read them.

  python scripts/gen_dev_vars.py            writes backend/.dev.vars (local dev, `make backend-dev`)
  python scripts/gen_dev_vars.py --upload   uploads them as Worker secrets (`make secrets`)

Only the backend keys are copied, so the Wi-Fi and Pico passwords never reach the Worker.
Blank keys are skipped. Files written here are gitignored; the upload's file is deleted after.
"""
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
BACKEND = ROOT / "backend"
BACKEND_KEYS = ["ICS_URL", "EMQX_API_URL", "EMQX_API_KEY", "EMQX_API_SECRET",
                "ALARM_OFFSET_MIN", "DEVICE_ID", "APP_PASSWORD"]

if not ENV_FILE.exists():
    sys.exit("No .env file. Run: cp .env.example .env  (then fill it in)")

env = dotenv_values(ENV_FILE)
values = {key: (env.get(key) or "").strip() for key in BACKEND_KEYS}
lines = "".join(f'{key}="{value}"\n' for key, value in values.items() if value)
skipped = [key for key, value in values.items() if not value]
if skipped:
    print("Blank in .env, skipped:", ", ".join(skipped))

if "--upload" not in sys.argv:
    (BACKEND / ".dev.vars").write_text(lines, encoding="utf-8")
    print("Wrote backend/.dev.vars")
    sys.exit()

upload_file = BACKEND / ".secrets.env"
upload_file.write_text(lines, encoding="utf-8")
try:
    result = subprocess.run(["uv", "run", "pywrangler", "secret", "bulk", upload_file.name], cwd=BACKEND)
finally:
    upload_file.unlink()   # never leave secrets lying around
sys.exit(result.returncode)
