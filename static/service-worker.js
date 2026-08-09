/* ------------------------------------------------------------------
 *  service‑worker.js – Updated worker for EDUALLY
 *
 *  * static assets ( /static/, manifest, icons ) → cache‑first
 *  * API calls ( /slm/api/… )                     → network‑first
 *  * navigation (HTML pages)                     → network‑first,
 *                                                   fall back to cached shell when offline
 *
 *  Bump `CACHE_VERSION` on every deploy – that forces a fresh install.
 * ------------------------------------------------------------------ */

const CACHE_VERSION = "{{ PWA_SW_VERSION }}"; // bump this whenever you redeploy
const STATIC_CACHE = `edually-static-${CACHE_VERSION}`;
const SHELL_CACHE = `edually-shell-${CACHE_VERSION}`;

/* ------------------------------------------------------------------
 *  1️⃣  STATIC ASSETS that never change (or are fingerprint‑hashed)
 *
 *  Add every file that you *do* want to be available offline.
 *  If you use Django’s `collectstatic` with hashed filenames you can
 *  simply glob `'/static/**'` – here we list the ones that are needed
 *  for the first paint.
 * ------------------------------------------------------------------ */
const CORE_STATIC_ASSETS = [
  "/static/css/base.css",
  "/static/css/dashboard.css",
  "/static/css/slm/slm.css",
  "/static/css/slm/module_detail.css",
  "/static/css/slm/highlight_ai.css",
  "/static/js/forum/category-dots.js",
  "/static/js/forum/forum_ajax.js",
  "/static/js/forum/forum-reply-focus.js",
  "/static/js/forum/forum-upvote.js",
  "/static/js/ai-helper.js",
  "/static/js/modal.js",
  "/static/js/slm/tab_switching.js",
  "/static/js/slm/subject_ajax.js",
  "/static/js/slm/module_ajax.js",
  "/static/js/slm/personal_material_ajax.js",
  "/static/js/slm/highlight_ai.js",
  "/static/js/slm/utils.js",
  "/manifest.json",
  "/static/icons/icon-192x192.png",
  "/static/icons/icon-512x512.png",
];

/* ------------------------------------------------------------------
 *  2️⃣  OFFLINE FALLBACK PAGE – must exist in your URLconf
 * ------------------------------------------------------------------ */
const OFFLINE_PAGE = "/offline/";

/* ------------------------------------------------------------------
 *  3️⃣  INSTALL – pre‑cache the static assets only.
 * ------------------------------------------------------------------ */
self.addEventListener('install', ev => {
  ev.waitUntil(
    (async () => {
      const cache = await caches.open(STATIC_CACHE);

      // Try to cache each asset one‑by‑one and log the problem.
      for (const url of CORE_STATIC_ASSETS) {
        try {
          await cache.add(url);
        } catch (err) {
          console.error('SW install – failed to cache:', url, err);
          throw err;
        }
      }

      // If we got this far, every asset was cached → activate immediately.
      self.skipWaiting();
    })()
  );
});

/* ------------------------------------------------------------------
 *  4️⃣  ACTIVATE – wipe any old caches that don’t match the current version.
 * ------------------------------------------------------------------ */
self.addEventListener("activate", (ev) => {
  ev.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys.map((key) => {
          if (![STATIC_CACHE, SHELL_CACHE].includes(key)) {
            return caches.delete(key);
          }
        }),
      );
    })().then(() => self.clients.claim()),
  );
});

/* ------------------------------------------------------------------
 *  5️⃣  FETCH – the heart of the worker.
 *
 *  Order matters:
 *    1️⃣  Anything that isn’t a GET → let the network handle it.
 *    2️⃣  API calls (`/slm/api/…`) → network‑first, never store the
 *        response (they’re already cheap and you always need the latest).
 *    3️⃣  Navigation requests (full HTML pages) → network‑first,
 *        falling back to a cached copy (the “app‑shell”) when offline.
 *    4️⃣  All other GETs (static files) → cache‑first.
 *
 *  The `fetch` handler is deliberately *small* – we only care about
 *  the three patterns above, everything else is a simple network‑only.
 * ------------------------------------------------------------------ */
self.addEventListener("fetch", (ev) => {
  const req = ev.request;

  // -----------------------------------------------------------------
  // 5.1  Non‑GET requests (POST, PUT, DELETE, …) → network only.
  // -----------------------------------------------------------------
  if (req.method !== "GET") return; // let Django handle the mutation

  const url = new URL(req.url);

  // -----------------------------------------------------------------
  // 5.2  API requests – NEVER cache, always go to the network.
  // -----------------------------------------------------------------
  if (
    url.pathname.startsWith("/slm/api/") || 
    url.pathname.startsWith("/aihelper/")
  ) {
    ev.respondWith(
      fetch(req).catch(() => {
        // In the very unlikely case the device is offline *and* the
        // user asks for data, we give a friendly 504 response.
        return new Response(
          JSON.stringify({
            error: "Network unavailable – cannot fetch live data.",
          }),
          { status: 504, headers: { "Content-Type": "application/json" } },
        );
      }),
    );
    return;
  }

  // -----------------------------------------------------------------
  // 5.3  Navigation (HTML page) – network‑first, cache for offline.
  // -----------------------------------------------------------------
  if (
    req.mode === "navigate" ||
    req.headers.get("accept")?.includes("text/html")
  ) {
    ev.respondWith(
      fetch(req)
        .then((networkRes) => {
          // -----------------------------------------------------------------
          // 5.3.1  Only cache when the response does not explicitly say “no‑store”.
          // -----------------------------------------------------------------
          const cc = networkRes.headers.get("Cache-Control") || "";
          const canCache = networkRes.status === 200 && !/no-store/.test(cc);

          if (canCache) {
            const copy = networkRes.clone();
            caches.open(SHELL_CACHE).then((cache) => cache.put(req, copy));
          }
          return networkRes;
        })
        .catch(() => {
          // Offline → try a previously‑cached page (if we have one) else the fallback.
          return caches
            .match(req)
            .then((cached) => cached || caches.match(OFFLINE_PAGE));
        }),
    );
    return;
  }

  // -----------------------------------------------------------------
  // 5.4  All other GETs – static assets (CSS, JS, fonts, images, …)
  //        → cache‑first, populate the cache the first time we see it.
  // -----------------------------------------------------------------
  ev.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;

      // Not cached → fetch from network, store a copy if it’s a same‑origin OK response.
      return fetch(req)
        .then((networkRes) => {
          // Only cache successful same‑origin responses.
          if (
            networkRes &&
            networkRes.status === 200 &&
            url.origin === location.origin
          ) {
            const copy = networkRes.clone();
            caches.open(STATIC_CACHE).then((cache) => cache.put(req, copy));
          }
          return networkRes;
        })
        .catch(() => {
          // Optional: return a tiny placeholder for images etc.
          // if (req.destination === 'image') return caches.match('/static/img/placeholder.png');
          return new Response("Network error", { status: 504 });
        });
    }),
  );
});

/* ------------------------------------------------------------------
 *  6️⃣  OPTIONAL – Listen for a “skipWaiting” message from the page.
 *        This lets you force an immediate activation after a deploy.
 * ------------------------------------------------------------------ */
self.addEventListener("push", (event) => {
  const payload = event.data ? event.data.json() : null;
  const title = payload?.title || "EduAlly notification";
  const body = payload?.body || "You have a new announcement.";
  const tag = payload?.tag || "edually-announcement";
  const url = payload?.url || "/account/announcements/";

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      tag,
      icon: payload?.icon || "/static/icons/icon-192x192.png",
      data: { url },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || "/account/announcements/";

  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes(location.origin) && "focus" in client) {
          return client.focus();
        }
      }
      return clients.openWindow(targetUrl);
    }),
  );
});

self.addEventListener("message", (ev) => {
  if (ev.data && ev.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});
