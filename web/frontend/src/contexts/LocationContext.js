import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { astrologyService } from "../services/api";
import { useAuth } from "./AuthContext";

/**
 * Where the user is **now** — one per account, server-stored, and nothing to do
 * with any birth profile.
 *
 * Server-stored rather than localStorage because the reader isn't the only thing
 * that needs it: the digest scheduler runs at 3am with no browser to ask. It's a
 * separate context from SettingsContext because it isn't a preference — it's
 * structured data with one authoritative copy on the server, where
 * SettingsContext's whole design is a localStorage cache mirrored upward.
 *
 * `location` is `{place, latitude, longitude, timezone, utc_offset}`, or null
 * for "not set" — which is not a broken state. It means "fall back to the birth
 * profile", the pre-§40 behaviour, still correct for anyone who lives where they
 * were born.
 */
const LocationContext = createContext(null);

export const useCurrentLocation = () => {
  const ctx = useContext(LocationContext);
  if (!ctx) throw new Error("useCurrentLocation must be used within a LocationProvider");
  return ctx;
};

export const LocationProvider = ({ children }) => {
  const { user } = useAuth();
  const [location, setLocation] = useState(null);
  // Distinguishes "not loaded yet" from "loaded, and there is none" — the
  // detect-and-confirm prompt must not fire on the former or it would ask every
  // user to set a location they may already have.
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!user) {
      setLocation(null);
      setLoaded(false);
      return undefined;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await astrologyService.getCurrentLocation();
        if (!cancelled) setLocation(res.data?.location || null);
      } catch {
        // Best-effort: every consumer already falls back to birth details.
      } finally {
        if (!cancelled) setLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user]);

  /** Save where the user is now. `timezone` is derived server-side from the
   *  coordinates when omitted — the picker only knows a float offset. */
  const saveLocation = useCallback(async ({ place, latitude, longitude, timezone }) => {
    const res = await astrologyService.putCurrentLocation({
      place,
      latitude,
      longitude,
      timezone,
    });
    const saved = res.data?.location || null;
    setLocation(saved);
    return saved;
  }, []);

  /** Set the location from the browser's zone alone, in one click. Throws if the
   *  server can't confirm the zone's city — callers fall back to asking. */
  const saveLocationFromZone = useCallback(async (zone) => {
    const res = await astrologyService.setCurrentLocationFromZone(zone);
    const saved = res.data?.location || null;
    setLocation(saved);
    return saved;
  }, []);

  const clearLocation = useCallback(async () => {
    await astrologyService.deleteCurrentLocation();
    setLocation(null);
  }, []);

  return (
    <LocationContext.Provider
      value={{ location, loaded, saveLocation, saveLocationFromZone, clearLocation }}
    >
      {children}
    </LocationContext.Provider>
  );
};
