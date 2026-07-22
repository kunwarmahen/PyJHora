import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Clock, AlertCircle, Star, ChevronDown, Calendar } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { intlLocale } from "../utils/format";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { AdvancedOnly } from "../components/AdvancedOnly";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
import { useSettings } from "../contexts/SettingsContext";
import "../styles/Dashboard.css";
import "../styles/Shared.css";
import { useLocalizeName } from "../i18n/localizeName";

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

const formatDate = (dateStr, locale = "en-US") => {
  if (!dateStr) return "—";
  try {
    return new Date(dateStr).toLocaleDateString(locale, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch (e) {
    return "—";
  }
};

// Vimsottari has four levels we expose; each gets its own label key + accent so
// the nested tree stays readable as you drill down.
const LEVELS = {
  1: { labelKey: "dhasa.mahaDasha", accent: "var(--saffron)" },
  2: { labelKey: "dhasa.bhukti", accent: "var(--cosmic-indigo)" },
  3: { labelKey: "dhasa.antara", accent: "var(--vermillion)" },
  4: { labelKey: "dhasa.sookshma", accent: "var(--terracotta)" },
};

const formatDuration = (node, level, t) => {
  if (level === 1 && node.duration_years != null) {
    return t("dhasa.years", { count: node.duration_years });
  }
  if (node.duration_months != null && node.duration_months >= 1) {
    return t("dhasa.months", { count: Math.round(node.duration_months * 10) / 10 });
  }
  if (node.duration_days != null) {
    return t("dhasa.days", { count: Math.round(node.duration_days) });
  }
  if (node.duration_months != null) {
    return t("dhasa.days", { count: Math.round(node.duration_months * 30) });
  }
  return "";
};

// ── Recursive period node (Mahadasha → Antardasha → Pratyantardasha → Sookshma) ─
// `eagerChildren` carries children already present in the payload (the Maha
// Dasha ships its Bhuktis). Deeper levels are lazy-fetched on first expand.
function DashaNode({ node, level, path, birthDetails, eagerChildren = null }) {
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
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
      setError(e.response?.data?.detail || t("dhasa.loadChildrenError"));
    } finally {
      setLoading(false);
    }
  }, [birthDetails, path, t]);

  // Auto-load children when a node opens (incl. the current-period cascade,
  // which expands the whole live Mahadasha→Antardasha→Pratyantardasha→Sookshma chain on mount).
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
      className={`dasha-node${level === 1 ? " dasha-node--root" : ""}${isCurrent ? " is-current" : ""}`}
      style={{ marginLeft: indent, "--lvl-accent": meta.accent, "--avatar": `${avatar}px` }}
    >
      <div onClick={toggle} className={`dasha-node__head${canExpand ? " is-expandable" : ""}`}>
        <div className="dasha-node__avatar">{(node.lord || "?").slice(0, 2)}</div>

        <div>
          <div className="dasha-node__lord" style={{ fontSize: lordSize }}>
            {node.lord}
            <span className="dasha-node__level">{t(meta.labelKey)}</span>
          </div>
          <div className="dasha-node__dates">
            {formatDuration(node, level, t)}
            {node.start_date && node.end_date && (
              <span>
                {" "}
                • {formatDate(node.start_date, locale)} to {formatDate(node.end_date, locale)}
              </span>
            )}
          </div>
        </div>

        {isCurrent && <div className="dasha-node__now">{t("dhasa.now")}</div>}

        {canExpand ? (
          <div className={`dasha-node__chevron${expanded ? " is-open" : ""}`}>
            <ChevronDown size={20} />
          </div>
        ) : (
          <div className="dasha-node__spacer" />
        )}
      </div>

      {expanded && canExpand && (
        <div className="dasha-node__children">
          {loading && (
            <div className="dasha-node__loading">
              <div className="spinner" style={{ width: 18, height: 18 }}></div>
              {t("dhasa.loadingChildren")}
            </div>
          )}
          {error && (
            <div className="dasha-node__error">
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

// ── Other (non-Vimsottari) dasha systems: a picker + a flat maha-period table ──
function OtherDashaSystems({ birthDetails }) {
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const { settings } = useSettings();
  const [systems, setSystems] = useState([]);
  const [selected, setSelected] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [applicable, setApplicable] = useState([]);
  const [searchParams] = useSearchParams();
  const deepLinkDone = useRef(false);
  const pendingScroll = useRef(false);
  const sectionRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    astrologyService
      .getDashaSystems()
      .then((r) => {
        if (!cancelled) setSystems(r.data.systems || []);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  // Which conditional dashas classically apply to THIS chart (BPHS rules).
  useEffect(() => {
    if (!birthDetails) return;
    let cancelled = false;
    astrologyService
      .getApplicableDashas(birthDetails, settings.ayanamsa)
      .then((r) => !cancelled && setApplicable(r.data?.applicable || []))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [birthDetails, settings.ayanamsa]);

  const load = useCallback(
    (key) => {
      if (!key || !birthDetails) return;
      setLoading(true);
      setError("");
      setData(null);
      astrologyService
        .getDashaPeriods(birthDetails, key)
        .then((r) => setData(r.data))
        .catch((e) => setError(e.response?.data?.detail || t("dhasa.loadDashaError")))
        .finally(() => setLoading(false));
    },
    [birthDetails, t]
  );

  const onChange = (key) => {
    setSelected(key);
    load(key);
  };

  // Deep link: /dhasa?system=<key> preselects that dasha and loads it once the
  // systems catalog and the chart are both ready. Runs once (the dashboard
  // launcher and any shared link land straight on the chosen system).
  useEffect(() => {
    if (deepLinkDone.current || !birthDetails || systems.length === 0) return;
    const key = searchParams.get("system");
    if (key && systems.some((s) => s.key === key)) {
      deepLinkDone.current = true;
      setSelected(key);
      load(key);
      // The picker sits far below the Vimsottari tree, so a deep link would
      // otherwise land silently at the top of the page. Defer the scroll until
      // the period table has loaded (below) so the layout has settled.
      pendingScroll.current = true;
    }
  }, [searchParams, systems, birthDetails, load]);

  // Bring the deep-linked system into view once its table has rendered.
  useEffect(() => {
    if (pendingScroll.current && data && !loading) {
      pendingScroll.current = false;
      requestAnimationFrame(() =>
        sectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
      );
    }
  }, [data, loading]);

  return (
    <div ref={sectionRef}>
    <Card title={t("dhasa.otherSystems")} icon={<Clock size={24} />}>
      {applicable.length > 0 && (
        <div className="dasha-reco">
          <div className="dasha-reco__label">
            <Star size={15} /> {t("dhasa.applicableTitle")}
          </div>
          <div className="dasha-reco__chips">
            {applicable.map((a) => {
              const clickable = !!a.picker_key;
              return (
                <button
                  key={a.key}
                  type="button"
                  className={`dasha-reco__chip${clickable ? "" : " is-static"}`}
                  title={a.description}
                  disabled={!clickable}
                  onClick={() => clickable && onChange(a.picker_key)}
                >
                  {a.name}
                </button>
              );
            })}
          </div>
          <p className="card-note">{t("dhasa.applicableNote")}</p>
        </div>
      )}

      <label className="ayanamsa-select" style={{ marginBottom: "var(--space-lg)" }}>
        <span>{t("dhasa.system")}</span>
        <select value={selected} onChange={(e) => onChange(e.target.value)}>
          <option value="">{t("dhasa.chooseSystem")}</option>
          {systems.map((s) => (
            <option key={s.key} value={s.key}>
              {s.name}
            </option>
          ))}
        </select>
      </label>

      {selected && systems.find((s) => s.key === selected)?.description && (
        <p className="text-secondary" style={{ marginBottom: "var(--space-lg)" }}>
          {systems.find((s) => s.key === selected).description}
        </p>
      )}

      <ErrorBanner message={error} />
      {loading && <LoadingState message={t("dhasa.calcPeriods")} />}

      {/* Sudarshana Chakra runs three wheels at once — name the reference signs
          so the three-part lord ("Taurus · Leo · Taurus") is readable. */}
      {data?.lord_type === "chakra" && data?.chakra_refs && (
        <p className="card-note">
          {t("dhasa.chakraRefs", {
            lagna: data.chakra_refs.lagna,
            moon: data.chakra_refs.moon,
            sun: data.chakra_refs.sun,
          })}
        </p>
      )}

      {data?.periods?.length > 0 && (
        <div className="period-list">
          {data.periods.map((p, i) => {
            const current = isCurrentPeriod(p.start_date, p.end_date);
            return (
              <div key={`${p.lord}-${i}`} className={`period-row${current ? " is-current" : ""}`}>
                <span className="fw-700 text-indigo">
                  {p.chakra ? (
                    <span className="chakra-wheels">
                      {["lagna", "moon", "sun"].map((w) => (
                        <span key={w} className={`chakra-wheel chakra-wheel--${w}`}>
                          <span className="chakra-wheel__ref">{t(`dhasa.wheel.${w}`)}</span>
                          {p.chakra[w].sign}
                          <span className="chakra-wheel__house">{p.chakra[w].house}</span>
                        </span>
                      ))}
                    </span>
                  ) : (
                    p.lord
                  )}
                  {current && <span className="period-row__now">{t("dhasa.now")}</span>}
                </span>
                <span className="text-secondary" style={{ fontSize: "0.8125rem" }}>
                  {formatDate(p.start_date, locale)} – {formatDate(p.end_date, locale)}
                </span>
                <span className="text-muted" style={{ fontSize: "0.8125rem" }}>
                  {p.duration_years}y
                </span>
              </div>
            );
          })}
        </div>
      )}
    </Card>
    </div>
  );
}

// ── Sudarsana Chakra: three wheels (Lagna / Moon / Sun as ascendant) ──────────
function SudarsanaChakra({ birthDetails }) {
  const { t } = useTranslation();
  const ln = useLocalizeName();
  const [open, setOpen] = useState(false);
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const { settings } = useSettings();
  const chartStyle = settings.chartStyle;
  const ayanamsa = settings.ayanamsa;
  const Kundali = chartStyle === "south" ? SouthIndianChart : NorthIndianChart;

  const load = useCallback(
    (yr) => {
      if (!birthDetails) return;
      setLoading(true);
      setError("");
      astrologyService
        .getSudarsanaChakra(birthDetails, yr, ayanamsa)
        .then((r) => setData(r.data))
        .catch((e) => setError(e.response?.data?.detail || t("dhasa.sudarsana.loadError")))
        .finally(() => setLoading(false));
    },
    [birthDetails, ayanamsa, t]
  );

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && !data) load(offset);
  };

  const step = (delta) => {
    const next = Math.max(0, offset + delta);
    setOffset(next);
    load(next);
  };

  const wheelLabel = (ref) =>
    ref.startsWith("Lagna")
      ? t("dhasa.sudarsana.wheelLagna")
      : ref.startsWith("Chandra")
        ? t("dhasa.sudarsana.wheelMoon")
        : t("dhasa.sudarsana.wheelSun");

  return (
    <div className="mt-xl">
      <Card title={t("dhasa.sudarsana.title")} icon={<Star size={24} />}>
        <p className="text-secondary" style={{ marginBottom: "var(--space-md)" }}>
          {t("dhasa.sudarsana.intro")}
        </p>
        {!open ? (
          <button className="ui-btn" onClick={toggle}>
            {t("dhasa.sudarsana.show")}
          </button>
        ) : (
          <>
            <div className="page-controls" style={{ marginBottom: "var(--space-md)" }}>
              <div className="controls-group">
                <label className="control-label">{t("dhasa.sudarsana.yearOffset")}</label>
                <div className="stepper">
                  <button
                    className="stepper__btn"
                    onClick={() => step(-1)}
                    disabled={offset <= 0}
                    aria-label="-1"
                  >
                    −
                  </button>
                  <span className="control-input" style={{ minWidth: "6rem", textAlign: "center" }}>
                    {offset === 0
                      ? t("dhasa.sudarsana.natal")
                      : t("dhasa.sudarsana.yearLabel", { year: offset })}
                  </span>
                  <button className="stepper__btn" onClick={() => step(1)} aria-label="+1">
                    +
                  </button>
                </div>
              </div>
              <button className="control-btn" onClick={toggle}>
                {t("dhasa.sudarsana.hide")}
              </button>
            </div>

            <ErrorBanner message={error} />
            {loading && <LoadingState message={t("dhasa.calcPeriods")} />}
            {data && !loading && (
              <div className="sudarsana-wheels">
                {(data.wheels || []).map((w, i) => (
                  <Kundali
                    key={i}
                    planets={data.planets}
                    lagna={{ house: w.lagna_house, sign_name: w.sign_name }}
                    title={wheelLabel(w.ref)}
                    subtitle={ln(w.sign_name, "rasi")}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}

export const DhasaPage = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const { selectedProfile } = useProfile();
  const [dhasaSearchParams] = useSearchParams();

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
      setError(err.response?.data?.detail || t("dhasa.calcError"));
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
        title={t("dhasa.title")}
        subtitle={t("dhasa.subtitle")}
        accent="indigo"
      />

      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />

        <ErrorBanner message={error} />

        {/* System badge + today */}
        <div className="dhasa-badges">
          <div className="dhasa-badge">
            <Clock size={18} style={{ color: "var(--saffron)" }} />
            {t("dhasa.vimsottariSystem")}
            <span className="dhasa-badge__sub">{t("dhasa.cycle120")}</span>
          </div>
          <div className="dhasa-today">
            <Calendar size={16} />
            {t("dhasa.today")}{" "}
            {NOW.toLocaleDateString(locale, { year: "numeric", month: "short", day: "numeric" })}
          </div>
        </div>

        {loading ? (
          <Card>
            <LoadingState message={t("dhasa.loading")} />
          </Card>
        ) : result ? (
          <div className="fade-in">
            {/* Current Period Highlight */}
            {currentMahaDasha && (
              <div className="current-period">
                <div className="current-period__head">
                  <div className="current-period__icon">
                    <Clock size={20} />
                  </div>
                  <h3 style={{ margin: 0, color: "var(--cosmic-indigo)", fontSize: "1.5rem" }}>
                    {t("dhasa.currentPeriod")}
                  </h3>
                </div>
                <div className="current-period__grid">
                  <div>
                    <div className="field-label">{t("dhasa.mahaDasha")}</div>
                    <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--saffron)" }}>
                      {currentMahaDasha.lord}
                    </div>
                  </div>
                  <div>
                    <div className="field-label">{t("dhasa.period")}</div>
                    <div className="fw-600 text-indigo" style={{ fontSize: "0.875rem" }}>
                      {formatDate(currentMahaDasha.start_date, locale)} -{" "}
                      {formatDate(currentMahaDasha.end_date, locale)}
                    </div>
                  </div>
                  {currentSubPeriod && (
                    <div>
                      <div className="field-label">{t("dhasa.currentBhukti")}</div>
                      <div
                        style={{
                          fontSize: "1.125rem",
                          fontWeight: 600,
                          color: "var(--vermillion)",
                        }}
                      >
                        {currentSubPeriod.lord}
                      </div>
                      <div
                        className="text-secondary"
                        style={{ fontSize: "0.75rem", marginTop: "var(--space-xs)" }}
                      >
                        {formatDate(currentSubPeriod.start_date, locale)} -{" "}
                        {formatDate(currentSubPeriod.end_date, locale)}
                      </div>
                    </div>
                  )}
                </div>
                <p
                  className="text-secondary"
                  style={{ margin: "var(--space-lg) 0 0", fontSize: "0.8125rem" }}
                >
                  {t("dhasa.liveHint")}
                </p>
              </div>
            )}

            {/* Full drill-down tree */}
            <div className="ui-card ui-card--accent-indigo ui-card--flush">
              <h3 className="ui-card-header">
                <Star size={24} />
                {t("dhasa.allMaha")}
              </h3>

              {result.dasha_sequence && result.dasha_sequence.length > 0 && (
                <div className="dasha-tree">
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

        {/* Vimsottari above is what "my dasha" means to most people. The other
            14 systems and the three-wheel Sudarshana Chakra are a specialist's
            cross-check — collapsed in Essentials, plain in Everything. */}
        {!loading && result && (
          <AdvancedOnly
            title={t("dhasa.otherSystems")}
            defaultOpen={!!dhasaSearchParams.get("system")}
          >
            <OtherDashaSystems birthDetails={birthDetails} />
            <SudarsanaChakra birthDetails={birthDetails} />
          </AdvancedOnly>
        )}
      </div>
    </div>
  );
};
