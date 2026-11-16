// Service worker: lets phones install BedQuake as an app, and opens the last loaded
// page when there's no internet (the Pico controls still need a connection to work).
const CACHE = 'bedquake-v2'

self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))

// Network first, so updates show up right away; the cached copy is only an offline fallback.
self.addEventListener('fetch', (event) => {
  const { request } = event
  if (request.method !== 'GET' || new URL(request.url).origin !== self.location.origin) return
  event.respondWith(
    fetch(request)
      .then((response) => {
        const copy = response.clone()
        caches.open(CACHE).then((cache) => cache.put(request, copy))
        return response
      })
      .catch(() => caches.match(request)),
  )
})
