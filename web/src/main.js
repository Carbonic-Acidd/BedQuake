// The page: sends test, stop, alarm and calendar sync commands to the Worker's /api, which
// passes them on to the Pico. The page can't see the Pico, so it only shows whether each
// command was sent.
//
// Password: the site itself holds none. You type the shared password once; this device
// remembers it and sends it with every /api call, and the Worker checks it (backend/src/entry.py).
const PATTERNS = ['breathe', 'heartbeat', 'pulse', 'steady']   // must match pico/shaker.py
const DEFAULT_PATTERN = 'pulse'
const TEST_SECONDS = 10   // how long a test button plays
const PASSWORD_KEY = 'shakeawake-password'   // where this device remembers the password

const $ = (id) => document.getElementById(id)

const describe = (time) => new Date(time * 1000).toLocaleString([], {
  weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
})

// localStorage can be blocked (e.g. private browsing); then the password lasts until reload.
let password = ''
try { password = localStorage.getItem(PASSWORD_KEY) || '' } catch {}

function askPassword(note) {
  password = ''
  try { localStorage.removeItem(PASSWORD_KEY) } catch {}
  $('login-note').textContent = note
  $('login').hidden = false
}

// Calls the Worker. Returns its reply, or throws an Error whose message suits the page.
async function api(method, path, body) {
  let response
  try {
    response = await fetch('/api/' + path, {
      method,
      headers: { Authorization: 'Bearer ' + password, ...(body ? { 'Content-Type': 'application/json' } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new Error('no connection')
  }
  const data = await response.json().catch(() => ({}))
  if (response.status === 401) {
    askPassword('Wrong password, try again.')
    throw new Error('wrong password')
  }
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'error ' + response.status)
  return data
}

// Sends a command and shows the outcome; `what` describes it for the message.
async function send(method, path, body, what) {
  $('result').textContent = 'Sending...'
  try {
    await api(method, path, body)
    $('result').textContent = 'Sent: ' + what
  } catch (error) {
    $('result').textContent = 'Not sent: ' + error.message
  }
}

// Checks a typed password right away (against /api/health) before remembering it.
async function login(event) {
  event.preventDefault()
  password = $('password').value
  $('login-note').textContent = 'Checking...'
  try {
    await api('GET', 'health')
  } catch (error) {
    if (error.message !== 'wrong password') $('login-note').textContent = 'Couldn\'t check it: ' + error.message
    return
  }
  try { localStorage.setItem(PASSWORD_KEY, password) } catch {}
  $('login').hidden = true
  $('result').textContent = 'Password OK. This device will remember it.'
  sync()
}

// Reads the calendar and sends its alarms to the Pico (the same job as the nightly sync), then
// shows the next one. The Worker keeps no copy of what it sent, so syncing is how the page knows.
async function sync() {
  $('next-alarm').textContent = 'Syncing...'
  try {
    const { alarms } = await api('POST', 'sync')   // [[UTC seconds, pattern], ...] in time order
    $('next-alarm').textContent = alarms.length
      ? 'Next alarm: ' + describe(alarms[0][0]) + ' · ' + alarms[0][1]
      : 'No calendar alarms in the next 7 days'
  } catch (error) {
    $('next-alarm').textContent = 'Sync failed: ' + error.message
  }
}

function setAlarm() {
  const value = $('alarm-time').value
  const time = Math.floor(new Date(value).getTime() / 1000)   // local -> UTC seconds
  if (!value || time <= Date.now() / 1000) {
    $('result').textContent = 'Pick a time in the future.'
    return
  }
  const pattern = $('alarm-pattern').value
  send('PUT', 'alarm', { time, pattern }, 'alarm ' + describe(time) + ' · ' + pattern)
}

$('patterns').replaceChildren(...PATTERNS.map((name) => {
  const button = document.createElement('button')
  button.textContent = name
  button.onclick = () => send('POST', 'test', { pattern: name, seconds: TEST_SECONDS }, name + ' for ' + TEST_SECONDS + ' s')
  return button
}))
$('alarm-pattern').replaceChildren(...PATTERNS.map((name) => new Option(name, name)))
$('alarm-pattern').value = DEFAULT_PATTERN

$('stop').onclick = () => send('POST', 'stop', null, 'stop')
$('alarm-set').onclick = setAlarm
$('alarm-clear').onclick = () => send('DELETE', 'alarm', null, 'alarm cleared')
$('sync').onclick = sync
$('login').onsubmit = login
if (!password) askPassword('Enter the Shake Awake password. This device will remember it.')
else sync()

// Older versions remembered the broker password on this device. It isn't used any more.
try { localStorage.removeItem('shakeawake-mqtt-password') } catch {}

if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js')
