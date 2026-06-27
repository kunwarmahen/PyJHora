import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Sun, ArrowLeft, AlertCircle } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { GrahaTable } from "../components/GrahaTable";
import "../styles/ledger.css";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const formatDate = (iso) => {
  if (!iso) return "—";
  const [y, m, d] = iso.split("T")[0].split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${d} ${MONTHS[m - 1]} ${y}`;
};

const formatLat = (v) =>
  v == null || Number.isNaN(v) ? "—" : `${Math.abs(v).toFixed(4)}°${v >= 0 ? "N" : "S"}`;
const formatLon = (v) =>
  v == null || Number.isNaN(v) ? "—" : `${Math.abs(v).toFixed(4)}°${v >= 0 ? "E" : "W"}`;
const formatTz = (v) =>
  v == null || v === "" ? "—" : `${Number(v) >= 0 ? "+" : "−"}${Math.abs(Number(v)).toFixed(2)}`;

export const BirthChartPage = () => {
  const navigate = useNavigate();
  const { selectedProfile } = useProfile();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    calculateChart();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProfile, navigate]);

  const calculateChart = async () => {
    if (!selectedProfile) return;
    setLoading(true);
    setError("");
    try {
      const b = selectedProfile.birth_details;
      const response = await astrologyService.calculateBirthChart({
        name: b.name,
        dob: b.dob,
        tob: b.tob,
        place: b.place,
        latitude: parseFloat(b.latitude),
        longitude: parseFloat(b.longitude),
        timezone: parseFloat(b.timezone),
      });
      setResult(response.data);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "The chart could not be cast. Check the birth details and try again."
      );
    } finally {
      setLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const b = selectedProfile.birth_details;
  const displayName = b.name || selectedProfile.profile_name;

  return (
    <div className="jl-page">
      <header className="jl-topbar">
        <div className="jl-brand">
          <Sun size={18} />
          <span>Jyotisha</span>
        </div>
        <button className="jl-back" onClick={() => navigate("/dashboard")}>
          <ArrowLeft size={14} />
          Back
        </button>
      </header>

      <main className="jl-folio">
        {error && (
          <div className="jl-alert" role="alert">
            <AlertCircle size={20} />
            <span>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="jl-loading">
            <div className="jl-loading-mark" />
            <h2>Casting the chart</h2>
            <p>Computing planetary positions and divisional charts…</p>
          </div>
        ) : result ? (
          <>
            {/* Masthead — birth particulars */}
            <section className="jl-masthead">
              <p className="jl-eyebrow">Birth Chart</p>
              <h1 className="jl-name">{displayName}</h1>
              <p className="jl-particulars">
                {formatDate(b.dob)} · {b.tob || "—"} · {b.place || "—"}
              </p>
              <div className="jl-rule" />
              <dl className="jl-coords">
                <div><dt>lat</dt><dd>{formatLat(parseFloat(b.latitude))}</dd></div>
                <div><dt>lon</dt><dd>{formatLon(parseFloat(b.longitude))}</dd></div>
                <div><dt>tz</dt><dd>{formatTz(b.timezone)}</dd></div>
                {result.lagna?.sign_name && (
                  <div><dt>lagna</dt><dd>{result.lagna.sign_name}</dd></div>
                )}
              </dl>
            </section>

            {/* Charts */}
            <section className="jl-section">
              <div className="jl-section-head"><h2>Charts</h2></div>
              <div className="jl-charts">
                <NorthIndianChart chartData={result} title="Rāśi · D1" subtitle="North Indian" />
                {result.d9_chart && result.d9_lagna && (
                  <NorthIndianChart
                    planets={result.d9_chart}
                    lagna={result.d9_lagna}
                    title="Navāṁśa · D9"
                    subtitle="North Indian"
                  />
                )}
              </div>
            </section>

            {/* Graha positions */}
            {result.d1_chart && (
              <section className="jl-section">
                <div className="jl-section-head"><h2>Graha Positions</h2></div>
                <GrahaTable lagna={result.lagna} planets={result.d1_chart} />
              </section>
            )}
          </>
        ) : null}
      </main>
    </div>
  );
};
