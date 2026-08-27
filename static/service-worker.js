/* ------------------------------------------------------------------
 * service-worker.js – EduAlly
 *
 * PURPOSE
 * ------------------------------------------------------------------
 * 1. Cache the PWA shell and important static resources.
 * 2. Make previously visited public HTML pages available offline.
 * 3. Keep dynamic/user/AI data network-only.
 * 4. Improve static-resource loading with stale-while-revalidate.
 * 5. Provide an offline fallback page.
 * 6. Handle Web Push notifications.
 *
 * IMPORTANT
 * ------------------------------------------------------------------
 * Dynamic application data is intentionally NOT cached:
 *
 *   /account/
 *   /forum/
 *   /slm/
 *   /aihelper/
 *
 * This prevents stale or user-specific application data from being
 * served as if it were current.
 *
 * Bump PWA_SW_VERSION whenever you deploy a new application version.
 * ------------------------------------------------------------------ */

/* ==================================================================
 * 1. VERSIONING
 * ================================================================== */

const CACHE_VERSION = "{{ PWA_SW_VERSION }}";

const STATIC_CACHE = `edually-static-${CACHE_VERSION}`;
const SHELL_CACHE = `edually-shell-${CACHE_VERSION}`;
const RUNTIME_CACHE = `edually-runtime-${CACHE_VERSION}`;

const OFFLINE_PAGE = "/offline/";

/* ==================================================================
 * 2. PRECACHED CORE ASSETS
 *
 * These are resources that EduAlly should have available immediately
 * after the Service Worker installation succeeds.
 * ================================================================== */

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

  OFFLINE_PAGE,
];

/* ==================================================================
 * 3. CACHE LIMIT
 *
 * Runtime resources are cached as users browse the application.
 * Keep the cache bounded so it cannot grow indefinitely.
 * ================================================================== */

const MAX_RUNTIME_ENTRIES = 100;

/* ==================================================================
 * 4. INSTALL
 *
 * Pre-cache the important application shell.
 *
 * We intentionally DO NOT call skipWaiting() automatically here.
 *
 * This avoids replacing an active worker in the middle of a user's
 * current session. The page can explicitly request SKIP_WAITING when
 * it is ready to update.
 * ================================================================== */

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(STATIC_CACHE);

      for (const url of CORE_STATIC_ASSETS) {
        try {
          await cache.add(url);
        } catch (error) {
          console.error("EduAlly SW: failed to precache:", url, error);

          /*
           * Installation should fail if a required core
           * resource cannot be cached.
           *
           * This prevents activating an incomplete
           * application shell.
           */
          throw error;
        }
      }

      console.log("EduAlly SW: installation completed:", CACHE_VERSION);
    })(),
  );
});

/* ==================================================================
 * 5. ACTIVATE
 *
 * Remove caches belonging to older Service Worker versions.
 * ================================================================== */

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const validCaches = new Set([STATIC_CACHE, SHELL_CACHE, RUNTIME_CACHE]);

      const cacheNames = await caches.keys();

      await Promise.all(
        cacheNames.map((cacheName) => {
          if (!validCaches.has(cacheName)) {
            console.log("EduAlly SW: deleting old cache:", cacheName);

            return caches.delete(cacheName);
          }

          return Promise.resolve();
        }),
      );

      /*
       * Take control after activation.
       *
       * This does not force a new worker to activate during
       * installation. It only applies once this worker is active.
       */
      await self.clients.claim();

      console.log("EduAlly SW: activated:", CACHE_VERSION);
    })(),
  );
});

/* ==================================================================
 * 6. HELPER FUNCTIONS
 * ================================================================== */

/**
 * Check whether a response is safe to put into the Cache API.
 */
function isCacheableResponse(response, request) {
  if (!response) {
    return false;
  }

  if (response.status !== 200) {
    return false;
  }

  /*
   * Only cache same-origin resources.
   */
  if (request.url.startsWith(self.location.origin) === false) {
    return false;
  }

  /*
   * Do not cache responses explicitly marked as no-store.
   */
  const cacheControl = response.headers.get("Cache-Control") || "";

  if (/no-store/i.test(cacheControl)) {
    return false;
  }

  return true;
}

/**
 * Save a response into a cache.
 *
 * Errors are intentionally ignored because a cache failure should
 * never break the user's actual network request.
 */
async function putInCache(cacheName, request, response) {
  try {
    if (!isCacheableResponse(response, request)) {
      return;
    }

    const cache = await caches.open(cacheName);

    await cache.put(request, response.clone());
  } catch (error) {
    console.warn("EduAlly SW: cache write failed:", request.url, error);
  }
}

/**
 * Limit the number of runtime cached resources.
 *
 * The Cache API does not automatically provide an application-level
 * maximum number of entries, so we maintain a simple FIFO-style limit.
 */
async function trimCache(cacheName, maxEntries) {
  try {
    const cache = await caches.open(cacheName);
    const requests = await cache.keys();

    if (requests.length <= maxEntries) {
      return;
    }

    const excess = requests.length - maxEntries;

    for (let index = 0; index < excess; index++) {
      await cache.delete(requests[index]);
    }
  } catch (error) {
    console.warn("EduAlly SW: cache cleanup failed:", error);
  }
}

/**
 * Determine whether a request is for a dynamic EduAlly area.
 *
 * These areas contain user/application data and should always be
 * fetched from the server.
 */
function isDynamicPath(pathname) {
  return (
    pathname === "/account" ||
    pathname.startsWith("/account/") ||
    pathname === "/forum" ||
    pathname.startsWith("/forum/") ||
    pathname === "/slm" ||
    pathname.startsWith("/slm/") ||
    pathname === "/aihelper" ||
    pathname.startsWith("/aihelper/")
  );
}

/**
 * Determine whether a request is a known API request.
 *
 * API responses are never stored by this Service Worker.
 */
function isApiRequest(pathname) {
  return (
    pathname.startsWith("/slm/api/") || pathname.startsWith("/aihelper/api/")
  );
}

/**
 * Determine whether a request is a static resource.
 */
function isStaticRequest(request, url) {
  if (url.origin !== self.location.origin) {
    return false;
  }

  if (url.pathname.startsWith("/static/")) {
    return true;
  }

  if (url.pathname === "/manifest.json") {
    return true;
  }

  if (request.destination === "style") {
    return true;
  }

  if (request.destination === "script") {
    return true;
  }

  if (request.destination === "font") {
    return true;
  }

  if (request.destination === "image") {
    return true;
  }

  return false;
}

/* ==================================================================
 * 7. NETWORK-ONLY
 *
 * Used for:
 *
 * - account
 * - forum
 * - SLM
 * - AI Helper
 * - API requests
 * - authenticated/dynamic data
 *
 * This is intentional.
 * ================================================================== */

async function networkOnly(request) {
  try {
    return await fetch(request);
  } catch (error) {
    /*
     * Return a useful response instead of exposing a generic
     * Service Worker failure.
     *
     * JSON is useful for AJAX/API requests.
     */
    if (request.headers.get("Accept")?.includes("application/json")) {
      return new Response(
        JSON.stringify({
          error:
            "Network unavailable. This EduAlly feature requires an internet connection.",
        }),
        {
          status: 504,
          headers: {
            "Content-Type": "application/json",
          },
        },
      );
    }

    return new Response(
      "Network unavailable. Please reconnect to use this EduAlly feature.",
      {
        status: 504,
        headers: {
          "Content-Type": "text/plain; charset=utf-8",
        },
      },
    );
  }
}

/* ==================================================================
 * 8. STATIC ASSETS
 *
 * Strategy:
 *
 *     CACHE FIRST
 *          ↓
 *     return cached version immediately
 *          +
 *     network refreshes cache in background
 *
 * This gives fast loading while still allowing updated resources to
 * reach the cache.
 * ================================================================== */

async function staleWhileRevalidate(request) {
  const cache = await caches.open(STATIC_CACHE);

  const cachedResponse = await cache.match(request);

  /*
   * Always attempt a network update.
   *
   * waitUntil() allows the Service Worker to continue the cache
   * update after returning the cached response to the browser.
   */
  const networkUpdate = fetch(request)
    .then(async (networkResponse) => {
      if (isCacheableResponse(networkResponse, request)) {
        await cache.put(request, networkResponse.clone());
      }

      return networkResponse;
    })
    .catch(() => null);

  if (cachedResponse) {
    return cachedResponse;
  }

  const networkResponse = await networkUpdate;

  if (networkResponse) {
    return networkResponse;
  }

  return new Response("Resource unavailable while offline.", {
    status: 504,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
    },
  });
}

/* ==================================================================
 * 9. HTML NAVIGATION
 *
 * Strategy:
 *
 *     NETWORK FIRST
 *          ↓
 *     latest server page
 *
 * If offline:
 *
 *     cached page
 *          ↓
 *     /offline/
 *
 * Dynamic/private areas are excluded before this function is called.
 * ================================================================== */

async function networkFirstNavigation(request) {
  try {
    const networkResponse = await fetch(request);

    /*
     * Only store successful HTML responses.
     */
    const contentType = networkResponse.headers.get("Content-Type") || "";

    const cacheControl = networkResponse.headers.get("Cache-Control") || "";

    const canCache =
      networkResponse.status === 200 &&
      contentType.includes("text/html") &&
      !/no-store/i.test(cacheControl);

    if (canCache) {
      await putInCache(SHELL_CACHE, request, networkResponse);
    }

    return networkResponse;
  } catch (error) {
    /*
     * Offline:
     *
     * 1. Try the exact page.
     * 2. Fall back to the dedicated offline page.
     */
    const cachedPage = await caches.match(request);

    if (cachedPage) {
      return cachedPage;
    }

    const offlinePage = await caches.match(OFFLINE_PAGE);

    if (offlinePage) {
      return offlinePage;
    }

    return new Response("EduAlly is offline.", {
      status: 503,
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
      },
    });
  }
}

/* ==================================================================
 * 10. RUNTIME GET RESOURCES
 *
 * Used for same-origin resources that are not part of the core
 * precache but are safe to cache.
 * ================================================================== */

async function runtimeResource(request) {
  const cache = await caches.open(RUNTIME_CACHE);

  const cachedResponse = await cache.match(request);

  if (cachedResponse) {
    /*
     * Return the cached resource immediately.
     *
     * Update the resource in the background.
     */
    fetch(request)
      .then(async (networkResponse) => {
        if (isCacheableResponse(networkResponse, request)) {
          await cache.put(request, networkResponse.clone());

          await trimCache(RUNTIME_CACHE, MAX_RUNTIME_ENTRIES);
        }
      })
      .catch(() => {
        /*
         * Ignore background network errors.
         *
         * The cached response is already available.
         */
      });

    return cachedResponse;
  }

  try {
    const networkResponse = await fetch(request);

    if (isCacheableResponse(networkResponse, request)) {
      await cache.put(request, networkResponse.clone());

      await trimCache(RUNTIME_CACHE, MAX_RUNTIME_ENTRIES);
    }

    return networkResponse;
  } catch (error) {
    return new Response("Resource unavailable while offline.", {
      status: 504,
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
      },
    });
  }
}

/* ==================================================================
 * 11. FETCH EVENT
 * ================================================================== */

self.addEventListener("fetch", (event) => {
  const request = event.request;

  /*
   * Never intercept non-GET requests.
   *
   * POST / PUT / PATCH / DELETE must reach Django normally.
   */
  if (request.method !== "GET") {
    return;
  }

  const url = new URL(request.url);

  /*
   * Ignore cross-origin requests.
   *
   * This keeps the Service Worker focused on EduAlly's own origin.
   */
  if (url.origin !== self.location.origin) {
    return;
  }

  /* --------------------------------------------------------------
   * 11.1 API / dynamic application requests
   * -------------------------------------------------------------- */

  if (isApiRequest(url.pathname) || isDynamicPath(url.pathname)) {
    event.respondWith(networkOnly(request));

    return;
  }

  /* --------------------------------------------------------------
   * 11.2 HTML navigation
   *
   * Public/non-dynamic pages can use network-first caching.
   * -------------------------------------------------------------- */

  const acceptsHtml = request.headers.get("Accept")?.includes("text/html");

  if (request.mode === "navigate" || acceptsHtml) {
    event.respondWith(networkFirstNavigation(request));

    return;
  }

  /* --------------------------------------------------------------
   * 11.3 Static resources
   * -------------------------------------------------------------- */

  if (isStaticRequest(request, url)) {
    event.respondWith(staleWhileRevalidate(request));

    return;
  }

  /* --------------------------------------------------------------
   * 11.4 Other same-origin GET requests
   *
   * Use a limited runtime cache only for resources that are
   * actually requested and successfully returned.
   * -------------------------------------------------------------- */

  event.respondWith(runtimeResource(request));
});

/* ==================================================================
 * 12. PUSH NOTIFICATIONS
 * ================================================================== */

self.addEventListener("push", (event) => {
  let payload = null;

  try {
    payload = event.data ? event.data.json() : null;
  } catch (error) {
    console.warn("EduAlly SW: invalid push payload.", error);
  }

  const title = payload?.title || "EduAlly notification";

  const body = payload?.body || "You have a new announcement.";

  const tag = payload?.tag || "edually-announcement";

  const targetUrl = payload?.url || "/account/announcements/";

  const icon = payload?.icon || "/static/icons/icon-192x192.png";

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      tag,
      icon,
      data: {
        url: targetUrl,
      },
    }),
  );
});

/* ==================================================================
 * 13. NOTIFICATION CLICK
 * ================================================================== */

self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const targetUrl = event.notification.data?.url || "/account/announcements/";

  event.waitUntil(
    clients
      .matchAll({
        type: "window",
        includeUncontrolled: true,
      })
      .then((clientList) => {
        /*
         * Reuse an existing EduAlly tab when possible.
         */
        for (const client of clientList) {
          if (
            client.url.startsWith(self.location.origin) &&
            "focus" in client
          ) {
            return client.focus().then(() => client.navigate(targetUrl));
          }
        }

        /*
         * Otherwise open EduAlly in a new window.
         */
        return clients.openWindow(targetUrl);
      }),
  );
});

/* ==================================================================
 * 14. CONTROLLED SERVICE WORKER UPDATE
 *
 * Your webpage can send:
 *
 * navigator.serviceWorker.controller.postMessage({
 *     type: "SKIP_WAITING"
 * });
 *
 * when it is ready to activate a new worker.
 * ================================================================== */

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});
