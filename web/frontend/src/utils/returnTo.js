/**
 * Where the profile picker sends you back to.
 *
 * "Change chart" used to drop everyone on the dashboard, whichever page they
 * were reading — the same for the redirect a chart page does when no profile is
 * selected yet. These two helpers carry the page you left in the navigation
 * state so ProfileSelectionPage can return you to it once a chart is picked.
 */

/** Navigate options that remember the page currently on screen. */
export const returnHere = () => {
  const params = new URLSearchParams(window.location.search);
  // ?profile=<id> is the digest emails' deep link, and ProfileContext acts on it
  // at startup: carrying it back would undo the chart just picked on a reload.
  params.delete("profile");
  const query = params.toString();
  return {
    state: { returnTo: window.location.pathname + (query ? `?${query}` : "") },
  };
};

/** Read that back, ignoring anything that isn't an in-app path. */
export const returnTarget = (state, fallback = "/dashboard") => {
  const to = state?.returnTo;
  if (typeof to !== "string") return fallback;
  // In-app paths only ("//host" is another origin), and never the picker itself.
  if (!to.startsWith("/") || to.startsWith("//")) return fallback;
  if (to.startsWith("/profile-selection")) return fallback;
  return to;
};
