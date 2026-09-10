import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { CloudOff } from "lucide-react";
import "../styles/OfflineBanner.css";

/**
 * "You're offline — this is a saved copy" (§68.8).
 *
 * The app shell has always worked offline; every number in it is computed on
 * the server, so it used to open empty. services/offlineCache.js now replays
 * the last successful response for any deterministic computation, which means
 * the pages fill in — and that is exactly why this banner exists: figures that
 * look live but are not must say so.
 *
 * It appears when the browser reports itself offline, and also when a request
 * has actually been served from the cache (the browser can be "online" behind a
 * captive portal or a dead backend), and names when the copy was saved.
 */
export const OfflineBanner = () => {
  const { t } = useTranslation();
  const [offline, setOffline] = useState(
    typeof navigator !== "undefined" ? navigator.onLine === false : false
  );
  const [savedAt, setSavedAt] = useState(null);

  useEffect(() => {
    const goOffline = () => setOffline(true);
    const goOnline = () => {
      setOffline(false);
      setSavedAt(null);
    };
    const served = (e) => {
      setOffline(true);
      setSavedAt(e.detail?.savedAt || null);
    };
    window.addEventListener("offline", goOffline);
    window.addEventListener("online", goOnline);
    window.addEventListener("jyotir:served-offline", served);
    return () => {
      window.removeEventListener("offline", goOffline);
      window.removeEventListener("online", goOnline);
      window.removeEventListener("jyotir:served-offline", served);
    };
  }, []);

  if (!offline) return null;

  const when = savedAt ? new Date(savedAt).toLocaleString() : null;

  return (
    <div className="offline-banner" role="status" aria-live="polite">
      <CloudOff size={16} className="offline-banner__icon" aria-hidden="true" />
      <span>
        {t("offline.title")} {when ? t("offline.savedAt", { when }) : t("offline.noCopy")}
      </span>
    </div>
  );
};

export default OfflineBanner;
