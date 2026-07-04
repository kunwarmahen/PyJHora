/* Web Push (PWA notifications) helpers.
 *
 * Subscribes the browser's service worker to push using the server's VAPID
 * public key, and hands the subscription to the backend. All functions degrade
 * gracefully when push isn't supported or permission is denied.
 */
import { notificationsService } from "../services/api";

export const pushSupported = () =>
  typeof window !== "undefined" &&
  "serviceWorker" in navigator &&
  "PushManager" in window &&
  "Notification" in window;

/** Why this browser can't use push, or "" if it can.
 *
 * Browsers only expose Service Workers + the Push API in a *secure context*
 * (HTTPS, or http://localhost / 127.0.0.1). Served over plain HTTP on a LAN
 * hostname the APIs simply don't exist, so `pushSupported()` is false. We check
 * `isSecureContext` first so we can tell the user the actionable reason
 * ("insecure") apart from a genuinely old browser ("unsupported"). */
export const pushUnavailableReason = () => {
  if (typeof window === "undefined") return "unsupported";
  if ("isSecureContext" in window && !window.isSecureContext) return "insecure";
  if (!pushSupported()) return "unsupported";
  return "";
};

// VAPID public keys are base64url; the PushManager wants a Uint8Array.
const urlBase64ToUint8Array = (base64String) => {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(base64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) out[i] = raw.charCodeAt(i);
  return out;
};

async function getRegistration() {
  // The SW is registered in index.js (production). In dev it may not be, so
  // register on demand here so the toggle works when tested against a build.
  const existing = await navigator.serviceWorker.getRegistration();
  if (existing) return existing;
  return navigator.serviceWorker.register(`${process.env.PUBLIC_URL || ""}/sw.js`);
}

/** Subscribe to push and register the subscription with the backend.
 * Returns { ok: true } or { ok: false, reason }. */
export async function enablePush(vapidPublicKey) {
  if (!pushSupported()) return { ok: false, reason: "unsupported" };
  if (!vapidPublicKey) return { ok: false, reason: "no_vapid_key" };

  const permission = await Notification.requestPermission();
  if (permission !== "granted") return { ok: false, reason: "denied" };

  try {
    const reg = await getRegistration();
    await navigator.serviceWorker.ready;
    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
      });
    }
    await notificationsService.subscribePush(sub.toJSON());
    return { ok: true };
  } catch (e) {
    return { ok: false, reason: "error", error: e };
  }
}

/** Unsubscribe locally + on the server. */
export async function disablePush() {
  if (!pushSupported()) return { ok: false, reason: "unsupported" };
  try {
    const reg = await navigator.serviceWorker.getRegistration();
    const sub = reg && (await reg.pushManager.getSubscription());
    if (sub) {
      const endpoint = sub.endpoint;
      await sub.unsubscribe();
      try {
        await notificationsService.unsubscribePush(endpoint);
      } catch {
        /* server cleanup is best-effort */
      }
    }
    return { ok: true };
  } catch (e) {
    return { ok: false, reason: "error", error: e };
  }
}
