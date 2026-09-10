import React, { Suspense, lazy, useState, useRef, useCallback, useMemo, useEffect } from "react";
import "./MapPicker.css";
import { API_URL } from "../services/api";

// Leaflet lives behind this boundary, not in the initial bundle (§68.4). The
// map is collapsed until "Pick on map" is pressed, so the chunk is fetched at
// the moment it is first needed and cached for the rest of the session.
const MapCanvas = lazy(() => import("./MapCanvas"));

// Whether the interactive map picker is enabled. Defaults to ON; set
// REACT_APP_ENABLE_MAP_PICKER=false to hide it for production deployments
// (pair with the backend's MAP_PICKER_ENABLED=false).
export const MAP_PICKER_ENABLED =
  (process.env.REACT_APP_ENABLE_MAP_PICKER ?? "true").toLowerCase() !== "false";

// Default view: roughly centred on India (the project's primary audience).
const DEFAULT_CENTER = [20.5937, 78.9629];
const DEFAULT_ZOOM = 4;
const PICKED_ZOOM = 9;

/**
 * MapPicker
 *
 * A free, key-less location picker using Leaflet + OpenStreetMap tiles. The user
 * clicks or drags the pin (or uses their browser location); coordinates are
 * captured client-side and a backend reverse-geocode call fills in the place
 * name + timezone. Calls onLocationSelect({ place, latitude, longitude, timezone }).
 */
const MapPicker = ({ onLocationSelect, latitude, longitude }) => {
  const [open, setOpen] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [error, setError] = useState("");
  const [marker, setMarker] = useState(
    latitude != null && longitude != null ? [Number(latitude), Number(longitude)] : null
  );
  const mapRef = useRef(null);
  const reverseTimer = useRef(null);
  // Mirror of `marker` so the prop-sync effect can compare against the latest
  // pin without re-running every time the pin moves.
  const markerRef = useRef(marker);

  const center = useMemo(() => marker || DEFAULT_CENTER, [marker]);

  const reverseGeocode = useCallback(
    (lat, lng) => {
      setResolving(true);
      setError("");
      fetch(`${API_URL}/api/location/reverse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ latitude: lat, longitude: lng }),
      })
        .then((r) => r.json())
        .then((data) => {
          if (data.success && onLocationSelect) {
            onLocationSelect({
              place: data.place,
              latitude: data.latitude,
              longitude: data.longitude,
              timezone: data.timezone,
            });
          } else if (!data.success) {
            setError(data.message || "Could not resolve that point.");
          }
        })
        .catch(() => setError("Failed to resolve location. Please try again."))
        .finally(() => setResolving(false));
    },
    [onLocationSelect]
  );

  // Move the pin and (debounced) resolve its place name + timezone. Debouncing
  // keeps us well under Nominatim's 1 req/sec policy during a drag.
  const pick = useCallback(
    (lat, lng) => {
      const rl = Math.round(lat * 1e6) / 1e6;
      const rg = Math.round(lng * 1e6) / 1e6;
      markerRef.current = [rl, rg];
      setMarker([rl, rg]);
      if (reverseTimer.current) clearTimeout(reverseTimer.current);
      reverseTimer.current = setTimeout(() => reverseGeocode(rl, rg), 600);
    },
    [reverseGeocode]
  );

  // Keep the pin in sync with coordinates set elsewhere (the text search, or
  // editing an existing profile): drop/move the pin and recentre. The epsilon
  // guard skips the echo of our own pick() — so dragging the pin never fights
  // the map back to where it started.
  useEffect(() => {
    if (latitude == null || longitude == null) return;
    const lat = Number(latitude);
    const lng = Number(longitude);
    if (Number.isNaN(lat) || Number.isNaN(lng)) return;
    const prev = markerRef.current;
    if (prev && Math.abs(prev[0] - lat) < 1e-6 && Math.abs(prev[1] - lng) < 1e-6) {
      return;
    }
    markerRef.current = [lat, lng];
    setMarker([lat, lng]);
    if (mapRef.current) mapRef.current.setView([lat, lng], PICKED_ZOOM);
  }, [latitude, longitude]);

  const handleUseMyLocation = () => {
    if (!navigator.geolocation) {
      setError("Your browser does not support location access.");
      return;
    }
    setError("");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude: lat, longitude: lng } = pos.coords;
        if (mapRef.current) mapRef.current.setView([lat, lng], PICKED_ZOOM);
        pick(lat, lng);
      },
      () => setError("Could not get your location (permission denied?)."),
      { enableHighAccuracy: false, timeout: 10000 }
    );
  };

  if (!MAP_PICKER_ENABLED) return null;

  return (
    <div className="map-picker">
      <button
        type="button"
        className="map-picker-toggle"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        🗺️ {open ? "Hide map" : "Pick on map"}
      </button>

      {open && (
        <div className="map-picker-body">
          <div className="map-picker-actions">
            <button type="button" className="map-picker-locate" onClick={handleUseMyLocation}>
              📍 Use my location
            </button>
            <span className="map-picker-hint">
              Click the map or drag the pin to set the birthplace.
            </span>
          </div>

          <div className="map-picker-canvas">
            <Suspense fallback={<div className="map-picker-status">Loading map…</div>}>
              <MapCanvas
                center={center}
                zoom={marker ? PICKED_ZOOM : DEFAULT_ZOOM}
                marker={marker}
                onPick={pick}
                mapRef={mapRef}
              />
            </Suspense>
          </div>

          {resolving && <div className="map-picker-status">Resolving location…</div>}
          {error && <div className="map-picker-error">⚠️ {error}</div>}
        </div>
      )}
    </div>
  );
};

export default MapPicker;
