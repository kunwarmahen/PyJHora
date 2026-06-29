import React, { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { Star, Calendar, Clock, MapPin } from "lucide-react";
import { astrologyService } from "../services/api";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { DataField } from "../components/DataField";
import { formatDate, orDash } from "../utils/format";
import "../styles/Dashboard.css";

/** Public, read-only view of a shared chart (no auth required). */
export const SharedChartPage = () => {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    astrologyService
      .getSharedChart(token)
      .then((r) => !cancelled && setData(r.data))
      .catch((e) => {
        if (!cancelled)
          setError(
            e.response?.status === 404
              ? "This shared chart was not found."
              : "Failed to load the shared chart."
          );
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [token]);

  const chart = data?.chart;
  const bd = data?.birth_details || {};
  const title = data?.profile_name || bd.name || "Shared Chart";

  return (
    <div className="dashboard-container mandala-bg">
      <nav className="navbar">
        <div className="navbar-brand">
          <Star className="brand-icon" size={28} />
          <h1>PyJHora</h1>
        </div>
        <div className="nav-right">
          <Link to="/login" className="change-profile-btn">
            <Star size={16} />
            <span>Open PyJHora</span>
          </Link>
        </div>
      </nav>

      <div className="dashboard-content">
        <div
          className="fade-in"
          style={{
            background: "rgba(255, 153, 51, 0.1)",
            border: "1px solid rgba(255, 153, 51, 0.3)",
            borderRadius: "var(--radius-lg)",
            padding: "var(--space-md) var(--space-lg)",
            marginBottom: "var(--space-xl)",
            color: "var(--saffron)",
            fontWeight: 600,
          }}
        >
          Read-only shared chart — anyone with this link can view it.
        </div>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message="Loading shared chart…" />
          </Card>
        ) : chart ? (
          <>
            <Card title={title} icon={<Star size={24} />}>
              <div className="ui-field-grid">
                <DataField
                  label="Date of Birth"
                  icon={<Calendar size={16} />}
                  value={formatDate(bd.dob)}
                />
                <DataField
                  label="Time of Birth"
                  icon={<Clock size={16} />}
                  value={orDash(bd.tob)}
                />
                <DataField label="Place" icon={<MapPin size={16} />} value={orDash(bd.place)} />
                <DataField
                  label="Lagna"
                  icon={<Star size={16} />}
                  value={chart.lagna?.sign_name || "—"}
                />
              </div>
            </Card>

            <NorthIndianChart chartData={chart} title="Rasi Chart" subtitle="D1" exportable />

            {chart.d9_chart && chart.d9_lagna && (
              <NorthIndianChart
                planets={chart.d9_chart}
                lagna={chart.d9_lagna}
                title="Navamsa Chart"
                subtitle="D9"
                exportable
              />
            )}

            <p
              style={{
                textAlign: "center",
                color: "var(--text-secondary)",
                marginTop: "var(--space-xl)",
              }}
            >
              Want your own chart, dashas and AI readings?{" "}
              <Link to="/register" style={{ color: "var(--saffron)", fontWeight: 600 }}>
                Create a free account
              </Link>
              .
            </p>
          </>
        ) : null}
      </div>
    </div>
  );
};

export default SharedChartPage;
