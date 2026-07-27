/* -----------------------------------------------------------------------
 *  service-worker.js – Robust PWA worker for EDUALLY
 * ----------------------------------------------------------------------- */

/* 1️⃣ Cache name – bump this when you change CORE_ASSETS */
const CACHE_NAME = 'educally-pwa-cache-v1';

/* 2️⃣ Assets that you *guarantee* exist on first load.
   Adjust the paths to match the real locations in your project. */
const CORE_ASSETS = [
  '/',                                 // Home page (rendered by Django)
  '/static/css/base.css',              // Your main stylesheet
  '/static/js/sidebar-toggle.js',     // Example JS – adjust if you don’t have it
  '/static/js/modal.js',               // Example JS – adjust if you don’t have it
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
  '/manifest.json',                     // <-- served by the view, not /static/manifest.json
  '/offline/'                          // Offline fallback page (must be reachable)
];

/* -----------------------------------------------------------------------
 *  Install – pre‑cache the core assets.
 *  We use Promise.allSettled() so a single failing request does NOT
 *  reject the whole install step.  Failed resources are simply skipped.
 * ----------------------------------------------------------------------- */
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(async cache => {
      // Fetch each URL, verify it’s ok, then put it into the cache.
      const results = await Promise.allSettled(
        CORE_ASSETS.map(async url => {
          const response = await fetch(url, {cache: 'no-store'}); // force network
          if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
          }
          await cache.put(url, response);
        })
      );

      // Log any assets that failed – they will just be fetched later on‑demand.
      results.forEach((result, i) => {
        if (result.status === 'rejected') {
          console.warn('SW: Could not cache', CORE_ASSETS[i], result.reason);
        }
      });
    }).then(() => self.skipWaiting())                // take control ASAP
  );
});

/* -----------------------------------------------------------------------
 *  Activate – delete old caches that don't match the current name.
 * ----------------------------------------------------------------------- */
self.addEventListener('activate', event => {
  const allowedCaches = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then(names =>
      Promise.all(
        names.map(name => {
          if (!allowedCaches.includes(name)) {
            return caches.delete(name);
          }
        })
      )
    ).then(() => self.clients.claim())
  );
});

/* -----------------------------------------------------------------------
 *  Fetch – decide how to respond to every request.
 * ----------------------------------------------------------------------- */
self.addEventListener('fetch', event => {
  const req = event.request;

  // We only handle GET – let POST/PUT/etc. fall through to the network.
  if (req.method !== 'GET') return;

  // --------------------------------------------------------------
  // a) Navigation requests (full page loads) – network‑first.
  // --------------------------------------------------------------
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then(networkRes => {
          // Cache a copy of the successful response for later offline use.
          if (networkRes && networkRes.status === 200) {
            const copy = networkRes.clone();
            caches.open(CACHE_NAME).then(c => c.put(req, copy));
          }
          return networkRes;
        })
        .catch(() => caches.match(req) || caches.match('/offline/')) // fallback
    );
    return;
  }

  // --------------------------------------------------------------
  // b) All other requests (CSS, JS, images, fonts, …) – cache‑first.
  // --------------------------------------------------------------
  event.respondWith(
    caches.match(req).then(cached => {
      if (cached) return cached;

      // Not in cache → fetch from network and put a copy in the cache.
      return fetch(req)
        .then(networkRes => {
          // Only cache same‑origin successful responses.
          if (networkRes && networkRes.status === 200 && req.url.startsWith(self.location.origin)) {
            const copy = networkRes.clone();
            caches.open(CACHE_NAME).then(c => c.put(req, copy));
          }
          return networkRes;
        })
        .catch(() => {
          // Optional: you could return a small placeholder for images etc.
          // if (req.destination === 'image') return caches.match('/static/img/placeholder.png');
          return new Response('Network error', {status: 504});
        });
    })
  );
});
