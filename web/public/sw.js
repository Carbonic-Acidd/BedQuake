// Service worker: lets phones install Shake Awake as an app, and opens the last loaded
// page when there's no internet (the Pico controls still need a connection to work).
// /api requests are never touched or cached: they go straight to the network.
const CACHE = 'shakeawake-v1'

self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))

// Network first, so updates show up right away; the cached copy is only an offline fallback.
self.addEventListener('fetch', (event) => {
  const { request } = event
  const url = new URL(request.url)
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return
  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok) {   // don't cache errors
          const copy = response.clone()
          caches.open(CACHE).then((cache) => cache.put(request, copy))
        }
        return response
      })
      .catch(() => caches.match(request)),
  )
})
