// The page: shows the Pico's status and sends test/stop commands.
import { connect, test, stop } from './mqtt.js'

const TEST_SECONDS = 10   // how long a test button plays

const picoEl = document.querySelector('#pico')
const patternsEl = document.querySelector('#patterns')
const stopEl = document.querySelector('#stop')
const connectionEl = document.querySelector('#connection')
let shownPatterns = ''    // the pattern names the buttons were built from

function showStatus(status) {
  picoEl.textContent = !status.online ? 'Pico offline'
    : status.playing ? 'Playing: ' + status.playing
    : 'Pico online'
  picoEl.className = status.online ? 'online' : 'offline'

  // The offline last-will has no pattern list, so keep the old buttons then.
  const names = (status.patterns || []).slice().sort()   // the Pico's order isn't stable
  if (names.length && names.join() !== shownPatterns) {
    shownPatterns = names.join()
    patternsEl.replaceChildren(...names.map((name) => {
      const button = document.createElement('button')
      button.textContent = name
      button.onclick = () => test(name, TEST_SECONDS)
      return button
    }))
  }
  for (const button of patternsEl.children) {
    button.disabled = !status.online
    button.classList.toggle('playing', button.textContent === status.playing)
  }
  stopEl.disabled = !status.online
}

if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js')

if (!import.meta.env.VITE_MQTT_URL) {
  connectionEl.textContent = 'VITE_MQTT_URL is missing from .env'
} else {
  stopEl.onclick = stop
  connect(showStatus, (text) => { connectionEl.textContent = 'Broker: ' + text })
}
