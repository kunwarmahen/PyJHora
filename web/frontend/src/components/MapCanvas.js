import React from "react";
import { MapContainer, TileLayer, Marker, useMapEvents } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

/**
 * The Leaflet half of MapPicker, split out so it can be `React.lazy`-loaded
 * (§68.4).
 *
 * `leaflet` + `react-leaflet` + `leaflet.css` are ~45 KB gzipped and were
 * riding in the initial bundle for every visitor, to serve one collapsed
 * dialog on the profile form. Nothing here is imported until someone actually
 * presses "Pick on map" — which is also when the OpenStreetMap tiles start
 * downloading, so the two costs now arrive together and only on demand.
 *
 * Everything stateful stays in MapPicker; this file owns only the map itself.
 */

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

// Turns a click anywhere on the map into a pick.
function ClickCapture({ onPick }) {
  useMapEvents({
    click(e) {
      onPick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

const MapCanvas = ({ center, zoom, marker, onPick, mapRef }) => (
  <MapContainer
    center={center}
    zoom={zoom}
    scrollWheelZoom
    style={{ height: "320px", width: "100%" }}
    ref={mapRef}
  >
    <TileLayer
      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
    />
    <ClickCapture onPick={onPick} />
    {marker && (
      <Marker
        position={marker}
        icon={markerIcon}
        draggable
        eventHandlers={{
          dragend: (e) => {
            const { lat, lng } = e.target.getLatLng();
            onPick(lat, lng);
          },
        }}
      />
    )}
  </MapContainer>
);

export default MapCanvas;
