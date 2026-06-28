import React, { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles, Grid3x3, Compass, Gauge } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { DataField } from "../components/DataField";
import { AYANAMSAS, DEFAULT_AYANAMSA } from "../constants/jyotish";
import "../styles/Dashboard.css";

const RASI_ABBR = ["Ar", "Ta", "Ge", "Cn", "Le", "Vi", "Li", "Sc", "Sg", "Cp", "Aq", "Pi"];

// Map a Sarva Ashtakavarga bindu count (~25–40) to a saffron tint for a heatmap.
const savColor = (v) => {
  const lo = 18,
    hi = 40;
  const t = Math.max(0, Math.min(1, (v - lo) / (hi - lo)));
  const alpha = 0.12 + t * 0.6;
  return `rgba(255, 153, 51, ${alpha.toFixed(2)})`;
};

export const AdvancedPage = () => {
  const navigate = useNavigate();
  const { selectedProfile } = useProfile();

  const [ayanamsa, setAyanamsa] = useState(
    () => localStorage.getItem("ayanamsa") || DEFAULT_AYANAMSA
  );
  const [av, setAv] = useState(null);
  const [details, setDetails] = useState(null);
  const [shadbala, setShadbala] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const birthDetails = useMemo(
    () =>
      selectedProfile
        ? {
            name: selectedProfile.birth_details.name,
            dob: selectedProfile.birth_details.dob,
            tob: selectedProfile.birth_details.tob,
            place: selectedProfile.birth_details.place,
            latitude: parseFloat(selectedProfile.birth_details.latitude),
            longitude: parseFloat(selectedProfile.birth_details.longitude),
            timezone: parseFloat(selectedProfile.birth_details.timezone),
          }
        : null,
    [selectedProfile]
  );

  const changeAyanamsa = (value) => {
    setAyanamsa(value);
    localStorage.setItem("ayanamsa", value);
  };

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    // Each section loads independently so one failure won't blank the others.
    setLoading(true);
    setError("");
    setAv(null);
    setDetails(null);
    setShadbala(null);
    let cancelled = false;
    const done = { av: false, d: false, sb: false };
    const settle = () => {
      if (!cancelled && done.av && done.d && done.sb) setLoading(false);
    };
    astrologyService
      .getAshtakavarga(birthDetails, ayanamsa)
      .then((r) => !cancelled && setAv(r.data))
      .catch(() => {})
      .finally(() => {
        done.av = true;
        settle();
      });
    astrologyService
      .getChartDetails(birthDetails, ayanamsa)
      .then((r) => !cancelled && setDetails(r.data))
      .catch(() => {})
      .finally(() => {
        done.d = true;
        settle();
      });
    astrologyService
      .getShadbala(birthDetails, ayanamsa)
      .then((r) => !cancelled && setShadbala(r.data))
      .catch((e) => !cancelled && setError(e.response?.data?.detail || ""))
      .finally(() => {
        done.sb = true;
        settle();
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProfile, navigate, ayanamsa]);

  if (!selectedProfile) return null;

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Sparkles size={24} />}
        title="Advanced Details"
        subtitle="Ashtakavarga, Arudha, Karakas, Special Lagnas, Upagrahas & Shadbala"
        accent="gold"
      />

      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />

        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            marginBottom: "var(--space-lg)",
          }}
        >
          <label className="ayanamsa-select">
            <span>Ayanamsa</span>
            <select value={ayanamsa} onChange={(e) => changeAyanamsa(e.target.value)}>
              {AYANAMSAS.map((a) => (
                <option key={a.value} value={a.value}>
                  {a.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message="Computing advanced chart factors…" />
          </Card>
        ) : (
          <>
            {/* Ashtakavarga */}
            {av && (
              <Card title="Ashtakavarga" icon={<Grid3x3 size={24} />} accent="saffron">
                <p style={{ color: "var(--text-secondary)", marginBottom: "var(--space-md)" }}>
                  Sarva Ashtakavarga (total bindus per sign — higher is more supportive). Grand
                  total: <strong>{av.sarva_total}</strong>.
                </p>
                <div style={{ overflowX: "auto" }}>
                  <table className="adv-table">
                    <thead>
                      <tr>
                        <th>Contributor</th>
                        {RASI_ABBR.map((r) => (
                          <th key={r}>{r}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td style={{ fontWeight: 700 }}>Sarva (SAV)</td>
                        {av.sarva.map((v, i) => (
                          <td key={i} style={{ background: savColor(v), fontWeight: 700 }}>
                            {v}
                          </td>
                        ))}
                      </tr>
                      {Object.entries(av.bhinna).map(([planet, row]) => (
                        <tr key={planet}>
                          <td>{planet}</td>
                          {row.map((v, i) => (
                            <td key={i}>{v}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}

            {/* Advanced chart details */}
            {details && (
              <Card title="Chart Factors" icon={<Compass size={24} />} accent="indigo">
                <h4 className="adv-subhead">Arudha Padas</h4>
                <div className="ui-field-grid">
                  {details.arudha_padas.map((a) => (
                    <DataField key={a.bhava} label={a.label} value={a.sign_name} />
                  ))}
                </div>

                <h4 className="adv-subhead">Chara Karakas (Jaimini)</h4>
                <div className="ui-field-grid">
                  {details.chara_karakas.map((k) => (
                    <DataField key={k.karaka} label={k.karaka} value={k.planet} />
                  ))}
                </div>

                <h4 className="adv-subhead">Special Lagnas</h4>
                <div className="ui-field-grid">
                  {details.special_lagnas.map((s) => (
                    <DataField key={s.name} label={s.name} value={`${s.sign_name} ${s.degrees}°`} />
                  ))}
                </div>

                <h4 className="adv-subhead">Upagrahas (Sub-planets)</h4>
                <div className="ui-field-grid">
                  {details.upagrahas.map((u) => (
                    <DataField key={u.name} label={u.name} value={`${u.sign_name} ${u.degrees}°`} />
                  ))}
                </div>
              </Card>
            )}

            {/* Shadbala */}
            {shadbala && (
              <Card
                title="Shadbala (Planetary Strength)"
                icon={<Gauge size={24} />}
                accent="vermillion"
              >
                <p style={{ color: "var(--text-secondary)", marginBottom: "var(--space-md)" }}>
                  Six-fold strength in rupas. A planet is sufficiently strong when its total meets
                  the required rupas (ratio ≥ 1.0).
                </p>
                <div style={{ overflowX: "auto" }}>
                  <table className="adv-table">
                    <thead>
                      <tr>
                        <th>Planet</th>
                        <th>Sthana</th>
                        <th>Kaala</th>
                        <th>Dig</th>
                        <th>Cheshta</th>
                        <th>Naisargika</th>
                        <th>Drik</th>
                        <th>Total (rupa)</th>
                        <th>Required</th>
                        <th>Ratio</th>
                        <th>Rank</th>
                      </tr>
                    </thead>
                    <tbody>
                      {shadbala.planets.map((p) => (
                        <tr key={p.planet}>
                          <td style={{ fontWeight: 700 }}>{p.planet}</td>
                          <td>{p.sthana}</td>
                          <td>{p.kaala}</td>
                          <td>{p.dig}</td>
                          <td>{p.cheshta}</td>
                          <td>{p.naisargika}</td>
                          <td>{p.drik}</td>
                          <td style={{ fontWeight: 700 }}>{p.total_rupa}</td>
                          <td>{p.required_rupa}</td>
                          <td
                            style={{
                              fontWeight: 700,
                              color: p.sufficient ? "var(--saffron)" : "var(--vermillion)",
                            }}
                          >
                            {p.strength_ratio}
                          </td>
                          <td>{p.rank}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default AdvancedPage;
