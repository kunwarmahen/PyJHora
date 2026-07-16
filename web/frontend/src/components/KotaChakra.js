import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Shield, ShieldAlert } from "lucide-react";
import { astrologyService } from "../services/api";
import { PLANET_ABBR } from "../constants/jyotish";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";

// Kota Chakra — the fort (§2.7). Four concentric enclosures counted from the
// janma nakshatra; a malefic transiting into the inner rings threatens the fort.
// Self-contained (own fetch) so a failure can't blank the host page.
export const KotaChakra = ({ birthDetails, transitDate, transitTime, transitTz, ayanamsa }) => {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!birthDetails) return;
    let cancelled = false;
    setLoading(true);
    setError("");
    astrologyService
      .getKotaChakra(birthDetails, {
        currentDate: transitDate,
        currentTime: transitTime,
        currentTz: transitTz,
        ayanamsa,
      })
      .then((r) => !cancelled && setData(r.data))
      .catch((err) => !cancelled && setError(err.response?.data?.detail || t("kota.error")))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [birthDetails, transitDate, transitTime, transitTz, ayanamsa, t]);

  if (loading) return <LoadingState message={t("kota.loading")} />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  return (
    <div className="fade-in">
      <p className="card-note">{t("kota.intro")}</p>

      <div className="info-pills">
        <span className="info-pill">
          {t("kota.birthStar")}:{" "}
          <strong className="text-saffron">
            {data.birth_star.name} ({t("kota.pada")} {data.birth_star.pada})
          </strong>
        </span>
        <span className="info-pill">
          {t("kota.swami")}: <strong className="text-indigo">{data.kota_lord}</strong>
        </span>
        <span className="info-pill">
          {t("kota.paala")}: <strong className="text-indigo">{data.kota_paala}</strong>
        </span>
      </div>

      {/* Rings, outermost first — the way an approach on the fort reads. */}
      <div className="kota-rings">
        {data.rings.map((ring, depth) => (
          <div key={ring.key} className={`kota-ring kota-ring--${ring.key}`}>
            <div className="kota-ring__head">
              <span className="kota-ring__name">{t(`kota.rings.${ring.key}`, ring.name)}</span>
              <span className="kota-ring__depth">{t("kota.ringDepth", { n: depth + 1 })}</span>
            </div>
            <p className="kota-ring__blurb">{ring.description}</p>
            <div className="kota-cells">
              {ring.cells.map((c) => (
                <div
                  key={c.star}
                  className={`kota-cell${c.transit.length ? " is-occupied" : ""}`}
                  title={c.natal.length ? `${t("kota.natal")}: ${c.natal.join(", ")}` : undefined}
                >
                  <span className="kota-cell__star">{c.star}</span>
                  {c.transit.length > 0 && (
                    <span className="kota-cell__planets">
                      {c.transit.map((p) => (
                        <span
                          key={p.name}
                          className={`kota-graha${p.malefic ? " is-malefic" : " is-benefic"}`}
                          title={p.name}
                        >
                          {PLANET_ABBR[p.name] || p.name}
                          {p.retrograde ? "℞" : ""}
                        </span>
                      ))}
                    </span>
                  )}
                  {c.natal.length > 0 && (
                    <span className="kota-cell__natal">
                      {c.natal.map((n) => PLANET_ABBR[n] || n).join(" ")}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {data.findings?.length > 0 && (
        <div className="ui-card ui-card--pad-lg mt-xl">
          <h4 className="ui-card-header ui-card-header--sm">
            <ShieldAlert size={18} />
            {t("kota.findings")}
          </h4>
          <ul className="detail-list">
            {data.findings.map((f, i) => (
              <li key={i} className={`kota-finding kota-finding--${f.tone}`}>
                {f.tone === "supportive" ? <Shield size={14} /> : <ShieldAlert size={14} />} {f.text}
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="card-note">{t("kota.legend")}</p>
    </div>
  );
};
