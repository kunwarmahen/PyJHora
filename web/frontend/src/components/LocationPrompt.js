import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { MapPin, X } from "lucide-react";
import { useCurrentLocation } from "../contexts/LocationContext";
import { useProfile } from "../contexts/ProfileContext";
import {
  detectOffsetHours,
  detectZone,
  dismissZone,
  locationPrompt,
} from "../config/currentLocation";
import "../styles/LocationPrompt.css";

/**
 * "Looks like you're in Chicago — is that where you are now?"
 *
 * Detect, then **confirm**. This suggests; it never sets anything. Adopting the
 * browser's zone silently would mean a fortnight abroad quietly moves someone's
 * digest and rewrites their panchanga with no visible cause — and travelling is
 * ordinary, while emigrating is not. See config/currentLocation.js for when it
 * chooses to speak at all.
 *
 * "Set my location" goes to Settings rather than resolving here on purpose: the
 * browser knows a zone but not *where*, and a stored location needs real
 * coordinates (place name, lat/lon) for the astrology to mean anything. Only the
 * user can supply their city; inventing a representative point for a zone would
 * be a fabrication that later reads as fact.
 */
export const LocationPrompt = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { location, loaded } = useCurrentLocation();
  const { selectedProfile } = useProfile();
  const [hidden, setHidden] = useState(false);

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
  if (!prompt) return null;

  const dismiss = () => {
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
        <button
          type="button"
          className="control-btn"
          onClick={() => navigate("/settings?tab=location")}
        >
          {t("location.prompt.set")}
        </button>
        <button
          type="button"
          className="location-prompt-dismiss"
          onClick={dismiss}
          aria-label={t("location.prompt.dismiss")}
          title={t("location.prompt.dismiss")}
        >
          <X size={16} />
        </button>
      </div>
    </div>
  );
};
