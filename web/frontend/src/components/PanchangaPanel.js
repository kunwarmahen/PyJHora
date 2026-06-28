import React, { useState, useEffect, useCallback } from "react";
import { Sun, Sunrise, Sunset } from "lucide-react";
import { astrologyService } from "../services/api";

/**
 * Daily almanac (Panchanga) for a location. Defaults to today; a date picker
 * lets the user check any day. Self-contained: fetches independently so a
 * failure here never blanks the surrounding page.
 */
export const PanchangaPanel = ({ place, latitude, longitude, timezone }) => {
  const today = new Date().toISOString().split("T")[0];
  const [date, setDate] = useState(today);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    astrologyService
      .getPanchanga({ place, latitude, longitude, timezone, date })
      .then((r) => setData(r.data))
      .catch(() => setError("Panchanga unavailable for this place/date."))
      .finally(() => setLoading(false));
  }, [place, latitude, longitude, timezone, date]);

  useEffect(() => {
    load();
  }, [load]);

  const limbs = data && [
    { label: "Tithi", value: data.tithi?.name, ends: data.tithi?.ends },
    { label: "Vaara", value: data.vaara?.name },
    { label: "Nakshatra", value: data.nakshatra?.name, ends: data.nakshatra?.ends,
      sub: data.nakshatra?.pada ? `Pada ${data.nakshatra.pada}` : null },
    { label: "Yoga", value: data.yoga?.name, ends: data.yoga?.ends },
    { label: "Karana", value: data.karana?.name, ends: data.karana?.ends },
  ];

  const range = (p) => (p && p.start ? `${p.start} – ${p.end}` : "—");

  return (
    <div className="panchanga-panel">
      <div className="panchanga-header">
        <h3>
          <Sun size={24} style={{ color: "var(--saffron)" }} />
          Panchanga
        </h3>
        <input
          type="date"
          className="panchanga-date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          aria-label="Almanac date"
        />
      </div>

      {loading && <div className="panchanga-status">Loading almanac…</div>}
      {error && !loading && <div className="panchanga-status">{error}</div>}

      {data && !loading && !error && (
        <>
          <div className="panchanga-limbs">
            {limbs.map((l) => (
              <div key={l.label} className="panchanga-limb">
                <span className="panchanga-limb-label">{l.label}</span>
                <span className="panchanga-limb-value">{l.value || "—"}</span>
                {l.sub && <span className="panchanga-limb-sub">{l.sub}</span>}
                {l.ends && <span className="panchanga-limb-sub">until {l.ends}</span>}
              </div>
            ))}
          </div>

          <div className="panchanga-suntimes">
            <span><Sunrise size={16} /> Sunrise {data.sunrise}</span>
            <span><Sunset size={16} /> Sunset {data.sunset}</span>
          </div>

          <div className="panchanga-periods">
            <div className="panchanga-period inauspicious">
              <span className="panchanga-period-label">Rahu Kalam</span>
              <span className="panchanga-period-time">{range(data.rahu_kalam)}</span>
            </div>
            <div className="panchanga-period inauspicious">
              <span className="panchanga-period-label">Yamaganda</span>
              <span className="panchanga-period-time">{range(data.yamaganda)}</span>
            </div>
            <div className="panchanga-period inauspicious">
              <span className="panchanga-period-label">Gulika Kalam</span>
              <span className="panchanga-period-time">{range(data.gulika)}</span>
            </div>
            <div className="panchanga-period auspicious">
              <span className="panchanga-period-label">Abhijit Muhurta</span>
              <span className="panchanga-period-time">{range(data.abhijit)}</span>
            </div>
          </div>

          {data.durmuhurtam && data.durmuhurtam.length > 0 && (
            <div className="panchanga-durmuhurtam">
              <span className="panchanga-period-label">Durmuhurtam</span>
              <span>
                {data.durmuhurtam.map((d, i) => (
                  <span key={i} className="panchanga-durm-slot">
                    {d.start} – {d.end}
                  </span>
                ))}
              </span>
            </div>
          )}
        </>
      )}
    </div>
  );
};
