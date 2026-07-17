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
  zoneCity,
} from "../config/currentLocation";
import "../styles/LocationPrompt.css";

/**
 * "Looks like you're in Chicago — I'm in Chicago / Ignore for now."
 *
 * Detect, then **confirm**. This suggests; the user's click is what sets
 * anything. Adopting the browser's zone silently would mean a fortnight abroad
 * quietly moves someone's digest and rewrites their panchanga with no visible
 * cause — travelling is ordinary, while emigrating is not. See
 * config/currentLocation.js for when it chooses to speak at all.
 *
 * **Confirming is one click, not a trip to Settings** (owner feedback: detecting
 * the zone and then asking you to type its name is silly). The server geocodes
 * the zone's representative city and *verifies* the result lands back in that
 * zone, so this is a real lookup with a check — not an invented position. Its
 * coordinates are metro-accurate: the zone's city defines the zone, but someone
 * in Milwaukee is also America/Chicago. That's exact for the timezone, which is
 * what "now" runs on; Settings → Location refines the place.
 *
 * If the server can't confirm the city, we fall back to Settings rather than
 * store a guess.
 */
export const LocationPrompt = () => {
  const { t } = useTranslation();
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
  const prompt = locationPrompt({
    location,
    birthOffset: Number(selectedProfile?.birth_details?.timezone),
    zone,
    offset: detectOffsetHours(),
  });

  // Confirmation after a successful set — the banner's own disappearance is too
  // quiet to read as "saved".
  if (done) {
    return (
      <div className="location-prompt location-prompt--done" role="status">
        <MapPin size={18} className="location-prompt-icon" />
        <p className="location-prompt-text">
          {/* The zone's city, not the stored place: Nominatim returns the full
              postal address ("Chicago, South Chicago Township, Cook County,
              Illinois, United States"), which is a mouthful to confirm back at
              someone. Settings shows the full thing. */}
          {t("location.prompt.done", {
            place: zoneCity(done.timezone) || done.place,
            zone: done.timezone,
          })}
        </p>
      </div>
    );
  }

  if (!prompt) return null;
  const city = zoneCity(prompt.zone) || prompt.zone;

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
          zone: prompt.zone,
        })}
      </p>
      <div className="location-prompt-actions">
        <button type="button" className="control-btn" onClick={accept} disabled={busy}>
          {busy ? t("location.prompt.setting") : t("location.prompt.accept", { city })}
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
