import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Heart, User, Users, Sparkles } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { formatDate, orDash } from "../utils/format";
import { astrologyService } from "../services/api";
import { PageHeader } from "../components/PageHeader";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import "../styles/Dashboard.css";

export const CompatibilityPage = () => {
  const navigate = useNavigate();
  const { selectedProfile, profiles, loadProfiles } = useProfile();

  const [secondProfile, setSecondProfile] = useState(null);
  const [useQwen, setUseQwen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  // Redirect if no profile selected
  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }

    loadProfiles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProfile, navigate]);

  const handleCalculate = async () => {
    if (!secondProfile) {
      setError("Please select a second profile for compatibility check");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const person1Data = {
        dob: selectedProfile.birth_details.dob,
        tob: selectedProfile.birth_details.tob,
        place: selectedProfile.birth_details.place,
        latitude: parseFloat(selectedProfile.birth_details.latitude),
        longitude: parseFloat(selectedProfile.birth_details.longitude),
        timezone: parseFloat(selectedProfile.birth_details.timezone),
      };

      const person2Data = {
        dob: secondProfile.birth_details.dob,
        tob: secondProfile.birth_details.tob,
        place: secondProfile.birth_details.place,
        latitude: parseFloat(secondProfile.birth_details.latitude),
        longitude: parseFloat(secondProfile.birth_details.longitude),
        timezone: parseFloat(secondProfile.birth_details.timezone),
      };

      const response = await astrologyService.getCompatibility(person1Data, person2Data, useQwen);
      setResult(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to calculate compatibility");
    } finally {
      setLoading(false);
    }
  };

  if (!selectedProfile) {
    return null;
  }

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Heart size={24} />}
        title="Compatibility Check"
        subtitle="Ashtakoot Matching System"
        accent="saffron"
      />

      {/* Content */}
      <div className="dashboard-content">
        <ErrorBanner message={error} />

        {/* Profile Selection Card */}
        <div
          style={{
            background: "white",
            borderRadius: "var(--radius-xl)",
            padding: "var(--space-xl)",
            marginBottom: "var(--space-xl)",
            boxShadow: "var(--shadow-lg)",
            borderTop: "4px solid var(--saffron)",
            animation: "fadeIn 0.6s ease-out",
          }}
        >
          <h3
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-sm)",
              marginBottom: "var(--space-lg)",
              color: "var(--cosmic-indigo)",
              fontSize: "1.5rem",
            }}
          >
            <Users size={24} style={{ color: "var(--saffron)" }} />
            Select Profiles for Compatibility
          </h3>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
              gap: "var(--space-lg)",
            }}
          >
            {/* Person 1 - Selected Profile */}
            <div
              style={{
                padding: "var(--space-lg)",
                background:
                  "linear-gradient(135deg, rgba(255, 153, 51, 0.05) 0%, rgba(255, 153, 51, 0.15) 100%)",
                borderRadius: "var(--radius-lg)",
                border: "2px solid var(--saffron)",
              }}
            >
              <h4
                style={{
                  color: "var(--saffron)",
                  marginBottom: "var(--space-md)",
                  fontSize: "1.125rem",
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-sm)",
                }}
              >
                <User size={20} /> Person 1
              </h4>
              <div
                style={{
                  padding: "var(--space-md)",
                  background: "white",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--sandalwood)",
                }}
              >
                <p
                  style={{
                    margin: "0 0 var(--space-sm) 0",
                    fontWeight: 600,
                    color: "var(--cosmic-indigo)",
                    fontSize: "1.125rem",
                  }}
                >
                  {selectedProfile.profile_name}
                </p>
                <div
                  style={{
                    fontSize: "0.875rem",
                    color: "var(--text-secondary)",
                    lineHeight: "1.6",
                  }}
                >
                  <div style={{ marginBottom: "var(--space-xs)" }}>
                    <strong>Name:</strong> {selectedProfile.birth_details.name || "Anonymous"}
                  </div>
                  <div style={{ marginBottom: "var(--space-xs)" }}>
                    <strong>DOB:</strong> {formatDate(selectedProfile.birth_details.dob)}
                  </div>
                  <div style={{ marginBottom: "var(--space-xs)" }}>
                    <strong>Time:</strong> {orDash(selectedProfile.birth_details.tob)}
                  </div>
                  <div>
                    <strong>Place:</strong> {orDash(selectedProfile.birth_details.place)}
                  </div>
                </div>
              </div>
            </div>

            {/* Person 2 - Select from profiles */}
            <div
              style={{
                padding: "var(--space-lg)",
                background:
                  "linear-gradient(135deg, rgba(227, 66, 52, 0.05) 0%, rgba(227, 66, 52, 0.15) 100%)",
                borderRadius: "var(--radius-lg)",
                border: "2px solid var(--vermillion)",
              }}
            >
              <h4
                style={{
                  color: "var(--vermillion)",
                  marginBottom: "var(--space-md)",
                  fontSize: "1.125rem",
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-sm)",
                }}
              >
                <User size={20} /> Person 2
              </h4>
              <label
                style={{
                  display: "block",
                  marginBottom: "var(--space-sm)",
                  fontWeight: 600,
                  color: "var(--cosmic-indigo)",
                  fontSize: "0.875rem",
                }}
              >
                Select Profile to Compare:
              </label>
              <select
                value={secondProfile?._id || ""}
                onChange={(e) => {
                  const profile = profiles.find((p) => p._id === e.target.value);
                  setSecondProfile(profile || null);
                  setResult(null);
                }}
                style={{
                  width: "100%",
                  padding: "var(--space-md)",
                  borderRadius: "var(--radius-md)",
                  border: "2px solid var(--sandalwood)",
                  fontSize: "1rem",
                  fontFamily: "inherit",
                  background: "white",
                  color: "var(--cosmic-indigo)",
                  cursor: "pointer",
                  transition: "all 0.3s ease",
                }}
              >
                <option value="">-- Select a profile --</option>
                {profiles
                  .filter((p) => p._id !== selectedProfile._id)
                  .map((profile) => (
                    <option key={profile._id} value={profile._id}>
                      {profile.profile_name} ({profile.birth_details.name || "Anonymous"})
                    </option>
                  ))}
              </select>

              {secondProfile && (
                <div
                  style={{
                    marginTop: "var(--space-md)",
                    padding: "var(--space-md)",
                    background: "white",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--sandalwood)",
                    animation: "fadeIn 0.3s ease-out",
                  }}
                >
                  <p
                    style={{
                      margin: "0 0 var(--space-sm) 0",
                      fontWeight: 600,
                      color: "var(--cosmic-indigo)",
                      fontSize: "1.125rem",
                    }}
                  >
                    {secondProfile.profile_name}
                  </p>
                  <div
                    style={{
                      fontSize: "0.875rem",
                      color: "var(--text-secondary)",
                      lineHeight: "1.6",
                    }}
                  >
                    <div style={{ marginBottom: "var(--space-xs)" }}>
                      <strong>Name:</strong> {secondProfile.birth_details.name || "Anonymous"}
                    </div>
                    <div style={{ marginBottom: "var(--space-xs)" }}>
                      <strong>DOB:</strong> {formatDate(secondProfile.birth_details.dob)}
                    </div>
                    <div style={{ marginBottom: "var(--space-xs)" }}>
                      <strong>Time:</strong> {orDash(secondProfile.birth_details.tob)}
                    </div>
                    <div>
                      <strong>Place:</strong> {orDash(secondProfile.birth_details.place)}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* AI Toggle */}
          <div
            style={{
              marginTop: "var(--space-lg)",
              padding: "var(--space-md)",
              background: "var(--sacred-white)",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--sandalwood)",
              display: "flex",
              alignItems: "center",
              gap: "var(--space-md)",
            }}
          >
            <input
              type="checkbox"
              id="useQwen"
              checked={useQwen}
              onChange={(e) => setUseQwen(e.target.checked)}
              style={{
                width: "20px",
                height: "20px",
                cursor: "pointer",
                accentColor: "var(--saffron)",
              }}
            />
            <label
              htmlFor="useQwen"
              style={{
                cursor: "pointer",
                fontSize: "1rem",
                color: "var(--cosmic-indigo)",
                fontWeight: 500,
                display: "flex",
                alignItems: "center",
                gap: "var(--space-sm)",
              }}
            >
              <Sparkles size={18} style={{ color: "var(--saffron)" }} />
              Use AI for detailed compatibility analysis
            </label>
          </div>

          {/* Calculate Button */}
          <button
            onClick={handleCalculate}
            disabled={loading || !secondProfile}
            style={{
              marginTop: "var(--space-lg)",
              width: "100%",
              padding: "var(--space-lg)",
              background: secondProfile
                ? "linear-gradient(135deg, var(--saffron) 0%, var(--vermillion) 100%)"
                : "var(--sandalwood)",
              color: "white",
              border: "none",
              borderRadius: "var(--radius-lg)",
              fontSize: "1.125rem",
              fontWeight: 700,
              cursor: secondProfile ? "pointer" : "not-allowed",
              boxShadow: secondProfile ? "var(--shadow-lg)" : "none",
              transition: "all 0.3s ease",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "var(--space-sm)",
            }}
            onMouseOver={(e) => {
              if (secondProfile) {
                e.currentTarget.style.transform = "translateY(-2px)";
                e.currentTarget.style.boxShadow = "0 8px 24px rgba(255, 153, 51, 0.4)";
              }
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.boxShadow = secondProfile ? "var(--shadow-lg)" : "none";
            }}
          >
            <Heart size={20} />
            {loading ? "Calculating Compatibility..." : "Check Compatibility"}
          </button>
        </div>

        {/* Loading State */}
        {loading && (
          <Card>
            <LoadingState message="Calculating Compatibility — analyzing Ashtakoot matching between the two charts…" />
          </Card>
        )}

        {/* Results */}
        {result && !loading && (
          <div
            style={{
              background: "white",
              borderRadius: "var(--radius-xl)",
              padding: "var(--space-xl)",
              boxShadow: "var(--shadow-lg)",
              borderTop: "4px solid var(--saffron)",
              animation: "fadeIn 0.6s ease-out",
            }}
          >
            <h3
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-sm)",
                marginBottom: "var(--space-lg)",
                color: "var(--cosmic-indigo)",
                fontSize: "1.5rem",
              }}
            >
              <Heart size={24} style={{ color: "var(--saffron)" }} />
              Compatibility Results
            </h3>

            {/* Total Score Display */}
            <div
              style={{
                padding: "var(--space-xl)",
                background:
                  "linear-gradient(135deg, rgba(255, 153, 51, 0.1) 0%, rgba(227, 66, 52, 0.1) 100%)",
                borderRadius: "var(--radius-lg)",
                marginBottom: "var(--space-xl)",
                textAlign: "center",
                border: "2px solid var(--saffron)",
              }}
            >
              <div
                style={{
                  fontSize: "0.875rem",
                  color: "var(--text-secondary)",
                  marginBottom: "var(--space-sm)",
                  textTransform: "uppercase",
                  letterSpacing: "1px",
                  fontWeight: 600,
                }}
              >
                Total Compatibility Score
              </div>
              <div
                style={{
                  fontSize: "4rem",
                  fontWeight: 700,
                  background: "linear-gradient(135deg, var(--saffron) 0%, var(--vermillion) 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  marginBottom: "var(--space-sm)",
                }}
              >
                {result.total_score}
                <span style={{ fontSize: "2rem" }}>/36</span>
              </div>
              <div
                style={{
                  padding: "var(--space-md)",
                  background: "white",
                  borderRadius: "var(--radius-md)",
                  display: "inline-block",
                  boxShadow: "var(--shadow-sm)",
                }}
              >
                <span
                  style={{ fontWeight: 700, color: "var(--cosmic-indigo)", fontSize: "1.125rem" }}
                >
                  Status: {result.status}
                </span>
              </div>
            </div>

            {/* Ashtakoot Breakdown */}
            <h4
              style={{
                color: "var(--cosmic-indigo)",
                marginBottom: "var(--space-md)",
                fontSize: "1.25rem",
                fontWeight: 700,
              }}
            >
              Ashtakoot (8 Kootas) Breakdown
            </h4>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
                gap: "var(--space-md)",
                marginBottom: "var(--space-xl)",
              }}
            >
              {[
                { name: "Varna (Dina)", score: result.dinam, max: 1 },
                { name: "Vashya (Gana)", score: result.ganam, max: 2 },
                { name: "Tara (Dina)", score: result.dinam, max: 3 },
                { name: "Yoni", score: result.yoni, max: 4 },
                { name: "Graha Maitri (Rasi)", score: result.rasi, max: 5 },
                { name: "Gana", score: result.ganam, max: 6 },
                { name: "Bhakoot (Rajju)", score: result.rajju, max: 7 },
                { name: "Nadi (Vedha)", score: result.vedha, max: 8 },
              ].map((koota, index) => (
                <div
                  key={index}
                  style={{
                    padding: "var(--space-md)",
                    background: "var(--sacred-white)",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--sandalwood)",
                    textAlign: "center",
                    transition: "all 0.3s ease",
                  }}
                  onMouseOver={(e) => {
                    e.currentTarget.style.transform = "translateY(-2px)";
                    e.currentTarget.style.boxShadow = "var(--shadow-md)";
                  }}
                  onMouseOut={(e) => {
                    e.currentTarget.style.transform = "translateY(0)";
                    e.currentTarget.style.boxShadow = "none";
                  }}
                >
                  <div
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-secondary)",
                      marginBottom: "var(--space-xs)",
                      fontWeight: 600,
                    }}
                  >
                    {koota.name}
                  </div>
                  <div
                    style={{
                      fontSize: "1.5rem",
                      fontWeight: 700,
                      color:
                        koota.score >= koota.max * 0.7
                          ? "var(--emerald-green)"
                          : koota.score >= koota.max * 0.4
                            ? "var(--saffron)"
                            : "var(--vermillion)",
                    }}
                  >
                    {koota.score}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                    out of {koota.max}
                  </div>
                </div>
              ))}
            </div>

            {/* AI Analysis */}
            {result.ai_analysis && (
              <div
                style={{
                  padding: "var(--space-lg)",
                  background:
                    "linear-gradient(135deg, rgba(52, 73, 94, 0.05) 0%, rgba(52, 73, 94, 0.1) 100%)",
                  borderRadius: "var(--radius-lg)",
                  border: "2px solid var(--cosmic-indigo)",
                }}
              >
                <h4
                  style={{
                    color: "var(--cosmic-indigo)",
                    marginBottom: "var(--space-md)",
                    fontSize: "1.25rem",
                    fontWeight: 700,
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-sm)",
                  }}
                >
                  <Sparkles size={20} style={{ color: "var(--saffron)" }} />
                  AI Analysis
                </h4>
                <div
                  style={{
                    padding: "var(--space-md)",
                    background: "white",
                    borderRadius: "var(--radius-md)",
                    fontSize: "1rem",
                    lineHeight: "1.8",
                    color: "var(--cosmic-indigo)",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {result.ai_analysis}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
