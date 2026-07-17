import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useLocalizeName } from "../i18n/localizeName";
import {
  Calendar,
  User,
  MapPin,
  Clock,
  Star,
  Share2,
  Copy,
  Check,
  Eye,
  Crown,
  Landmark,
  ShieldAlert,
} from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { useSettings } from "../contexts/SettingsContext";
import { formatDate, orDash } from "../utils/format";
import { astrologyService } from "../services/api";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
import { PlanetExplorer } from "../components/PlanetExplorer";
import { PanchangaPanel } from "../components/PanchangaPanel";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { DataField } from "../components/DataField";
import { AspectsCard } from "../components/AspectsCard";
import { AdvancedOnly } from "../components/AdvancedOnly";
import { BirthTimeBanner } from "../components/BirthTimeBanner";
import { VARGAS, DEFAULT_VARGA } from "../constants/jyotish";
import "../styles/Dashboard.css";
import "../styles/Shared.css";

export const BirthChartPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const ln = useLocalizeName();
  const { selectedProfile } = useProfile();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [doshas, setDoshas] = useState(null);
  const [yogas, setYogas] = useState(null);
  const [rajaYogas, setRajaYogas] = useState(null);
  const [aspects, setAspects] = useState(null);
  const [showAspects, setShowAspects] = useState(
    () => localStorage.getItem("showAspects") === "1"
  );
  const [conditions, setConditions] = useState(null);
  const [showConditions, setShowConditions] = useState(
    () => localStorage.getItem("showConditions") === "1"
  );
  const [arudhas, setArudhas] = useState(null);
  const [showArudhas, setShowArudhas] = useState(
    () => localStorage.getItem("showArudhas") === "1"
  );
  const [focusPlanet, setFocusPlanet] = useState(null);
  const [explorerPlanet, setExplorerPlanet] = useState(null);
  // Chart style + ayanamsa are now global settings (edited in the Settings page).
  const { settings } = useSettings();
  const chartStyle = settings.chartStyle;
  const ayanamsa = settings.ayanamsa;
  const [varga, setVarga] = useState(() => Number(localStorage.getItem("varga")) || DEFAULT_VARGA);
  const [vargaChart, setVargaChart] = useState(null);
  const [vargaLoading, setVargaLoading] = useState(false);
  const [shareUrl, setShareUrl] = useState("");
  const [shareBusy, setShareBusy] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);

  const changeVarga = (value) => {
    setVarga(value);
    localStorage.setItem("varga", String(value));
  };

  const buildBirthDetails = () => ({
    name: selectedProfile.birth_details.name,
    dob: selectedProfile.birth_details.dob,
    tob: selectedProfile.birth_details.tob,
    place: selectedProfile.birth_details.place,
    latitude: parseFloat(selectedProfile.birth_details.latitude),
    longitude: parseFloat(selectedProfile.birth_details.longitude),
    timezone: parseFloat(selectedProfile.birth_details.timezone),
  });

  const handleShare = async () => {
    setShareBusy(true);
    try {
      const res = await astrologyService.createShare(
        buildBirthDetails(),
        ayanamsa,
        selectedProfile.profile_name
      );
      const url = `${window.location.origin}${res.data.path}`;
      setShareUrl(url);
      try {
        await navigator.clipboard.writeText(url);
        setShareCopied(true);
        setTimeout(() => setShareCopied(false), 2500);
      } catch {
        /* clipboard may be blocked; the link is still shown to copy manually */
      }
    } catch (err) {
      setError(err.response?.data?.detail || t("birthChart.shareError"));
    } finally {
      setShareBusy(false);
    }
  };

  // Redirect if no profile selected; (re)calculate when profile or ayanamsa changes
  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }

    calculateChart();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProfile, navigate, ayanamsa]);

  // Load the selected divisional (varga) chart. The Rasi (D1) and Navamsa (D9)
  // come back with the main birth-chart response, so reuse those instead of an
  // extra request; everything else is fetched on demand.
  useEffect(() => {
    if (!result || !selectedProfile) return;

    if (varga === 1) {
      setVargaChart({
        planets: result.planets,
        lagna: result.lagna,
        arudha_padas: result.d1_arudha_padas,
      });
      return;
    }
    if (varga === 9 && result.d9_chart && result.d9_lagna) {
      setVargaChart({
        planets: result.d9_chart,
        lagna: result.d9_lagna,
        arudha_padas: result.d9_arudha_padas,
      });
      return;
    }

    let cancelled = false;
    setVargaLoading(true);
    setVargaChart(null);
    astrologyService
      .getDivisionalChart(buildBirthDetails(), varga, ayanamsa)
      .then((r) => {
        if (!cancelled) setVargaChart(r.data);
      })
      .catch(() => {
        if (!cancelled) setVargaChart(null);
      })
      .finally(() => {
        if (!cancelled) setVargaLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result, varga, ayanamsa]);

  const calculateChart = async () => {
    if (!selectedProfile) return;

    setLoading(true);
    setError("");

    try {
      const birthDetails = buildBirthDetails();

      const response = await astrologyService.calculateBirthChart(birthDetails, ayanamsa);
      setResult(response.data);
      // Rasi (D1) arudhas ride along with the birth-chart response (per-chart arudhas
      // for the varga picker come from each divisional-chart response instead).
      setArudhas(response.data?.d1_arudha_padas || null);

      // Yogas, doshas & aspects load independently — a failure here shouldn't blank the chart.
      setDoshas(null);
      setYogas(null);
      setRajaYogas(null);
      setAspects(null);
      astrologyService
        .getDoshas(birthDetails, ayanamsa)
        .then((r) => setDoshas(r.data?.doshas || null))
        .catch(() => setDoshas(null));
      astrologyService
        .getYogas(birthDetails, ayanamsa)
        .then((r) => setYogas(r.data?.yogas || null))
        .catch(() => setYogas(null));
      astrologyService
        .getRajaYogas(birthDetails, ayanamsa)
        .then((r) => setRajaYogas(r.data?.raja_yogas || []))
        .catch(() => setRajaYogas(null));
      astrologyService
        .getAspects(birthDetails, ayanamsa)
        .then((r) => setAspects(r.data?.planets || null))
        .catch(() => setAspects(null));
      setConditions(null);
      astrologyService
        .getPlanetConditions(birthDetails, ayanamsa)
        .then((r) => setConditions(r.data?.flagged || null))
        .catch(() => setConditions(null));
    } catch (err) {
      setError(err.response?.data?.detail || t("birthChart.calcError"));
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
        icon={<Calendar size={24} />}
        title={t("birthChart.title")}
        subtitle={t("birthChart.subtitle")}
        accent="saffron"
      />

      {/* Content */}
      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />

        <ErrorBanner message={error} />

        {/* Loading State */}
        {loading ? (
          <Card>
            <LoadingState message={t("birthChart.loading")} />
          </Card>
        ) : result ? (
          <div className="fade-in">
            {/* Chart Details Card */}
            <Card
              title={t("birthChart.chartDetails")}
              icon={<Star size={24} />}
              actions={
                <button
                  className="chart-export-btn chart-export-btn--inline"
                  onClick={handleShare}
                  disabled={shareBusy}
                  title={t("birthChart.shareTitle")}
                >
                  {shareCopied ? <Check size={14} /> : <Share2 size={14} />}
                  <span>
                    {shareBusy
                      ? "…"
                      : shareCopied
                        ? t("birthChart.linkCopied")
                        : t("birthChart.share")}
                  </span>
                </button>
              }
            >
              <div className="ui-field-grid">
                <DataField
                  label={t("common.name")}
                  icon={<User size={16} />}
                  value={selectedProfile.birth_details.name || selectedProfile.profile_name}
                />
                <DataField
                  label={t("common.dateOfBirth")}
                  icon={<Calendar size={16} />}
                  value={formatDate(selectedProfile.birth_details.dob)}
                />
                <DataField
                  label={t("common.timeOfBirth")}
                  icon={<Clock size={16} />}
                  value={orDash(selectedProfile.birth_details.tob)}
                />
                <DataField
                  label={t("common.place")}
                  icon={<MapPin size={16} />}
                  value={orDash(selectedProfile.birth_details.place)}
                />
              </div>
              {shareUrl && (
                <div className="share-row">
                  <Copy size={14} style={{ color: "var(--saffron)", flexShrink: 0 }} />
                  <input
                    readOnly
                    className="share-url-input"
                    value={shareUrl}
                    onFocus={(e) => e.target.select()}
                  />
                </div>
              )}
            </Card>

            <BirthTimeBanner accuracy={selectedProfile.birth_details.time_accuracy} />

            {/* Chart style toggle: North / South Indian */}
            {(() => {
              const Kundali = chartStyle === "south" ? SouthIndianChart : NorthIndianChart;
              const styleLabel =
                chartStyle === "south" ? t("birthChart.southIndian") : t("birthChart.northIndian");
              // Birth time unknown → present the D1 from the Moon (Chandra Lagna),
              // since the real Ascendant can't be trusted.
              const unknownTime =
                (selectedProfile.birth_details.time_accuracy || "exact") === "unknown";
              const moon = result.planets?.Moon;
              const chandraLagna =
                unknownTime && moon
                  ? { house: moon.house, degrees: 0, sign_name: moon.sign_name }
                  : null;
              return (
                <>
                  <div className="aspect-controls">
                    {aspects && aspects.length > 0 && (
                      <button
                        type="button"
                        className={`aspect-toggle${showAspects ? " is-active" : ""}`}
                        onClick={() => {
                          const next = !showAspects;
                          setShowAspects(next);
                          localStorage.setItem("showAspects", next ? "1" : "0");
                        }}
                      >
                        <Eye size={16} />
                        {showAspects ? t("aspects.hideOnChart") : t("aspects.showOnChart")}
                      </button>
                    )}
                    {arudhas && arudhas.length > 0 && (
                      <button
                        type="button"
                        className={`aspect-toggle${showArudhas ? " is-active" : ""}`}
                        onClick={() => {
                          const next = !showArudhas;
                          setShowArudhas(next);
                          localStorage.setItem("showArudhas", next ? "1" : "0");
                        }}
                      >
                        <Landmark size={16} />
                        {showArudhas ? t("arudhas.hideOnChart") : t("arudhas.showOnChart")}
                      </button>
                    )}
                    {conditions && conditions.length > 0 && (
                      <button
                        type="button"
                        className={`aspect-toggle${showConditions ? " is-active" : ""}`}
                        onClick={() => {
                          const next = !showConditions;
                          setShowConditions(next);
                          localStorage.setItem("showConditions", next ? "1" : "0");
                        }}
                      >
                        <ShieldAlert size={16} />
                        {showConditions
                          ? t("conditions.hideOnChart")
                          : t("conditions.showOnChart")}
                      </button>
                    )}
                    {showAspects && aspects && aspects.length > 0 && (
                      <span className="aspect-controls__hint">{t("aspects.hoverHint")}</span>
                    )}
                    {showConditions && conditions && conditions.length > 0 && (
                      <span className="aspect-controls__hint">{t("conditions.hoverHint")}</span>
                    )}
                  </div>

                  <Kundali
                    chartData={result}
                    lagna={chandraLagna || undefined}
                    title={t("birthChart.rasiChart")}
                    subtitle={
                      chandraLagna
                        ? `D1 · ${t("birthTime.chandraLagna")} · ${styleLabel}`
                        : `D1 · ${styleLabel}`
                    }
                    exportable
                    aspects={aspects}
                    showAspects={showAspects}
                    focusPlanet={focusPlanet}
                    arudhas={arudhas}
                    showArudhas={showArudhas}
                    conditions={showConditions ? conditions : null}
                    onSelectPlanet={setExplorerPlanet}
                  />

                  {/* §5.5 Interactive explorer: click a graha (in the chart or the
                      chip strip) for its full picture */}
                  <PlanetExplorer
                    chart={result}
                    aspects={aspects}
                    conditions={conditions}
                    personName={selectedProfile.birth_details.name}
                    selected={explorerPlanet}
                    onSelect={setExplorerPlanet}
                  />

                  {/* Divisional (varga) chart with picker. Real Jyotish, but
                      "D9 / D10 / Shashtiamsa" is exactly the jargon a newcomer
                      shouldn't meet first — collapsed in Essentials. */}
                  <AdvancedOnly title={t("birthChart.divisionalChart")}>
                    {(() => {
                      const vargaMeta = VARGAS.find((v) => v.value === varga) || VARGAS[0];
                      return (
                        <div className="varga-section">
                          <label className="ayanamsa-select varga-picker">
                            <span>{t("birthChart.divisionalChart")}</span>
                            <select
                              value={varga}
                              onChange={(e) => changeVarga(Number(e.target.value))}
                            >
                              {VARGAS.map((v) => (
                                <option key={v.value} value={v.value}>
                                  {v.code} · {v.name}
                                </option>
                              ))}
                            </select>
                            <span className="varga-significance">{vargaMeta.significance}</span>
                          </label>

                          {vargaLoading ? (
                            <div className="varga-loading">
                              <div className="spinner"></div>
                              <span>
                                {t("birthChart.calculatingChart", { code: vargaMeta.code })}
                              </span>
                            </div>
                          ) : vargaChart && vargaChart.planets ? (
                            <Kundali
                              planets={vargaChart.planets}
                              lagna={vargaChart.lagna}
                              title={t("birthChart.nameChart", { name: vargaMeta.name })}
                              subtitle={`${vargaMeta.code} · ${styleLabel}`}
                              exportable
                              arudhas={vargaChart.arudha_padas}
                              showArudhas={showArudhas}
                            />
                          ) : (
                            <div className="varga-empty">{t("birthChart.chartUnavailable")}</div>
                          )}
                        </div>
                      );
                    })()}
                  </AdvancedOnly>
                </>
              );
            })()}

            {/* Nakshatra Information Section */}
            {result.lagna || result.d1_chart ? (
              <div className="ui-card ui-card--accent ui-card--flush mt-xl">
                <h3 className="ui-card-header">
                  <Star size={24} />
                  {t("birthChart.nakshatraInfo")}
                </h3>

                {/* Lagna Nakshatra */}
                {result.lagna && result.lagna.nakshatra && (
                  <div className="lagna-highlight">
                    <h4>{t("birthChart.lagnaAscendant")}</h4>
                    <div className="lagna-grid">
                      <div>
                        <span className="kv-label">{t("common.sign")}: </span>
                        <span className="kv-value">{ln(result.lagna.sign_name, "rasi")}</span>
                      </div>
                      <div>
                        <span className="kv-label">{t("common.nakshatra")}: </span>
                        <span className="kv-value">{ln(result.lagna.nakshatra, "nakshatra")}</span>
                      </div>
                      <div>
                        <span className="kv-label">{t("common.pada")}: </span>
                        <span className="kv-value">{result.lagna.nakshatra_pada}</span>
                      </div>
                      <div>
                        <span className="kv-label">{t("common.degrees")}: </span>
                        <span className="kv-value">{result.lagna.degrees}°</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Planetary Nakshatras */}
                {result.d1_chart && (
                  <div className="nakshatra-grid">
                    {Object.entries(result.d1_chart).map(([planet, data]) => (
                      <div key={planet} className="nakshatra-card">
                        <h5>{ln(planet, "graha")}</h5>
                        <div className="nakshatra-card__body">
                          <div>
                            <span className="kv-label">{t("common.sign")}: </span>
                            <span className="kv-value">{ln(data.sign_name, "rasi")}</span>
                          </div>
                          {data.nakshatra && (
                            <>
                              <div>
                                <span className="kv-label">{t("common.nakshatra")}: </span>
                                <span className="kv-value">{ln(data.nakshatra, "nakshatra")}</span>
                              </div>
                              <div>
                                <span className="kv-label">{t("common.pada")}: </span>
                                <span className="kv-value">{data.nakshatra_pada}</span>
                              </div>
                            </>
                          )}
                          <div>
                            <span className="kv-label">{t("common.degrees")}: </span>
                            <span className="kv-value">{data.degrees}°</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : null}

            {/* Panchanga (daily almanac) for the profile's location */}
            <PanchangaPanel
              place={selectedProfile.birth_details.place}
              latitude={parseFloat(selectedProfile.birth_details.latitude)}
              longitude={parseFloat(selectedProfile.birth_details.longitude)}
              timezone={parseFloat(selectedProfile.birth_details.timezone)}
            />

            {/* Yogas */}
            {yogas && yogas.length > 0 && (
              <div className="ui-card ui-card--accent ui-card--flush mt-xl">
                <h3 className="ui-card-header">
                  <Star size={24} />
                  {t("birthChart.yogas")}
                  <span className="section-count">
                    {t("birthChart.yogasFound", { count: yogas.length })}
                  </span>
                </h3>
                <div className="yoga-grid">
                  {yogas.map((y) => (
                    <div key={y.key} className="yoga-card">
                      <div className="yoga-name">{y.name}</div>
                      {y.description && <p className="yoga-desc">{y.description}</p>}
                      {y.benefits && (
                        <div className="yoga-benefit">
                          <span className="yoga-benefit-label">{t("birthChart.effects")}</span>
                          {y.benefits}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Raja Yogas (dedicated) */}
            {rajaYogas && (
              <div className="ui-card ui-card--accent-gold ui-card--flush mt-xl">
                <h3 className="ui-card-header">
                  <Crown size={24} />
                  {t("birthChart.rajaYogas")}
                  {rajaYogas.length > 0 && (
                    <span className="section-count">
                      {t("birthChart.rajaYogasFound", { count: rajaYogas.length })}
                    </span>
                  )}
                </h3>
                {rajaYogas.length > 0 ? (
                  <div className="yoga-grid">
                    {rajaYogas.map((y, i) => (
                      <div key={i} className="yoga-card raja-yoga-card">
                        <div className="yoga-name">
                          {y.name}
                          <span
                            className={`raja-yoga-strength raja-yoga-strength--${y.strength}`}
                            style={{ marginLeft: "0.5rem" }}
                          >
                            {t(`birthChart.rajaYogaStrength.${y.strength}`)}
                          </span>
                        </div>
                        {y.planets && y.planets.length > 0 && (
                          <div className="text-saffron fw-600" style={{ fontSize: "0.85rem" }}>
                            {y.planets.join(" – ")}
                          </div>
                        )}
                        {y.pairs_label && (
                          <div className="text-secondary" style={{ fontSize: "0.8rem" }}>
                            {y.pairs_label}
                          </div>
                        )}
                        {y.description && <p className="yoga-desc">{y.description}</p>}
                        {y.benefits && (
                          <div className="yoga-benefit">
                            <span className="yoga-benefit-label">{t("birthChart.effects")}</span>
                            {y.benefits}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="card-note">{t("birthChart.rajaYogasNone")}</p>
                )}
              </div>
            )}

            {/* Doshas */}
            {doshas && doshas.length > 0 && (
              <div className="ui-card ui-card--accent ui-card--flush mt-xl">
                <h3 className="ui-card-header">
                  <Star size={24} />
                  {t("birthChart.doshas")}
                </h3>
                <div className="dosha-grid">
                  {doshas.map((d) => (
                    <div key={d.key} className={`dosha-card${d.present ? " present" : ""}`}>
                      <div className="dosha-head">
                        <span className="dosha-name">{d.name}</span>
                        <span className={`dosha-badge ${d.present ? "yes" : "no"}`}>
                          {d.present ? t("birthChart.present") : t("birthChart.absent")}
                        </span>
                      </div>
                      <p className="dosha-desc">{d.description}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Graha Drishti (aspects) */}
            <AdvancedOnly title={t("birthChart.aspectsAdvanced")}>
              <AspectsCard aspects={aspects} onFocus={setFocusPlanet} focusPlanet={focusPlanet} />
            </AdvancedOnly>
          </div>
        ) : null}
      </div>
    </div>
  );
};
