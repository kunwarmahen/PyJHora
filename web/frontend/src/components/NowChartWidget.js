import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Globe, ChevronRight } from "lucide-react";
import { astrologyService } from "../services/api";
import { useProfile } from "../contexts/ProfileContext";
import { NorthIndianChart } from "./NorthIndianChart";
import { SouthIndianChart } from "./SouthIndianChart";
import { useSettings } from "../contexts/SettingsContext";
import { useLocalizeName } from "../i18n/localizeName";

const browserLocation = () =>
  new Promise((resolve) => {
    if (!navigator.geolocation) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        resolve({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          timezone: -new Date().getTimezoneOffset() / 60,
        }),
      () => resolve(null),
      { timeout: 8000 }
    );
  });

// A compact "chart of the moment" tile for the Dashboard: the current sky as a
// small kundali, tapping the transit/now compute already built. Links to the
// full /now page. Self-contained: its own fetch, silent on failure so it can
// never blank the dashboard.
export const NowChartWidget = () => {
  const { t } = useTranslation();
  const ln = useLocalizeName();
  const { selectedProfile } = useProfile();
  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;
  const Kundali = settings.chartStyle === "south" ? SouthIndianChart : NorthIndianChart;

  const [data, setData] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const here =
          (await browserLocation()) ||
          (selectedProfile
            ? {
                latitude: selectedProfile.birth_details.latitude,
                longitude: selectedProfile.birth_details.longitude,
                timezone: selectedProfile.birth_details.timezone,
              }
            : {});
        const res = await astrologyService.getNowChart({
          latitude: here.latitude,
          longitude: here.longitude,
          timezone: here.timezone,
          currentTz: here.timezone,
          ayanamsa,
        });
        if (!cancelled && res.data?.status === "success") setData(res.data);
      } catch (e) {
        /* silent — the widget is a convenience, not core */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedProfile, ayanamsa]);

  if (!data) return null;

  const panch = data.panchanga || {};

  return (
    <Link to="/now" className="now-widget fade-in">
      <div className="now-widget__chart">
        <Kundali
          planets={data.planets}
          lagna={data.lagna}
          title={t("now.chartTitle")}
          subtitle=""
        />
      </div>
      <div className="now-widget__body">
        <div className="now-widget__head">
          <Globe size={18} />
          <span>{t("now.widgetTitle")}</span>
        </div>
        {data.moment && (
          <p className="now-widget__moment">
            {t("now.asOf", { date: data.moment.date, time: data.moment.time })}
          </p>
        )}
        <div className="now-widget__pills">
          {panch.vaara?.name && <span className="info-pill">{panch.vaara.name}</span>}
          {panch.tithi?.name && <span className="info-pill">{panch.tithi.name}</span>}
          {panch.nakshatra?.name && (
            <span className="info-pill">{ln(panch.nakshatra.name, "nakshatra")}</span>
          )}
        </div>
        <span className="now-widget__cta">
          {t("now.widgetCta")} <ChevronRight size={16} />
        </span>
      </div>
    </Link>
  );
};

export default NowChartWidget;
