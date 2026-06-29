import React, { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { GitCompareArrows, Users } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { PageHeader } from "../components/PageHeader";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
import { DEFAULT_AYANAMSA } from "../constants/jyotish";
import "../styles/Dashboard.css";

const PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"];

const toBirthDetails = (p) => ({
  name: p.birth_details.name,
  dob: p.birth_details.dob,
  tob: p.birth_details.tob,
  place: p.birth_details.place,
  latitude: parseFloat(p.birth_details.latitude),
  longitude: parseFloat(p.birth_details.longitude),
  timezone: parseFloat(p.birth_details.timezone),
});

// One "Lagna / Moon / Sun / planet → sign" row, comparing the two charts.
const compareRows = (a, b) => {
  const rows = [
    { label: "Lagna", a: a?.lagna?.sign_name, b: b?.lagna?.sign_name },
    { label: "Moon", a: a?.d1_chart?.Moon?.sign_name, b: b?.d1_chart?.Moon?.sign_name },
    { label: "Sun", a: a?.d1_chart?.Sun?.sign_name, b: b?.d1_chart?.Sun?.sign_name },
  ];
  PLANETS.forEach((pl) => {
    rows.push({
      label: pl,
      a: a?.d1_chart?.[pl]?.sign_name,
      b: b?.d1_chart?.[pl]?.sign_name,
      sub: true,
    });
  });
  return rows;
};

export const ComparePage = () => {
  const navigate = useNavigate();
  const { selectedProfile, profiles, loadProfiles } = useProfile();

  const ayanamsa = localStorage.getItem("ayanamsa") || DEFAULT_AYANAMSA;
  const chartStyle = localStorage.getItem("chartStyle") || "north";
  const Kundali = chartStyle === "south" ? SouthIndianChart : NorthIndianChart;

  const [secondId, setSecondId] = useState("");
  const [chartA, setChartA] = useState(null);
  const [chartB, setChartB] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    loadProfiles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProfile, navigate]);

  const secondProfile = useMemo(
    () => profiles?.find((p) => p._id === secondId) || null,
    [profiles, secondId]
  );

  useEffect(() => {
    if (!selectedProfile || !secondProfile) {
      setChartA(null);
      setChartB(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    Promise.all([
      astrologyService.calculateBirthChart(toBirthDetails(selectedProfile), ayanamsa),
      astrologyService.calculateBirthChart(toBirthDetails(secondProfile), ayanamsa),
    ])
      .then(([ra, rb]) => {
        if (cancelled) return;
        setChartA(ra.data);
        setChartB(rb.data);
      })
      .catch((e) => {
        if (!cancelled) setError(e.response?.data?.detail || "Failed to calculate charts");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProfile, secondProfile, ayanamsa]);

  if (!selectedProfile) return null;

  const otherProfiles = (profiles || []).filter((p) => p._id !== selectedProfile._id);
  const nameA = selectedProfile.profile_name;
  const nameB = secondProfile?.profile_name || "Person 2";

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<GitCompareArrows size={24} />}
        title="Compare Charts"
        subtitle="Two profiles side by side"
        accent="indigo"
      />

      <div className="dashboard-content">
        <Card title="Select a second profile" icon={<Users size={24} />} accent="saffron">
          <div className="ui-field-grid">
            <div className="ui-datafield">
              <div className="ui-datafield-label">Person 1</div>
              <div className="ui-datafield-value">{nameA}</div>
            </div>
            <label className="ui-datafield" style={{ cursor: "pointer" }}>
              <div className="ui-datafield-label">Person 2</div>
              <select
                value={secondId}
                onChange={(e) => setSecondId(e.target.value)}
                style={{
                  width: "100%",
                  marginTop: "var(--space-xs)",
                  padding: "var(--space-sm)",
                  borderRadius: "var(--radius-md)",
                  border: "2px solid var(--sandalwood)",
                  background: "white",
                  color: "var(--cosmic-indigo)",
                  fontWeight: 600,
                }}
              >
                <option value="">Choose a profile…</option>
                {otherProfiles.map((p) => (
                  <option key={p._id} value={p._id}>
                    {p.profile_name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {otherProfiles.length === 0 && (
            <p style={{ color: "var(--text-secondary)", marginTop: "var(--space-md)" }}>
              You need at least two saved profiles to compare. Add another from “Change Chart”.
            </p>
          )}
        </Card>

        <ErrorBanner message={error} />

        {loading && (
          <Card>
            <LoadingState message="Calculating both charts…" />
          </Card>
        )}

        {!loading && chartA && chartB && (
          <>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
                gap: "var(--space-xl)",
              }}
            >
              <Card title={nameA} accent="saffron">
                <Kundali planets={chartA.planets} lagna={chartA.lagna} title={nameA} exportable />
              </Card>
              <Card title={nameB} accent="vermillion">
                <Kundali planets={chartB.planets} lagna={chartB.lagna} title={nameB} exportable />
              </Card>
            </div>

            <Card
              title="Placements side by side"
              icon={<GitCompareArrows size={24} />}
              accent="indigo"
            >
              <div style={{ overflowX: "auto" }}>
                <table className="adv-table">
                  <thead>
                    <tr>
                      <th>Body</th>
                      <th>{nameA}</th>
                      <th>{nameB}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {compareRows(chartA, chartB).map((r) => (
                      <tr key={r.label}>
                        <td style={{ fontWeight: r.sub ? 400 : 700 }}>{r.label}</td>
                        <td
                          style={{
                            background: r.a && r.a === r.b ? "rgba(255,153,51,0.12)" : undefined,
                          }}
                        >
                          {r.a || "—"}
                        </td>
                        <td
                          style={{
                            background: r.a && r.a === r.b ? "rgba(255,153,51,0.12)" : undefined,
                          }}
                        >
                          {r.b || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p
                style={{
                  color: "var(--text-secondary)",
                  marginTop: "var(--space-md)",
                  fontSize: "0.85rem",
                }}
              >
                Highlighted rows share the same sign in both charts.
              </p>
            </Card>
          </>
        )}
      </div>
    </div>
  );
};

export default ComparePage;
