import React, { useState, useRef, useCallback, useMemo } from "react";
import { MapContainer, TileLayer, Marker, useMapEvents } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./MapPicker.css";

// Get API URL from environment or use default
const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

// Whether the interactive map picker is enabled. Defaults to ON; set
// REACT_APP_ENABLE_MAP_PICKER=false to hide it for production deployments
// (pair with the backend's MAP_PICKER_ENABLED=false).
export const MAP_PICKER_ENABLED =
  (process.env.REACT_APP_ENABLE_MAP_PICKER ?? "true").toLowerCase() !== "false";

// Default view: roughly centred on India (the project's primary audience).
const DEFAULT_CENTER = [20.5937, 78.9629];
const DEFAULT_ZOOM = 4;
const PICKED_ZOOM = 9;

// CRA/webpack breaks Leaflet's default marker image paths; point them at the
// CDN-free copies bundled inside the leaflet package instead.
const markerIcon = L.icon({
  iconUrl: require("leaflet/dist/images/marker-icon.png"),
  iconRetinaUrl: require("leaflet/dist/images/marker-icon-2x.png"),
  shadowUrl: require("leaflet/dist/images/marker-shadow.png"),
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

// Re-centres the map imperatively when a coordinate is set from outside the map
// (e.g. the "use my location" button) without remounting the MapContainer.
function ClickCapture({ onPick }) {
  useMapEvents({
    click(e) {
      onPick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

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
    latitude != null && longitude != null
      ? [Number(latitude), Number(longitude)]
      : null,
  );
  const mapRef = useRef(null);
  const reverseTimer = useRef(null);

  const center = useMemo(
    () => marker || DEFAULT_CENTER,
    [marker],
  );

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
    [onLocationSelect],
  );

  // Move the pin and (debounced) resolve its place name + timezone. Debouncing
  // keeps us well under Nominatim's 1 req/sec policy during a drag.
  const pick = useCallback(
    (lat, lng) => {
      const rl = Math.round(lat * 1e6) / 1e6;
      const rg = Math.round(lng * 1e6) / 1e6;
      setMarker([rl, rg]);
      if (reverseTimer.current) clearTimeout(reverseTimer.current);
      reverseTimer.current = setTimeout(() => reverseGeocode(rl, rg), 600);
    },
    [reverseGeocode],
  );

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
      { enableHighAccuracy: false, timeout: 10000 },
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
            <button
              type="button"
              className="map-picker-locate"
              onClick={handleUseMyLocation}
            >
              📍 Use my location
            </button>
            <span className="map-picker-hint">
              Click the map or drag the pin to set the birthplace.
            </span>
          </div>

          <div className="map-picker-canvas">
            <MapContainer
              center={center}
              zoom={marker ? PICKED_ZOOM : DEFAULT_ZOOM}
              scrollWheelZoom
              style={{ height: "320px", width: "100%" }}
              ref={mapRef}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <ClickCapture onPick={pick} />
              {marker && (
                <Marker
                  position={marker}
                  icon={markerIcon}
                  draggable
                  eventHandlers={{
                    dragend: (e) => {
                      const { lat, lng } = e.target.getLatLng();
                      pick(lat, lng);
                    },
                  }}
                />
              )}
            </MapContainer>
          </div>

          {resolving && (
            <div className="map-picker-status">Resolving location…</div>
          )}
          {error && <div className="map-picker-error">⚠️ {error}</div>}
        </div>
      )}
    </div>
  );
};

export default MapPicker;
