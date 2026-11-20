// The only code that talks to the network: the Worker's /api (backend/src/entry.py), which
// passes commands on to the Pico. The site holds no secrets. The shared password is typed on
// every visit, kept only in memory, sent with every call, and checked by the Worker.
let password = ''

// Older versions remembered passwords on this device. Forget them, so nobody skips the lock.
try {
  localStorage.removeItem('shakeawake-password')
  localStorage.removeItem('shakeawake-mqtt-password')
} catch {}

// Calls the Worker. Returns its reply, or throws an Error whose message suits the page:
// "wrong password", "no connection", or the Worker's own reason.
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
    password = ''
    throw new Error('wrong password')
  }
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'error ' + response.status)
  return data
}

// Checks a typed password with the Worker; later calls use it if it works.
export async function login(typed) {
  password = typed
  try {
    await api('GET', 'health')
  } catch (error) {
    password = ''
    throw error
  }
}

// Reads the calendar and sends its alarms to the Pico. Returns [[UTC seconds, type], ...].
export const sync = async () => (await api('POST', 'sync')).alarms
export const setAlarm = (time, pattern) => api('PUT', 'alarm', { time, pattern })
export const clearAlarm = () => api('DELETE', 'alarm')
export const setType = (pattern) => api('PUT', 'type', { pattern })   // the type every alarm plays
export const test = (pattern, seconds) => api('POST', 'test', { pattern, seconds })
export const stop = () => api('POST', 'stop')
