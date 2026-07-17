import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { MapPin } from "lucide-react";
import { useCurrentLocation } from "../contexts/LocationContext";
import { useProfile } from "../contexts/ProfileContext";
import {
  detectOffsetHours,
  detectZone,
  dismissZone,
  locationPrompt,
  zoneLabel,
} from "../config/currentLocation";
import "../styles/LocationPrompt.css";

/**
 * "You seem to be on Central Time (UTC−5) — Use this timezone / Ignore for now."
 *
 * Detect, then **confirm**. This suggests; the user's click is what sets
 * anything. Adopting the browser's zone silently would mean a fortnight abroad
 * quietly moves someone's digest and rewrites their panchanga with no visible
 * cause — travelling is ordinary, while emigrating is not. See
 * config/currentLocation.js for when it chooses to speak at all.
 *
 * **It speaks in timezones, never cities** (owner: "it should say which timezone
 * I'm in, not the city — the user would be confused"). Naming the city would
 * state as fact the one thing this flow doesn't know: the zone's city defines
 * the zone, but someone in Milwaukee is also America/Chicago, so "I'm in
 * Chicago" could simply be false. The timezone is what's known exactly, and what
 * everything about "now" runs on. A city still gets geocoded underneath — the
 * store needs coordinates — but it's the server's business, verified there, and
 * refinable in Settings → Location. It is never claimed to the user as their
 * whereabouts.
 *
 * **Confirming is one click, not a trip to Settings** (owner: detecting the zone
 * and then asking you to type its name is silly). If the server can't confirm
 * the zone's city, we fall back to Settings rather than store a guess.
 */
export const LocationPrompt = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { location, loaded, saveLocationFromZone } = useCurrentLocation();
  const { selectedProfile } = useProfile();
  const [hidden, setHidden] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);

  // Wait for the server's answer: prompting before it arrives would ask users
  // who already have a location set.
  if (!loaded || hidden) return null;

  const zone = detectZone();
  const offset = detectOffsetHours();
  const prompt = locationPrompt({
    location,
    birthOffset: Number(selectedProfile?.birth_details?.timezone),
    zone,
    offset,
  });

  // Confirmation after a successful set — the banner's own disappearance is too
  // quiet to read as "saved".
  if (done) {
    return (
      <div className="location-prompt location-prompt--done" role="status">
        <MapPin size={18} className="location-prompt-icon" />
        <p className="location-prompt-text">
          {/* The timezone, not the stored place. Naming the place would both
              claim a city the user may not be in and, since Nominatim returns a
              full postal address, be a mouthful. Settings shows the place. */}
          {t("location.prompt.done", {
            zone: zoneLabel(done.timezone, done.utc_offset, i18n.language),
          })}
        </p>
      </div>
    );
  }

  if (!prompt) return null;
  const label = zoneLabel(prompt.zone, offset, i18n.language);

  const accept = async () => {
    setBusy(true);
    try {
      setDone(await saveLocationFromZone(prompt.zone));
    } catch {
      // Couldn't confirm the zone's city — ask rather than guess.
      navigate("/settings?tab=location");
    } finally {
      setBusy(false);
    }
  };

  const ignore = () => {
    dismissZone(zone);
    setHidden(true);
  };

  return (
    <div className="location-prompt" role="status">
      <MapPin size={18} className="location-prompt-icon" />
      <p className="location-prompt-text">
        {t(prompt.kind === "moved" ? "location.prompt.moved" : "location.prompt.unset", {
          zone: label,
        })}
      </p>
      <div className="location-prompt-actions">
        <button type="button" className="control-btn" onClick={accept} disabled={busy}>
          {busy ? t("location.prompt.setting") : t("location.prompt.accept")}
        </button>
        <button
          type="button"
          className="control-btn control-btn--ghost"
          onClick={ignore}
          disabled={busy}
        >
          {t("location.prompt.ignore")}
        </button>
      </div>
    </div>
  );
};
