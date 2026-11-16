# BedQuake plan

Each step is small and ends with a check you can do with a `make` command and your
eyes or ears. Do one step at a time.

## 1. Restructure (done when the shaker works as before)
New layout, one `.env`, and `make run` plays the shaker patterns. No network yet.
Check: `make run` and feel the pulse pattern; Ctrl-C stops it.

## 2. Pico joins Wi-Fi and HiveMQ
`net.py` joins Wi-Fi and connects to HiveMQ Cloud over TLS (port 8883). It publishes a
retained `bedquake/status` with a last-will of `{"online": false}`.
`gen_pico_env.py` now **requires** the Pico keys and stops if any are blank.
Check: `make run` prints "connected". In the HiveMQ Cloud web client, `bedquake/status`
shows online, and unplugging the Pico shows offline within about a minute.

## 3. Pico obeys commands
The Pico handles `bedquake/alarm/test` (play a pattern by name for N seconds) and
`bedquake/alarm/stop`.
Check: publish them from the HiveMQ web client and feel the shaker start and stop.

Why this is its own step: it tests the Pico side before the website exists, so a
later bug is clearly in either the Pico or the website, not both.

## 4. Website: status and test buttons
`mqtt.js` connects over wss and shows the Pico as online or offline. The page shows one
"Test" button per pattern (from `status.patterns`), plus a Stop button.
Check: `make dev`, open the page, tap a pattern, and feel it.

## 5. Alarm
The website publishes `bedquake/alarm/set`. The Pico gets the time from NTP, starts the
chosen pattern at the set time, and auto-stops after a maximum run time. Stop works
from the website.
Check: set an alarm 2 minutes ahead in `make dev` and feel it fire on time.

## 6. PWA polish
Real manifest, icons, and a working service worker, so the site installs on a phone.
Check: "Add to Home Screen" on the phone opens full screen.

## 7. Deploy to Vercel
Root directory `web`, VITE_ variables set in the Vercel dashboard. Test the full system
end to end.
Check: from the phone on mobile data, set an alarm and feel it fire.

Security note: VITE_ values are readable by anyone who loads the site. Give the website
its own HiveMQ credential, and consider typing the password into the page instead of
building it in.

## MQTT topics (the contract between the Pico and the website)
Times are UTC Unix seconds. Payloads are JSON.

| Topic | Direction | Retained | Example payload |
|---|---|---|---|
| `bedquake/status` | Pico -> web | yes (+ last-will) | `{"online": true, "playing": "pulse", "patterns": ["pulse", "breathe", "steady", "heartbeat"], "alarm": 1763290800}`, last-will `{"online": false}` |
| `bedquake/alarm/test` | web -> Pico | no | `{"pattern": "breathe", "seconds": 10}` |
| `bedquake/alarm/stop` | web -> Pico | no | `{}` |
| `bedquake/alarm/set` | web -> Pico | yes | `{"time": 1763290800, "pattern": "pulse"}`; `{"time": null}` clears it |

The Pico lists its patterns in `status`, so adding one in `pico/shaker.py` adds a
button on the website with no web change.
