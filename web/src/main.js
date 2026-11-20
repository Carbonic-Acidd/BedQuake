// The page: type the password and slide to unlock (the Worker checks it), then one screen:
// the screen panel (next alarm, current alarm type), the knob (turn to choose a type, press its
// cap to set it), the custom alarm chip, Try and Stop.
// The Worker can't see the Pico or tell us anything back, so this device remembers the alarm
// type and custom alarm it set, and Sync (which resends the calendar) is how the page learns the
// calendar's alarms.
import * as api from './api.js'
import { liveWave } from './wave.js'

// Alarm types: name -> steps (start strength, end strength, ms), copied from pico/shaker.py.
// Keep them in sync.
const TYPES = {
  classic: [[1, 1, 300], [0, 0, 300], [1, 1, 300], [0, 0, 300], [1, 1, 1500], [0, 0, 1000]],
  waves: [[0, 1, 2000], [1, 0, 2000]],
  rise: [[0.2, 1, 20000], [1, 1, 70000]],
  knock: [[1, 1, 120], [0, 0, 120], [1, 1, 120], [0, 0, 120], [1, 1, 120], [0, 0, 900]],
}
const NAMES = Object.keys(TYPES)
const title = (name) => name[0].toUpperCase() + name.slice(1)   // "classic" -> "Classic"
const DEFAULT_TYPE = 'classic'
const TEST_SECONDS = 10      // how long "Try" plays
const DEFAULT_HOUR = 7       // the custom alarm picker opens at the next 7:00
const HEIGHTS = { preview: 1, browsing: 0.95, armed: 0.85, idle: 0.6 }   // the trace's height in each state
const DAWN_S = 8 * 3600      // the screen starts to glow this long before an alarm
const ANGLES = [-45, 45, 135, 225]   // knob positions (degrees clockwise from the top), one per type
const UNLOCK_AT = 0.85       // how far the slider must go to unlock
const TYPE_KEY = 'shakeawake-type'       // where this device remembers the alarm type it set
const MANUAL_KEY = 'shakeawake-manual'   // ... and its custom alarm
const STATUS_MS = 2500       // how long a failure message shows
const DONE_MS = 1200         // how long Sync shows its checkmark
const SHAKE_MS = 600         // matches the shake animation in style.css
const TICK_MS = 30_000       // how often the countdown refreshes

const $ = (id) => document.getElementById(id)
const now = () => Date.now() / 1000
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches
const setWave = liveWave($('wave-path'), reducedMotion)
const store = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)) } catch {} }
const recall = (key) => { try { return JSON.parse(localStorage.getItem(key)) } catch { return null } }

let alarmType = TYPES[recall(TYPE_KEY)] ? recall(TYPE_KEY) : DEFAULT_TYPE
let browse = NAMES.indexOf(alarmType)   // the type the knob points at
let knobAngle = ANGLES[browse]          // where the knob rests; grows past 360 as it's turned round
const manual = { time: 0, on: false }   // the custom alarm; `on` goes false once it has passed
Object.assign(manual, recall(MANUAL_KEY))
let calendarNext = null   // [UTC seconds, type] from the last sync
let preview = null        // type name while "Try" plays
let previewTimer = 0
let statusTimer = 0

// ---------- Small helpers ----------
function shake(element) {
  element.classList.remove('shake')
  void element.offsetWidth   // restart the animation
  element.classList.add('shake')
  setTimeout(() => element.classList.remove('shake'), SHAKE_MS)
}

function showStatus(text) {
  $('status').textContent = text
  $('status').dataset.show = ''
  clearTimeout(statusTimer)
  statusTimer = setTimeout(() => delete $('status').dataset.show, STATUS_MS)
}

// Runs an API call. On failure it shows why (or locks, if the password stopped working).
async function run(call) {
  try {
    await call()
    return true
  } catch (error) {
    if (error.message === 'wrong password') showLock()
    else showStatus('Not sent: ' + error.message)
    return false
  }
}

// View Transitions move the logo and open the slider into the screen.
function swap(update) {
  if (document.startViewTransition && !reducedMotion) document.startViewTransition(update)
  else update()
}

const pad = (n) => String(n).padStart(2, '0')
function toInputValue(seconds) {
  const d = new Date(seconds * 1000)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
function resetPicker() {
  const d = new Date()
  d.setHours(DEFAULT_HOUR, 0, 0, 0)
  if (d.getTime() <= Date.now()) d.setDate(d.getDate() + 1)
  $('custom-input').value = toInputValue(d.getTime() / 1000)
}
const pickedTime = () => {
  const value = $('custom-input').value
  return value ? Math.floor(new Date(value).getTime() / 1000) : 0
}

// "tomorrow", "Tuesday", or "Nov 28" for later; "" for today.
function dayWords(date) {
  const days = Math.round((new Date(date).setHours(0, 0, 0, 0) - new Date().setHours(0, 0, 0, 0)) / 86_400_000)
  if (days === 0) return ''
  if (days === 1) return 'tomorrow'
  if (days < 7) return date.toLocaleDateString([], { weekday: 'long' })
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function timeLeft(seconds) {
  const minutes = Math.max(1, Math.ceil((seconds - now()) / 60))
  const days = Math.floor(minutes / 1440)
  const hours = Math.floor((minutes % 1440) / 60)
  return days ? `${days}d ${hours}h` : hours ? `${hours}h ${minutes % 60}m` : `${minutes}m`
}

// ---------- Drawing the screen ----------
function nextAlarm() {
  const times = []
  if (manual.on) times.push(manual.time)
  if (calendarNext && calendarNext[0] > now()) times.push(calendarNext[0])
  return times.length ? Math.min(...times) : null
}

function render() {
  if (manual.on && manual.time <= now()) {   // it has passed: back to "Set custom alarm"
    manual.on = false
    store(MANUAL_KEY, manual)
    resetPicker()
  }
  const next = nextAlarm()
  const shown = NAMES[browse]

  // The next alarm: "Next alarm (day)", the time, "Wake up in ..."
  $('screen').toggleAttribute('data-empty', !next)
  if (next) {
    const date = new Date(next * 1000)
    const parts = new Intl.DateTimeFormat([], { hour: 'numeric', minute: '2-digit' }).formatToParts(date)
    $('next-label').textContent = ('Next alarm ' + dayWords(date)).trim()
    $('next-time').textContent = parts.filter((p) => p.type !== 'dayPeriod').map((p) => p.value).join('').trim()
    $('next-period').textContent = parts.find((p) => p.type === 'dayPeriod')?.value || ''
    $('next-until').textContent = 'Wake up in ' + timeLeft(next)
  } else {
    $('next-label').textContent = 'No alarm set'
    $('next-time').textContent = '--:--'
    $('next-period').textContent = ''
    $('next-until').textContent = ''
  }

  // The trace plays "Try" at full height and the type on the knob a little lower; the screen
  // glows brighter (dawn) as the alarm gets closer
  const height = preview ? HEIGHTS.preview : shown !== alarmType ? HEIGHTS.browsing : next ? HEIGHTS.armed : HEIGHTS.idle
  setWave(TYPES[preview || shown], height)
  $('wave').toggleAttribute('data-live', Boolean(preview || next))
  $('app').toggleAttribute('data-playing', Boolean(preview))
  $('try-text').textContent = preview ? 'Playing' : 'Try'
  $('app').style.setProperty('--dawn', next ? Math.min(1, Math.max(0, 1 - (next - now()) / DAWN_S)) : 0)

  // The knob and the alarm type that's set
  $('current-type').textContent = title(alarmType)
  if (!knobDrag) $('knob').style.setProperty('--angle', knobAngle + 'deg')
  $('knob').setAttribute('aria-valuenow', browse)
  $('knob').setAttribute('aria-valuetext', title(shown))
  for (const label of $('knob-labels').children) {
    label.setAttribute('aria-current', label.dataset.type === shown)
    label.toggleAttribute('data-set', label.dataset.type === alarmType)
  }
  $('deck').toggleAttribute('data-changed', shown !== alarmType)
  $('knob-cap').setAttribute('aria-label', shown === alarmType ? 'Alarm type set' : 'Set alarm type to ' + title(shown))

  $('custom').toggleAttribute('data-set', manual.on)
  $('custom-text').textContent = manual.on
    ? new Date(manual.time * 1000).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
    : 'Set custom alarm'
}

// ---------- Actions ----------
// Points the knob at another alarm type, turning it the short way round.
function browseTo(index) {
  browse = index
  knobAngle += ((ANGLES[index] - knobAngle) % 360 + 540) % 360 - 180
  render()
}
// Turns the knob one type clockwise (1) or back (-1), wrapping round.
function browseStep(step) {
  browse = (browse + step + NAMES.length) % NAMES.length
  knobAngle += 90 * step
  render()
}

// Makes the type the knob points at the one every alarm plays (calendar and custom).
async function chooseType() {
  const name = NAMES[browse]
  if (name === alarmType) return
  const before = alarmType
  alarmType = name
  store(TYPE_KEY, name)
  render()
  if (!(await run(() => api.setType(name)))) {
    alarmType = before
    store(TYPE_KEY, before)
    render()
  }
}

// Plays the type the knob points at on the shaker for a few seconds.
async function tryType() {
  preview = NAMES[browse]
  $('app').removeAttribute('data-playing')   // restart the Try countdown bar
  void $('app').offsetWidth
  clearTimeout(previewTimer)
  previewTimer = setTimeout(endPreview, TEST_SECONDS * 1000)
  render()
  if (!(await run(() => api.test(preview, TEST_SECONDS)))) endPreview()
}

function endPreview() {
  clearTimeout(previewTimer)
  preview = null
  render()
}

async function stop() {
  endPreview()
  await run(api.stop)
}

// Sends the picked time as the custom alarm (replacing the last one).
async function setCustom() {
  const time = pickedTime()
  if (time <= now()) return shake($('custom-pick'))
  const before = { ...manual }
  Object.assign(manual, { time, on: true })
  store(MANUAL_KEY, manual)
  render()
  if (!(await run(() => api.setAlarm(time, alarmType)))) {
    Object.assign(manual, before)
    store(MANUAL_KEY, manual)
    render()
  }
}

async function clearCustom() {
  manual.on = false
  store(MANUAL_KEY, manual)
  resetPicker()
  render()
  if (!(await run(api.clearAlarm))) {
    manual.on = true
    store(MANUAL_KEY, manual)
    render()
  }
}

async function sync() {
  const button = $('sync')
  if (button.dataset.state === 'busy') return
  button.dataset.state = 'busy'
  try {
    calendarNext = (await api.sync())[0] || null
    button.dataset.state = 'done'
    setTimeout(() => { button.dataset.state = '' }, DONE_MS)
    render()
  } catch (error) {
    button.dataset.state = ''
    shake(button)
    if (error.message === 'wrong password') showLock()
    else showStatus('Sync failed: ' + error.message)
  }
}

// ---------- Turning the knob (all the way round, as many turns as you like) ----------
let knobDrag = null   // { angle, last } while it's being turned
const typeAt = (angle) => (((Math.round((angle - ANGLES[0]) / 90)) % NAMES.length) + NAMES.length) % NAMES.length
const snap = (angle) => ANGLES[0] + 90 * Math.round((angle - ANGLES[0]) / 90)
function pointerAngle(event) {   // degrees clockwise from the top of the knob
  const box = $('knob').getBoundingClientRect()
  return Math.atan2(event.clientX - (box.left + box.width / 2), (box.top + box.height / 2) - event.clientY) * 180 / Math.PI
}
$('knob').onpointerdown = (event) => {
  knobDrag = { angle: knobAngle, last: pointerAngle(event) }
  $('knob').setPointerCapture(event.pointerId)
  $('knob').classList.add('dragging')
}
$('knob').onpointermove = (event) => {
  if (!knobDrag) return
  const angle = pointerAngle(event)
  knobDrag.angle += ((angle - knobDrag.last + 540) % 360) - 180   // the short way round
  knobDrag.last = angle
  $('knob').style.setProperty('--angle', knobDrag.angle + 'deg')
  if (typeAt(knobDrag.angle) !== browse) {
    browse = typeAt(knobDrag.angle)
    render()
  }
}
$('knob').onpointerup = $('knob').onpointercancel = () => {
  if (!knobDrag) return
  knobAngle = snap(knobDrag.angle)   // settles on the type it points at
  knobDrag = null
  $('knob').classList.remove('dragging')
  render()
}
$('knob').onkeydown = (event) => {
  if (['ArrowRight', 'ArrowUp'].includes(event.key)) { event.preventDefault(); browseStep(1) }
  if (['ArrowLeft', 'ArrowDown'].includes(event.key)) { event.preventDefault(); browseStep(-1) }
  if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); chooseType() }
}

// ---------- Password + slide to unlock (one control) ----------
let progress = 0
let dragFrom = null
let checking = false
const travel = () => $('slide').clientWidth - $('slide-thumb').offsetWidth - 2 * parseFloat(getComputedStyle($('slide')).paddingLeft)

function setSlide(value) {
  progress = value
  $('slide').style.setProperty('--progress', value)
  $('slide').style.setProperty('--x', value * travel() + 'px')
}

// Asks for the password: empties the track and shows `hint` in it.
function askPassword(hint = 'Enter password') {
  setSlide(0)
  $('password').value = ''
  $('password').placeholder = hint
  $('slide').toggleAttribute('data-ready', false)
}

$('password').oninput = () => $('slide').toggleAttribute('data-ready', $('password').value !== '')
$('slide-thumb').onpointerdown = (event) => {
  if (checking) return
  if (!$('password').value) {   // nothing typed yet: point at the field instead of sliding
    $('password').focus()
    return shake($('slide'))
  }
  dragFrom = event.clientX - progress * travel()
  $('slide-thumb').setPointerCapture(event.pointerId)
  $('slide').classList.add('dragging')
}
$('slide-thumb').onpointermove = (event) => {
  if (dragFrom !== null) setSlide(Math.min(1, Math.max(0, (event.clientX - dragFrom) / travel())))
}
$('slide-thumb').onpointerup = $('slide-thumb').onpointercancel = () => {
  if (dragFrom === null) return
  dragFrom = null
  $('slide').classList.remove('dragging')
  if (progress >= UNLOCK_AT) login()
  else setSlide(0)
}
$('slide-thumb').onkeydown = (event) => {   // keyboard: Enter or Space unlocks
  if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); login() }
}

// Checks the typed password with the Worker.
async function login() {
  if (checking) return
  const typed = $('password').value
  if (!typed) {
    $('password').focus()
    return shake($('slide'))
  }
  checking = true
  setSlide(1)
  $('slide').classList.add('checking')
  try {
    await api.login(typed)
    unlock()
  } catch (error) {
    askPassword(error.message === 'wrong password' ? 'Enter password' : 'No connection, try again')
    shake($('slide'))
    $('password').focus()
  } finally {
    checking = false
    $('slide').classList.remove('checking')
  }
}

function unlock() {
  render()
  swap(() => {
    $('lock').hidden = true
    $('app').hidden = false
    $('app').classList.remove('enter')
    void $('app').offsetWidth
    $('app').classList.add('enter')
  })
  askPassword()   // the password lives only inside api.js from here on
  sync()
}

// Back to the lock screen (the password stopped working).
function showLock() {
  endPreview()
  askPassword()
  swap(() => {
    $('app').hidden = true
    $('lock').hidden = false
  })
}

// ---------- Start ----------
$('knob-labels').replaceChildren(...NAMES.map((name, index) => {
  const label = document.createElement('button')
  label.className = 'knob-label'
  label.dataset.type = name
  label.textContent = title(name)
  label.style.setProperty('--a', ANGLES[index] + 'deg')
  label.onclick = () => browseTo(index)
  return label
}))

if (manual.on && manual.time > now()) $('custom-input').value = toInputValue(manual.time)
else resetPicker()
$('custom-input').onchange = setCustom
$('custom-input').onclick = () => { try { $('custom-input').showPicker() } catch {} }   // desktop: open the calendar
$('custom-clear').onclick = clearCustom
$('knob-cap').onclick = chooseType
$('try').onclick = tryType
$('app').style.setProperty('--try-ms', TEST_SECONDS * 1000 + 'ms')   // how long the Try bar takes to drain
$('stop').onclick = stop
$('sync').onclick = sync
$('lock').onsubmit = (event) => { event.preventDefault(); login() }
setInterval(() => { if (!$('app').hidden) render() }, TICK_MS)

$('password').focus()

if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js')
