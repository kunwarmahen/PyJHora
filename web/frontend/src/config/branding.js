// Central brand config. Both values are overridable at deploy time via CRA env
// vars (REACT_APP_*, baked in at build time) so the app can be white-labelled
// without touching source. When unset, we keep the default Jyotir AI branding.
//
//   REACT_APP_SITE_TITLE=Jyotirai
//   REACT_APP_SITE_TAGLINE=The AI-native Vedic Astrology Platform
export const SITE_TITLE = (process.env.REACT_APP_SITE_TITLE || "Jyotir AI").trim();

// Left blank by default so callers can fall back to their translated tagline
// (e.g. i18n "auth.tagline"). When set, this override wins everywhere.
export const SITE_TAGLINE = (process.env.REACT_APP_SITE_TAGLINE || "").trim();
