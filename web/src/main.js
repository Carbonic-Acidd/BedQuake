// The page: shows the Pico's status and sends test, stop and alarm commands.
// Everything shown about the Pico comes from its own status messages, not from this page.
import { connect, test, stop, setAlarm, clearAlarm } from './mqtt.js'

const TEST_SECONDS = 10           // how long a test button plays
const CONFIRM_TIMEOUT_MS = 5000   // how long to wait for the Pico to confirm an alarm change

const $ = (id) => document.getElementById(id)
let shownPatterns = ''   // the pattern names the buttons were built from
let heard = false        // has any status arrived yet?
let online = false
let picoAlarm            // the alarm the Pico last reported: undefined = unknown, null = none
let pending              // the alarm we last sent that the Pico hasn't confirmed: undefined = none
let pendingLate = false  // the Pico is online but hasn't confirmed within CONFIRM_TIMEOUT_MS
let pendingTimer

const sameAlarm = (a, b) => (a && b ? a.time === b.time && a.pattern === b.pattern : a === b)
const describe = (alarm) => !alarm ? 'no alarm'
  : new Date(alarm.time * 1000).toLocaleString([], {
      weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
    }) + ' · ' + alarm.pattern

function render() {
  $('pico').textContent = online ? 'Pico online' : heard ? 'Pico offline' : 'Waiting for the Pico...'
  $('pico').className = online ? 'online' : 'offline'

  for (const button of $('patterns').children) button.disabled = !online
  $('stop').disabled = !online

  $('alarm-now').textContent = picoAlarm === undefined ? 'Unknown' : picoAlarm ? describe(picoAlarm) : 'No alarm set'
  $('alarm-note').textContent = !online && picoAlarm !== undefined ? 'Last known. The Pico is offline.' : ''

  $('alarm-pending').textContent = pending === undefined ? ''
    : !online ? 'Sent: ' + describe(pending) + '. Saved on the broker; the Pico gets it when it reconnects.'
    : pendingLate ? 'The Pico hasn\'t confirmed: ' + describe(pending) + '. Try again.'
    : 'Sending: ' + describe(pending) + '...'
}

function showStatus(status) {
  heard = true
  online = !!status.online

  const names = (status.patterns || []).slice().sort()   // the Pico's order isn't stable
  if (names.length && names.join() !== shownPatterns) {
    shownPatterns = names.join()
    $('patterns').replaceChildren(...names.map((name) => {
      const button = document.createElement('button')
      button.textContent = name
      button.onclick = () => test(name, TEST_SECONDS)
      return button
    }))
    const chosen = $('alarm-pattern').value || 'pulse'
    $('alarm-pattern').replaceChildren(...names.map((name) => new Option(name, name)))
    $('alarm-pattern').value = names.includes(chosen) ? chosen : names[0]
  }
  for (const button of $('patterns').children) {
    button.classList.toggle('playing', button.textContent === status.playing)
  }
  $('playing').textContent = online && status.playing ? 'Playing: ' + status.playing : ''

  if ('alarm' in status) picoAlarm = status.alarm   // the offline last-will doesn't say
  if (pending !== undefined && sameAlarm(pending, picoAlarm)) pending = undefined
  render()
}

// Only the latest click matters: the broker keeps the last alarm/set, and the page waits
// until the Pico reports exactly that alarm.
function send(alarm) {
  pending = sameAlarm(alarm, picoAlarm) ? undefined : alarm
  pendingLate = false
  clearTimeout(pendingTimer)
  pendingTimer = setTimeout(() => { pendingLate = true; render() }, CONFIRM_TIMEOUT_MS)
  alarm ? setAlarm(alarm.time, alarm.pattern) : clearAlarm()
  render()
}

function onSetAlarm() {
  const time = Math.floor(new Date($('alarm-time').value).getTime() / 1000)   // local -> UTC seconds
  if (!$('alarm-time').value || time <= Date.now() / 1000) {
    $('alarm-pending').textContent = 'Pick a time in the future.'
    return
  }
  send({ time, pattern: $('alarm-pattern').value })
}

if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js')

if (!import.meta.env.VITE_MQTT_URL) {
  $('connection').textContent = 'VITE_MQTT_URL is missing from .env'
} else {
  $('stop').onclick = stop
  $('alarm-set').onclick = onSetAlarm
  $('alarm-clear').onclick = () => send(null)
  connect(showStatus, (text) => { $('connection').textContent = 'Broker: ' + text })
}
render()
