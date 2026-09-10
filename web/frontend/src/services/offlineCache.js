/* Offline readability (§68.8).
 *
 * `public/sw.js` caches the app shell, so opening the app on a plane gave you a
 * working shell with nothing in it: every computation is server-side. This is
 * the other half — the responses themselves, kept in IndexedDB and served back
 * when the network is gone.
 *
 * Why not the service worker: the core payloads (birth chart, vargas, dashas,
 * yogas) are **POSTs** carrying the birth details in the body. The Cache API
 * keys on the request URL and refuses to store a POST at all, so a SW cannot
 * see the difference between two profiles' charts. An app-level cache can, by
 * hashing the body into the key.
 *
 * What is cached: deterministic computations only — the same birth details give
 * the same answer, so a saved copy is never misleading, just possibly from an
 * older ayanamsa setting. AI readings are excluded (expensive, non-deterministic
 * and already kept in the unified history, §17), as are job/stream endpoints.
 * The rule is a predicate rather than a list of paths so a new endpoint is
 * covered the day it ships instead of being forgotten.
 *
 * Privacy: entries are namespaced by the signed-in user and dropped wholesale on
 * logout — this is a browser someone else may use.
 */
const DB_NAME = "jyotir-ai-offline";
const STORE = "responses";
const DB_VERSION = 1;
// Enough for a couple of profiles' worth of pages; evicted oldest-first.
const MAX_ENTRIES = 250;

let dbPromise = null;

const openDb = () => {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("no indexedDB"));
      return;
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: "key" });
        store.createIndex("savedAt", "savedAt");
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  }).catch((err) => {
    // Private windows and locked-down browsers throw here. Stay off rather than
    // retrying on every request for the rest of the session.
    dbPromise = Promise.reject(err);
    throw err;
  });
  return dbPromise;
};

const tx = async (mode, fn) => {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE, mode);
    const result = fn(t.objectStore(STORE));
    t.oncomplete = () => resolve(result && result.__value);
    t.onerror = () => reject(t.error);
    t.onabort = () => reject(t.error);
  });
};

/* Endpoints worth keeping offline: a deterministic computation, not an AI
 * reading, a background job or a stream. */
const NEVER_CACHE = /-analysis$|\/ask$|\/predict$|\/life-report\/|\/rectify|\/stream/;

export const isCacheable = (method, url = "") => {
  if ((method || "").toLowerCase() !== "post" && (method || "").toLowerCase() !== "get") {
    return false;
  }
  const path = url.split("?")[0];
  if (NEVER_CACHE.test(path)) return false;
  return (
    path.startsWith("/api/astrology/") ||
    path === "/api/user/charts" ||
    path === "/api/user/preferences" ||
    path === "/api/user/location"
  );
};

/* A stable string for a value, so that {a:1,b:2} and {b:2,a:1} share a key. */
const stable = (value) => {
  if (value === null || typeof value !== "object") return JSON.stringify(value) ?? "null";
  if (Array.isArray(value)) return `[${value.map(stable).join(",")}]`;
  return `{${Object.keys(value)
    .sort()
    .map((k) => `${JSON.stringify(k)}:${stable(value[k])}`)
    .join(",")}}`;
};

export const cacheKey = (config = {}, owner = "anon") => {
  const method = (config.method || "get").toLowerCase();
  const url = (config.url || "").split("?")[0];
  let body = config.data;
  if (typeof body === "string") {
    try {
      body = JSON.parse(body);
    } catch (e) {
      /* not JSON — hash it as the string it is */
    }
  }
  return [owner, method, url, stable(config.params ?? null), stable(body ?? null)].join("|");
};

export const put = async (key, data) => {
  try {
    await tx("readwrite", (store) => {
      store.put({ key, data, savedAt: Date.now() });
    });
    await evict();
  } catch (e) {
    /* Storage full or unavailable — offline reading is a bonus, never a failure. */
  }
};

export const get = async (key) => {
  try {
    const db = await openDb();
    return await new Promise((resolve) => {
      const req = db.transaction(STORE, "readonly").objectStore(STORE).get(key);
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => resolve(null);
    });
  } catch (e) {
    return null;
  }
};

/* Oldest-first eviction, so the cache cannot grow without bound. */
const evict = async () => {
  try {
    const db = await openDb();
    const store = db.transaction(STORE, "readwrite").objectStore(STORE);
    const countReq = store.count();
    countReq.onsuccess = () => {
      const excess = countReq.result - MAX_ENTRIES;
      if (excess <= 0) return;
      let removed = 0;
      const cursorReq = store.index("savedAt").openCursor();
      cursorReq.onsuccess = () => {
        const cursor = cursorReq.result;
        if (!cursor || removed >= excess) return;
        cursor.delete();
        removed += 1;
        cursor.continue();
      };
    };
  } catch (e) {
    /* nothing to do */
  }
};

/** Drop everything. Called on logout — a shared browser must not keep a
 *  previous user's charts readable. */
export const clearAll = async () => {
  try {
    await tx("readwrite", (store) => {
      store.clear();
    });
  } catch (e) {
    /* nothing to clear */
  }
};

export const __testing = { stable, NEVER_CACHE };
