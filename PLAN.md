# Shake Awake plan

Each step is small and ends with a check you can do with a `make` command and your
eyes or ears. Do one step at a time.

## 1. Restructure (done when the shaker works as before)
New layout, one `.env`, and `make run` plays the shaker patterns. No network yet.
Check: `make run` and feel the pulse pattern; Ctrl-C stops it.

## 2. Pico joins Wi-Fi and the broker
`net.py` joins Wi-Fi and connects to EMQX Serverless over TLS (port 8883). It publishes a
retained `shakeawake/status` with a last-will of `{"online": false}`.
`gen_pico_env.py` now **requires** the Pico keys and stops if any are blank.
Check: `make run` prints "connected". In MQTTX Web (mqttx.app/web-client), `shakeawake/status`
shows online, and unplugging the Pico shows offline within about 90 seconds.

## 3. Pico obeys commands
The Pico handles `shakeawake/alarm/test` (play a pattern by name for N seconds) and
`shakeawake/alarm/stop`.
Check: publish them from MQTTX Web and feel the shaker start and stop.

Why this is its own step: it tests the Pico side before the website exists, so a
later bug is clearly in either the Pico or the website, not both.

## 4. Website: status and test buttons
`mqtt.js` connects over wss and shows the Pico as online or offline. The page shows one
"Test" button per pattern (from `status.patterns`), plus a Stop button.
Check: `make dev`, open the page, tap a pattern, and feel it.

## 5. Alarm
The website publishes `shakeawake/alarm/set`. The Pico gets the time from NTP, starts the
chosen pattern at the set time, and auto-stops after a maximum run time. Stop works
from the website.
Check: set an alarm 2 minutes ahead in `make dev` and feel it fire on time.

## 6. PWA polish
Real manifest, icons, and a working service worker, so the site installs on a phone.
Check: in Chrome on the laptop (`make dev`), the install icon appears in the address bar
and the installed app opens in its own window. Phones only run service workers over
HTTPS, so the phone "Add to Home Screen" check happens in Step 7.

## 7. Deploy to Vercel
Root directory `web`, VITE_ variables set in the Vercel dashboard. Test the full system
end to end.
Check: on the phone, "Add to Home Screen" opens Shake Awake full screen with its icon;
then, on mobile data, set an alarm and feel it fire.

Security: VITE_ values are readable by anyone who loads the site, so only the broker URL
and the website's username are VITE_ values. The website's password is typed into the
page once and remembered on that device; it is never in the repo or the deployed site.

## MQTT topics (the contract between the Pico and the website)
Times are UTC Unix seconds. Payloads are JSON.

| Topic | Direction | Retained | Example payload |
|---|---|---|---|
| `shakeawake/status` | Pico -> web | yes (+ last-will) | `{"online": true, "playing": "pulse", "patterns": ["pulse", "breathe", "steady", "heartbeat"], "alarm": {"time": 1763290800, "pattern": "pulse"}}` (`"alarm": null` when none), last-will `{"online": false}` |
| `shakeawake/alarm/test` | web -> Pico | no | `{"pattern": "breathe", "seconds": 10}` (default 10, max 90) |
| `shakeawake/alarm/stop` | web -> Pico | no | anything, e.g. `{}` |
| `shakeawake/alarm/set` | web -> Pico | yes | `{"time": 1763290800, "pattern": "pulse"}`; an empty message clears it |

Alarms are one-shot: the Pico forgets an alarm once it fires, and skips any alarm more
than 120 s in the past (so the stale retained `alarm/set` doesn't refire after a restart).
An alarm plays until Stop, or 90 s at most. The website sends `alarm/set` with QoS 1.

Offline: the Pico needs the internet at boot to set its clock. After that, if the network
drops, it keeps its alarm and clock, fires the alarm on time, and tries to reconnect every
30 s (not while playing), resyncing the clock when it does. Each Wi-Fi rejoin switches the
radio off and on first (a plain rejoin can get stuck). After 5 minutes offline with no alarm
waiting, it restarts, since a fresh start always rejoins. Stop from the website can't reach
it while it's offline.

The Pico lists its patterns in `status`, so adding one in `pico/shaker.py` adds a
button on the website with no web change.
