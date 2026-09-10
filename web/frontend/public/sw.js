/* Minimal, conservative service worker for Jyotir AI.
 * Goal: make the app installable + give a basic offline shell, WITHOUT caching
 * API responses (which are per-user and auth-scoped).
 *
 * Strategy:
 *   - navigations: network-first, fall back to the cached app shell when offline
 *   - same-origin static GETs: stale-while-revalidate
 *   - anything under /api or cross-origin: passthrough (never cached)
 */
// Bumping this name drops the previous shell on activate — do it whenever the
// cached shell could be stale in a way that matters (see the navigation note).
const CACHE = "jyotir-ai-v3";
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

  // App navigations: network-first, falling back to the cached shell offline.
  //
  // `cache: "reload"` is load-bearing. index.html is the only thing that names
  // the current hashed bundles, and a plain fetch() may be answered from the
  // browser's HTTP cache — which pins the tab to a previous build's JavaScript,
  // across new tabs, for as long as heuristic freshness lasts. An old bundle
  // against the current API does not error; it renders something plausible and
  // wrong (todo.md §66). So always revalidate the shell against the network.
  //
  // It has to be re-fetched **by URL**, not by passing the navigation Request
  // with an init: `fetch(request, { cache: "reload" })` on a request whose mode
  // is "navigate" is a synchronous TypeError, and it threw before
  // `event.respondWith` was ever called — so this whole branch silently did
  // nothing. Online the browser just did the navigation itself (which is why
  // nobody saw it, and why the §66 revalidation above was never actually in
  // force); offline the navigation simply failed, which is why the app could
  // not be opened or reloaded without a network even though its shell was
  // sitting in the cache. Found while splitting the routes (§68.4), which is
  // what made the offline path worth trusting.
  if (request.mode === "navigate") {
    event.respondWith(
      (async () => {
        try {
          return await fetch(request.url, { cache: "reload", credentials: "same-origin" });
        } catch (e) {
          /* offline, or the server is down — fall through */
        }
        try {
          return await fetch(request);
        } catch (e) {
          /* still nothing; serve the shell we cached at install */
        }
        // "./" before "./index.html": depending on the static server, the
        // shell may have been cached as the *result of a redirect*
        // (`serve`, for one, sends /index.html -> /), and the browser refuses
        // a redirected response for a navigation — the request fails as if
        // nothing had been cached at all. Re-wrap it when that is what we
        // have, so the navigation always gets a plain 200.
        const shell = (await caches.match("./")) || (await caches.match("./index.html"));
        if (!shell) return Response.error();
        if (!shell.redirected) return shell;
        return new Response(shell.body, {
          status: 200,
          statusText: "OK",
          headers: shell.headers,
        });
      })()
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
  const title = data.title || "Jyotir AI";
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
