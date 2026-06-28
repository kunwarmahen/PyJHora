import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Clock, AlertCircle, Star, ChevronDown, Calendar } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import "../styles/Dashboard.css";

// ── Shared helpers ──────────────────────────────────────────────────────────
const NOW = new Date();

const isCurrentPeriod = (startDate, endDate) => {
  if (!startDate || !endDate) return false;
  try {
    return NOW >= new Date(startDate) && NOW <= new Date(endDate);
  } catch (e) {
    return false;
  }
};

const formatDate = (dateStr) => {
  if (!dateStr) return "N/A";
  try {
    return new Date(dateStr).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch (e) {
    return "N/A";
  }
};

// Vimsottari has four levels we expose; each gets its own label + accent so the
// nested tree stays readable as you drill down.
const LEVELS = {
  1: { label: "Maha Dasha", accent: "var(--saffron)" },
  2: { label: "Bhukti (Antar)", accent: "var(--cosmic-indigo)" },
  3: { label: "Antara (Pratyantar)", accent: "var(--vermillion)" },
  4: { label: "Sookshma", accent: "var(--terracotta)" },
};

const formatDuration = (node, level) => {
  if (level === 1 && node.duration_years != null) {
    return `${node.duration_years} years`;
  }
  if (node.duration_months != null && node.duration_months >= 1) {
    return `${Math.round(node.duration_months * 10) / 10} months`;
  }
  if (node.duration_days != null) {
    return `${Math.round(node.duration_days)} days`;
  }
  if (node.duration_months != null) {
    return `${Math.round(node.duration_months * 30)} days`;
  }
  return "";
};

// ── Recursive period node (Maha → Bhukti → Antara → Sookshma) ───────────────
// `eagerChildren` carries children already present in the payload (the Maha
// Dasha ships its Bhuktis). Deeper levels are lazy-fetched on first expand.
function DashaNode({ node, level, path, birthDetails, eagerChildren = null }) {
  const isCurrent = isCurrentPeriod(node.start_date, node.end_date);
  const canExpand = level < 4;
  const meta = LEVELS[level];

  const [expanded, setExpanded] = useState(isCurrent && canExpand);
  const [children, setChildren] = useState(eagerChildren);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchChildren = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await astrologyService.getDhasaChildren(birthDetails, path);
      setChildren(res.data.children || []);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load sub-periods");
    } finally {
      setLoading(false);
    }
  }, [birthDetails, path]);

  // Auto-load children when a node opens (incl. the current-period cascade,
  // which expands the whole live Maha→Bhukti→Antara→Sookshma chain on mount).
  useEffect(() => {
    if (expanded && canExpand && children == null && !loading) {
      fetchChildren();
    }
  }, [expanded, canExpand, children, loading, fetchChildren]);

  const toggle = () => {
    if (canExpand) setExpanded((v) => !v);
  };

  // Indentation + size taper with depth so deep trees stay compact.
  const indent = (level - 1) * 16;
  const avatar = level === 1 ? 40 : level === 2 ? 34 : 28;
  const lordSize = level === 1 ? "1.125rem" : level === 2 ? "1rem" : "0.9375rem";

  return (
    <div
      style={{
        marginLeft: indent,
        border: isCurrent ? `2px solid ${meta.accent}` : "1px solid var(--sandalwood)",
        borderRadius: "var(--radius-lg)",
        overflow: "hidden",
        background: isCurrent ? "rgba(255, 153, 51, 0.05)" : "var(--sacred-white)",
      }}
    >
      <div
        onClick={toggle}
        style={{
          padding: level === 1 ? "var(--space-lg)" : "var(--space-md)",
          cursor: canExpand ? "pointer" : "default",
          display: "grid",
          gridTemplateColumns: "auto 1fr auto auto",
          gap: "var(--space-md)",
          alignItems: "center",
        }}
      >
        <div
          style={{
            width: avatar,
            height: avatar,
            background: isCurrent
              ? "linear-gradient(135deg, var(--saffron) 0%, var(--vermillion) 100%)"
              : `linear-gradient(135deg, ${meta.accent} 0%, var(--cosmic-indigo-light) 100%)`,
            borderRadius: "50%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "white",
            fontWeight: 700,
            fontSize: "0.75rem",
            flexShrink: 0,
          }}
        >
          {(node.lord || "?").slice(0, 2)}
        </div>

        <div>
          <div
            style={{
              fontSize: lordSize,
              fontWeight: 700,
              color: isCurrent ? meta.accent : "var(--cosmic-indigo)",
            }}
          >
            {node.lord}
            <span
              style={{
                marginLeft: "var(--space-sm)",
                fontSize: "0.6875rem",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.5px",
                color: "var(--text-muted)",
              }}
            >
              {meta.label}
            </span>
          </div>
          <div style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", marginTop: "2px" }}>
            {formatDuration(node, level)}
            {node.start_date && node.end_date && (
              <span>
                {" "}
                • {formatDate(node.start_date)} to {formatDate(node.end_date)}
              </span>
            )}
          </div>
        </div>

        {isCurrent && (
          <div
            style={{
              padding: "var(--space-xs) var(--space-sm)",
              background: meta.accent,
              color: "white",
              borderRadius: "var(--radius-full)",
              fontSize: "0.625rem",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.5px",
              whiteSpace: "nowrap",
            }}
          >
            Now
          </div>
        )}

        {canExpand ? (
          <div
            style={{
              color: meta.accent,
              transition: "transform 0.3s ease",
              transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
            }}
          >
            <ChevronDown size={20} />
          </div>
        ) : (
          <div style={{ width: 20 }} />
        )}
      </div>

      {expanded && canExpand && (
        <div
          style={{
            borderTop: "1px solid var(--sandalwood)",
            padding: "var(--space-md)",
            background: "white",
            display: "flex",
            flexDirection: "column",
            gap: "var(--space-sm)",
          }}
        >
          {loading && (
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)", color: "var(--text-secondary)", fontSize: "0.875rem" }}>
              <div className="spinner" style={{ width: 18, height: 18 }}></div>
              Loading {LEVELS[level + 1]?.label || "sub"}-periods…
            </div>
          )}
          {error && (
            <div style={{ color: "var(--vermillion)", fontSize: "0.875rem", display: "flex", alignItems: "center", gap: "var(--space-sm)" }}>
              <AlertCircle size={16} /> {error}
            </div>
          )}
          {!loading &&
            !error &&
            children &&
            children.map((child, idx) => (
              <DashaNode
                key={`${child.lord}-${idx}`}
                node={child}
                level={level + 1}
                path={[...path, child.lord]}
                birthDetails={birthDetails}
                eagerChildren={child.sub_periods || null}
              />
            ))}
        </div>
      )}
    </div>
  );
}

export const DhasaPage = () => {
  const navigate = useNavigate();
  const { selectedProfile } = useProfile();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const birthDetails = useMemo(
    () =>
      selectedProfile
        ? {
            name: selectedProfile.birth_details.name,
            dob: selectedProfile.birth_details.dob,
            tob: selectedProfile.birth_details.tob,
            place: selectedProfile.birth_details.place,
            latitude: selectedProfile.birth_details.latitude,
            longitude: selectedProfile.birth_details.longitude,
            timezone: selectedProfile.birth_details.timezone,
          }
        : null,
    [selectedProfile]
  );

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    calculateDasha();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProfile, navigate]);

  const calculateDasha = async () => {
    if (!selectedProfile) return;
    setLoading(true);
    setError("");
    try {
      const response = await astrologyService.getDhasa(birthDetails, "vimsottari");
      setResult(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to calculate Dasha");
    } finally {
      setLoading(false);
    }
  };

  // Current Maha + Bhukti from the eager payload, for the summary banner.
  const getCurrentMahaDasha = () => {
    if (!result || !result.dasha_sequence) return null;
    return result.dasha_sequence.find((d) => isCurrentPeriod(d.start_date, d.end_date)) || null;
  };
  const getCurrentSubPeriod = (maha) => {
    if (!maha || !maha.sub_periods) return null;
    return maha.sub_periods.find((s) => isCurrentPeriod(s.start_date, s.end_date)) || null;
  };

  const currentMahaDasha = getCurrentMahaDasha();
  const currentSubPeriod = currentMahaDasha ? getCurrentSubPeriod(currentMahaDasha) : null;

  if (!selectedProfile) {
    return null;
  }

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Clock size={24} />}
        title="Vimsottari Dasha"
        subtitle="Planetary periods — drill down Maha → Bhukti → Antara → Sookshma"
        accent="indigo"
      />

      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />

        <ErrorBanner message={error} />

        {/* System badge + today */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "var(--space-md)",
            marginBottom: "var(--space-xl)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-sm)",
              padding: "var(--space-sm) var(--space-lg)",
              background: "white",
              borderRadius: "var(--radius-full)",
              boxShadow: "var(--shadow-sm)",
              borderLeft: "4px solid var(--cosmic-indigo)",
              fontWeight: 700,
              color: "var(--cosmic-indigo)",
            }}
          >
            <Clock size={18} style={{ color: "var(--saffron)" }} />
            Vimsottari System
            <span style={{ fontSize: "0.75rem", fontWeight: 500, color: "var(--text-muted)" }}>120-year cycle</span>
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-sm)",
              padding: "var(--space-sm) var(--space-md)",
              background: "rgba(255, 153, 51, 0.1)",
              borderRadius: "var(--radius-md)",
              fontSize: "0.875rem",
              color: "var(--saffron)",
              fontWeight: 600,
            }}
          >
            <Calendar size={16} />
            Today: {NOW.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })}
          </div>
        </div>

        {loading ? (
          <div
            style={{
              background: "white",
              borderRadius: "var(--radius-xl)",
              padding: "var(--space-3xl)",
              textAlign: "center",
              boxShadow: "var(--shadow-lg)",
            }}
          >
            <div className="spinner" style={{ margin: "0 auto var(--space-xl)" }}></div>
            <h3 style={{ color: "var(--cosmic-indigo)", marginBottom: "var(--space-sm)" }}>Calculating Vimsottari Dasha</h3>
            <p style={{ color: "var(--text-secondary)" }}>Analyzing planetary periods…</p>
          </div>
        ) : result ? (
          <div style={{ opacity: 0, animation: "fadeIn 0.6s ease-out forwards" }}>
            {/* Current Period Highlight */}
            {currentMahaDasha && (
              <div
                style={{
                  background: "linear-gradient(135deg, rgba(255, 153, 51, 0.1) 0%, rgba(226, 123, 90, 0.1) 100%)",
                  border: "3px solid var(--saffron)",
                  borderRadius: "var(--radius-xl)",
                  padding: "var(--space-xl)",
                  marginBottom: "var(--space-xl)",
                  boxShadow: "0 0 24px rgba(255, 153, 51, 0.2)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-sm)", marginBottom: "var(--space-md)" }}>
                  <div
                    style={{
                      width: "40px",
                      height: "40px",
                      background: "linear-gradient(135deg, var(--saffron) 0%, var(--vermillion) 100%)",
                      borderRadius: "50%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "white",
                    }}
                  >
                    <Clock size={20} />
                  </div>
                  <h3 style={{ margin: 0, color: "var(--cosmic-indigo)", fontSize: "1.5rem" }}>Current Period</h3>
                </div>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                    gap: "var(--space-md)",
                    marginTop: "var(--space-lg)",
                  }}
                >
                  <div>
                    <div style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.5px", color: "var(--text-muted)", marginBottom: "var(--space-xs)" }}>
                      Maha Dasha
                    </div>
                    <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--saffron)" }}>{currentMahaDasha.lord}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.5px", color: "var(--text-muted)", marginBottom: "var(--space-xs)" }}>
                      Period
                    </div>
                    <div style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--cosmic-indigo)" }}>
                      {formatDate(currentMahaDasha.start_date)} - {formatDate(currentMahaDasha.end_date)}
                    </div>
                  </div>
                  {currentSubPeriod && (
                    <div>
                      <div style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.5px", color: "var(--text-muted)", marginBottom: "var(--space-xs)" }}>
                        Current Bhukti
                      </div>
                      <div style={{ fontSize: "1.125rem", fontWeight: 600, color: "var(--vermillion)" }}>{currentSubPeriod.lord}</div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "var(--space-xs)" }}>
                        {formatDate(currentSubPeriod.start_date)} - {formatDate(currentSubPeriod.end_date)}
                      </div>
                    </div>
                  )}
                </div>
                <p style={{ margin: "var(--space-lg) 0 0", fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                  The live period is expanded below — keep drilling to see the running Antara and Sookshma.
                </p>
              </div>
            )}

            {/* Full drill-down tree */}
            <div
              style={{
                background: "white",
                borderRadius: "var(--radius-xl)",
                padding: "var(--space-xl)",
                boxShadow: "var(--shadow-lg)",
                borderTop: "4px solid var(--cosmic-indigo)",
              }}
            >
              <h3
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-sm)",
                  marginBottom: "var(--space-xl)",
                  color: "var(--cosmic-indigo)",
                  fontSize: "1.5rem",
                }}
              >
                <Star size={24} style={{ color: "var(--saffron)" }} />
                All Maha Dasha Periods
              </h3>

              {result.dasha_sequence && result.dasha_sequence.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
                  {result.dasha_sequence.map((dasha, index) => (
                    <DashaNode
                      key={`${dasha.lord}-${index}`}
                      node={dasha}
                      level={1}
                      path={[dasha.lord]}
                      birthDetails={birthDetails}
                      eagerChildren={dasha.sub_periods || null}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};
