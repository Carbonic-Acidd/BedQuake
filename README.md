# Shake Awake

A silent bed-shaker alarm. A Raspberry Pi Pico WH drives a bass shaker through an
amp. A phone web app, served by a Cloudflare Worker, sends commands to the Worker's `/api`,
which publishes them to an EMQX Serverless broker; the Pico gets them over MQTT. Each night
the Worker also turns the next 7 days of a calendar into alarms.

```
phone --HTTPS + password--> Worker (/api) --REST--> EMQX --MQTT/TLS--> Pico
```

## Prerequisites
Python 3, Node LTS, Make, and uv 0.13.4 or newer (`winget install astral-sh.uv`). On Windows: `winget install GnuWin32.Make`, or use Git Bash.
Accounts: EMQX Cloud (a Serverless deployment) and Cloudflare (free Workers plan; no card needed).
The first `make backend-deploy` creates the site at `https://shakeawake.<your-subdomain>.workers.dev`.
Run every `make` command from the repo root.

## First-time setup
```
cp .env.example .env     # then fill it in; each key has a comment saying where it comes from
make setup               # Python tools + web packages
make pico-setup          # once per Pico, with the Pico plugged in
cd backend && uv run pywrangler login && cd ..   # once: lets this laptop deploy to Cloudflare
```

### EMQX
1. In the EMQX Cloud console, open the deployment's **Overview**.
2. Copy the **REST API** address into `EMQX_API_URL` (ends in `/api/v5`).
3. Under **API Key**, select **+ New API Key**; put the App ID in `EMQX_API_KEY` and the
   App Secret in `EMQX_API_SECRET` (the secret is only shown once).
4. Under **Access Control > Authentication**, add a username and password for the Pico
   (`PICO_MQTT_USER`, `PICO_MQTT_PASS`); `MQTT_HOST` is the deployment's address.

### The website's password
The page is public, but it holds no secrets and can do nothing on its own. Every `/api`
call must carry the shared password, which the Worker compares with its `APP_PASSWORD`
secret; anything else gets a 401 and nothing is sent to the Pico.
1. Put a long passphrase in `APP_PASSWORD` (four or five random words; plain letters,
   numbers and spaces).
2. `make secrets`, then `make backend-deploy`.
3. Open the site on each phone and type the password once; that device remembers it.

To change it: edit `.env`, run `make secrets`, and type the new one on each device (the
page asks again by itself). With no `APP_PASSWORD` set, nobody can use `/api`.

### Deploy
Pushing to `main` deploys the Worker automatically when `backend/` or `web/` changed
(`.github/workflows/deploy.yml`; watch it in the repo's **Actions** tab). One-time setup:
1. Cloudflare dashboard > **Manage Account** > **Account API Tokens** > **Create Token** >
   template **Edit Cloudflare Workers**, limited to your account. Copy the token.
2. Copy the **Account ID** from the **Workers & Pages** overview page.
3. GitHub repo > **Settings** > **Secrets and variables** > **Actions** > **New repository
   secret**: add `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`.

Still by hand:
```
make secrets          # after changing any backend value in .env (CI never sees them)
make backend-deploy   # deploy from the laptop without pushing (e.g. to try something)
make run              # after changing pico/ (with the Pico plugged in)
```
Logs and each request's CPU time: dashboard > **Workers & Pages** > **shakeawake** >
**Observability**. The calendar sync runs at 08:00 UTC; `POST /api/sync` runs it now (the
page's Sync button, and opening the page).

## Daily commands
- `make run`: copy the code to the Pico and run it. Ctrl-C stops it, then Ctrl-] exits.
- `make stop`: stop whatever is running on the Pico.
- `make logs`: open the Pico's REPL.
- `make backend-dev`: build the website and run the Cloudflare Worker at http://localhost:8787.
- `make backend-deploy`: build the website and deploy the Worker.
- `make secrets`: upload the backend's values from `.env` to Cloudflare.
- `make help`: list all commands.

## Files
- `Makefile`: every command above.
- `.github/workflows/deploy.yml`: deploys the Worker on every push to `main` (GitHub Actions).
- `.env.example`: the config keys; copy it to `.env` (never committed) for real values.
- `requirements.txt`: laptop Python tools (mpremote, python-dotenv).
- `PLAN.md`: the roadmap and the MQTT topics contract.
- `scripts/gen_pico_env.py`: turns `.env` into `pico/env.py`, because the Pico can't read `.env`.
- `scripts/gen_dev_vars.py`: copies the backend's keys from `.env` to `backend/.dev.vars` (local dev) or uploads them as Worker secrets.
- `backend/wrangler.jsonc`: the Cloudflare Worker's config; serves `web/dist` and sends `/api/*` to Python.
- `backend/pyproject.toml`: the Worker's Python packages: FastAPI, icalendar, recurring-ical-events (`uv.lock` and `pylock.toml` pin them).
- `backend/src/entry.py`: the Worker: the password check and the `/api` endpoints.
- `backend/src/emqx.py`: publishes MQTT messages through EMQX's REST API.
- `backend/src/calendar_job.py`: reads the calendar (`ICS_URL`) and works out the next 7 days' alarms.- `pico/main.py`: runs on boot and wires the shaker, alarms and network together.
- `pico/shaker.py`: drives the shaker; vibration patterns are defined at the top (keep `web/src/main.js`'s list in sync).
- `pico/net.py`: Wi-Fi, clock (NTP) and MQTT; never blocks waiting for Wi-Fi.
- `pico/alarms.py`: the calendar and manual alarm lists, saved in flash; decides when one is due.
- `pico/env.py`: generated from `.env`, never edited or committed.
- `web/package.json`: web dependencies (Vite).
- `web/index.html`: the page.
- `web/src/main.js`: the page's code; asks for the password once and calls the Worker's `/api`.
- `web/public/manifest.webmanifest`: lets the phone install the site as an app.
- `web/public/sw.js`: service worker; opens the last loaded page when offline (never caches `/api`).
- `web/public/*.png`: the logo (page header) and app icons (home screen and install).
