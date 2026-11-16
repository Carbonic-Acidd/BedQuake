// Talks to the EMQX broker over wss. Knows nothing about the page.
import mqtt from 'mqtt'

const STATUS_TOPIC = 'bedquake/status'
const TEST_TOPIC = 'bedquake/alarm/test'
const STOP_TOPIC = 'bedquake/alarm/stop'

let client

// onStatus(status) gets each status message from the Pico.
// onConnection(text) gets 'connecting', 'connected' or 'disconnected'.
export function connect(onStatus, onConnection) {
  onConnection('connecting')
  client = mqtt.connect(import.meta.env.VITE_MQTT_URL, {
    username: import.meta.env.VITE_MQTT_USER,
    password: import.meta.env.VITE_MQTT_PASS,
  })
  client.on('connect', () => {
    onConnection('connected')
    client.subscribe(STATUS_TOPIC)   // retained, so the current status arrives right away
  })
  client.on('reconnect', () => onConnection('connecting'))
  client.on('close', () => onConnection('disconnected'))
  client.on('message', (topic, payload) => {
    try {
      onStatus(JSON.parse(payload.toString()))
    } catch {
      console.warn('Ignored bad status:', payload.toString())
    }
  })
}

export function test(pattern, seconds) {
  client.publish(TEST_TOPIC, JSON.stringify({ pattern, seconds }))
}

export function stop() {
  client.publish(STOP_TOPIC, '{}')
}
