import React from "react";
import { withTranslation } from "react-i18next";
import { CloudOff, RefreshCw } from "lucide-react";
import "../styles/Shared.css";

// Only reload for a genuine failed-to-fetch-a-chunk error, and at most once per
// this many ms, so a page that is broken for some other reason cannot put the
// tab into a reload loop.
const RELOAD_KEY = "jyotir:chunk-reload";
const RELOAD_COOLDOWN_MS = 30000;

const isChunkError = (error) =>
  error?.name === "ChunkLoadError" ||
  /Loading chunk|Loading CSS chunk|dynamically imported module|Failed to fetch/i.test(
    error?.message || ""
  );

/**
 * The failure mode that route-level code splitting introduces (§68.4).
 *
 * When pages rode in the initial bundle, a page either rendered or the whole
 * app had failed to load. Now each one is fetched on navigation, so it can fail
 * on its own — two ways, both of them real:
 *
 *   - **offline**, on a page this browser has never opened (`public/sw.js`
 *     caches static assets stale-while-revalidate, so it holds the chunks you
 *     have actually fetched and no others);
 *   - **after a deploy**, in a tab that is still running the previous build and
 *     asks for a chunk whose hashed name no longer exists.
 *
 * The second case is fixed by reloading — index.html is always revalidated
 * against the network (see sw.js), so a reload lands on the current build — and
 * that is done here automatically, once. The first case cannot be fixed by
 * retrying, so it says what happened instead of showing a blank frame.
 */
class RouteErrorBoundaryInner extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error) {
    if (!isChunkError(error) || navigator.onLine === false) return;
    let last = 0;
    try {
      last = Number(sessionStorage.getItem(RELOAD_KEY)) || 0;
    } catch {
      // private mode: skip the auto-reload rather than risk a loop
      return;
    }
    if (Date.now() - last < RELOAD_COOLDOWN_MS) return;
    try {
      sessionStorage.setItem(RELOAD_KEY, String(Date.now()));
    } catch {
      return;
    }
    window.location.reload();
  }

  render() {
    const { error } = this.state;
    const { t, children } = this.props;
    if (!error) return children;

    const offline = navigator.onLine === false;
    return (
      <div className="loading-state" role="alert">
        {offline ? <CloudOff size={28} aria-hidden="true" /> : null}
        <p>
          <strong>{t("route.failedTitle")}</strong>
        </p>
        <p>{offline ? t("route.offlineBody") : t("route.onlineBody")}</p>
        <button
          type="button"
          className="ui-btn ui-btn--secondary"
          onClick={() => window.location.reload()}
        >
          <RefreshCw size={16} aria-hidden="true" /> {t("route.retry")}
        </button>
      </div>
    );
  }
}

export const RouteErrorBoundary = withTranslation()(RouteErrorBoundaryInner);
export default RouteErrorBoundary;
