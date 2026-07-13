import React, { useState, useCallback, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown, AlertCircle } from "lucide-react";
import { astrologyService } from "../services/api";

// Maha → Antara → Pratyantara → Sookshma → Prana → Deha. The backend indexes
// these 0-5 and refuses to go deeper (8^6 ≈ 262k periods), so `has_children`
// on the last level is false and the node renders as a leaf.
const LEVELS = [
  { labelKey: "varshaphal.taMaha", accent: "var(--saffron)" },
  { labelKey: "varshaphal.taAntara", accent: "var(--cosmic-indigo)" },
  { labelKey: "varshaphal.taPratyantara", accent: "var(--vermillion)" },
  { labelKey: "varshaphal.taSookshma", accent: "var(--terracotta)" },
  { labelKey: "varshaphal.taPrana", accent: "var(--cosmic-indigo)" },
  { labelKey: "varshaphal.taDeha", accent: "var(--vermillion)" },
];

/** Periods here carry a real time of day — a Deha period can be under a minute —
 *  so they are never rendered as a bare date. */
const formatMoment = (iso, locale) => {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

/** Spans run from ~74 days at the top to well under a minute at the bottom, so
 *  the unit has to follow the depth or the deep levels all read "0 days". */
const formatSpan = (days, t) => {
  if (days == null) return "";
  if (days >= 1) return t("varshaphal.taDays", { count: Math.round(days * 100) / 100 });
  const hours = days * 24;
  if (hours >= 1) return t("varshaphal.taHours", { count: Math.round(hours * 10) / 10 });
  return t("varshaphal.taMinutes", { count: Math.round(hours * 60) });
};

function TithiAshtottariNode({ node, birthDetails }) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "hi" ? "hi-IN" : "en-US";
  const level = node.level ?? 0;
  const meta = LEVELS[Math.min(level, LEVELS.length - 1)];
  const canExpand = !!node.has_children;

  const [expanded, setExpanded] = useState(false);
  const [children, setChildren] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchChildren = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      // A period is fully described by its start instant, lord and *degree* span,
      // so a child level needs nothing else — no re-derivation from the pravesha
      // moment, and no state held between expands.
      const res = await astrologyService.getTithiAshtottariChildren({
        start_jd: node.start_jd,
        lord: node.lord,
        span_deg: node.span_deg,
        level,
        latitude: birthDetails.latitude,
        longitude: birthDetails.longitude,
        timezone: birthDetails.timezone,
        place: birthDetails.place || "",
      });
      setChildren(res.data.periods || []);
    } catch (e) {
      setError(e.response?.data?.detail || t("varshaphal.taChildrenError"));
    } finally {
      setLoading(false);
    }
  }, [node, level, birthDetails, t]);

  useEffect(() => {
    if (expanded && canExpand && children == null && !loading) fetchChildren();
  }, [expanded, canExpand, children, loading, fetchChildren]);

  const indent = level === 0 ? 0 : 16;
  const avatar = level === 0 ? 40 : level === 1 ? 34 : 28;
  const lordSize = level === 0 ? "1.125rem" : level === 1 ? "1rem" : "0.9375rem";

  return (
    <div
      className={`dasha-node${level === 0 ? " dasha-node--root" : ""}${node.current ? " is-current" : ""}`}
      style={{ marginLeft: indent, "--lvl-accent": meta.accent, "--avatar": `${avatar}px` }}
    >
      <div
        onClick={() => canExpand && setExpanded((v) => !v)}
        className={`dasha-node__head${canExpand ? " is-expandable" : ""}`}
      >
        <div className="dasha-node__avatar">{(node.lord_name || "?").slice(0, 2)}</div>

        <div>
          <div className="dasha-node__lord" style={{ fontSize: lordSize }}>
            {node.lord_name}
            <span className="dasha-node__level">{t(meta.labelKey)}</span>
          </div>
          <div className="dasha-node__dates">
            {formatSpan(node.span_days, t)}
            <span>
              {" "}
              • {formatMoment(node.start, locale)} to {formatMoment(node.end, locale)}
            </span>
          </div>
        </div>

        {node.current && <div className="dasha-node__now">{t("varshaphal.current")}</div>}

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
              {t("varshaphal.taLoadingChildren")}
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
            children.map((child, i) => (
              <TithiAshtottariNode
                key={`${child.lord}-${i}`}
                node={child}
                birthDetails={birthDetails}
              />
            ))}
        </div>
      )}
    </div>
  );
}

/**
 * The compressed Tithi Ashtottari of a Tithi Pravesha chart, as an expandable
 * tree (Maha → Antara → Pratyantara → Sookshma → Prana → Deha).
 *
 * Levels are fetched on expand rather than shipped with the chart: six levels is
 * 8^6 ≈ 262k periods, and the deepest of them last under a minute.
 */
export function TithiAshtottariTree({ periods, birthDetails }) {
  return (
    <div className="dasha-tree">
      {periods.map((p, i) => (
        <TithiAshtottariNode key={`${p.lord}-${i}`} node={p} birthDetails={birthDetails} />
      ))}
    </div>
  );
}
