/* Minimal, conservative service worker for PyJHora.
 * Goal: make the app installable + give a basic offline shell, WITHOUT caching
 * API responses (which are per-user and auth-scoped).
 *
 * Strategy:
 *   - navigations: network-first, fall back to the cached app shell when offline
 *   - same-origin static GETs: stale-while-revalidate
 *   - anything under /api or cross-origin: passthrough (never cached)
 */
const CACHE = "pyjhora-v1";
const SHELL = ["./", "./index.html", "./manifest.json", "./icon-192.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  // Never touch API calls or cross-origin requests.
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api")) return;

  // App navigations: try network, fall back to cached shell offline.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match("./index.html"))
    );
    return;
  }

  // Static assets: stale-while-revalidate.
  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request)
        .then((resp) => {
          if (resp && resp.status === 200 && resp.type === "basic") {
            const copy = resp.clone();
            caches.open(CACHE).then((c) => c.put(request, copy));
          }
          return resp;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});

/* ── Web Push (daily digest notifications) ─────────────────────────────────
 * Payload shape sent by the backend: { title, body, url }. */
self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { body: event.data && event.data.text() };
  }
  const title = data.title || "PyJHora";
  const options = {
    body: data.body || "Your daily Vedic digest is ready.",
    icon: "./icon-192.png",
    badge: "./icon-192.png",
    data: { url: data.url || "/daily-digest" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "/daily-digest";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ("focus" in client) {
          client.navigate(target);
          return client.focus();
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(target);
    })
  );
});
