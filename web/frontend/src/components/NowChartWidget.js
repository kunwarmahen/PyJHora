import React, { useState, useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Globe, ChevronRight } from "lucide-react";
import { astrologyService } from "../services/api";
import { useCurrentLocation } from "../contexts/LocationContext";
import { useProfile } from "../contexts/ProfileContext";
import { NorthIndianChart } from "./NorthIndianChart";
import { SouthIndianChart } from "./SouthIndianChart";
import { useSettings } from "../contexts/SettingsContext";
import { isFeatureVisible } from "../config/features";
import { momentPlace } from "../config/currentLocation";
import { useLocalizeName } from "../i18n/localizeName";

/**
 * A compact "chart of the moment" tile for the Dashboard: the current sky as a
 * small kundali, tapping the same compute as the full /now page it links to.
 *
 * **It shows only in Everything mode.** `/now` is a `tier: "advanced"` feature,
 * so the drawer and the tiles already hide it in Essentials — but this widget
 * sat above the fold for everyone regardless, which meant the registry said
 * "advanced" and the Dashboard said "first thing you see". One source of truth:
 * it asks `isFeatureVisible` the same question every other surface asks.
 *
 * **It uses the stored viewer location, never the browser's GPS.** It used to
 * call `navigator.geolocation` on every dashboard mount — a permission prompt
 * raised by a widget nobody had asked for — and then fall back to the birth
 * place when that was denied, silently casting "the moment" for a city the
 * reader isn't standing in. `momentPlace` resolves that the way the rest of the
 * app does, and the place it picked is printed next to the timestamp, because
 * on this chart in particular the meridian IS the answer.
 */
export const NowChartWidget = () => {
  const { t } = useTranslation();
  const ln = useLocalizeName();
  const { location, loaded: locationLoaded } = useCurrentLocation();
  const { selectedProfile } = useProfile();
  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;
  const visible = isFeatureVisible("/now", settings.uiMode);
  const Kundali = settings.chartStyle === "south" ? SouthIndianChart : NorthIndianChart;

  const [data, setData] = useState(null);

  // Nothing until the stored location has actually been fetched. "Not loaded
  // yet" looks exactly like "there is none", and acting on the difference cast
  // the birth-place chart first and replaced it a beat later — a visible flash
  // of the wrong sky, plus a wasted call.
  const here = useMemo(
    () => (locationLoaded ? momentPlace(location, selectedProfile?.birth_details) : null),
    [locationLoaded, location, selectedProfile]
  );

  useEffect(() => {
    if (!visible || !here) {
      setData(null);
      return undefined;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await astrologyService.getNowChart({
          place: here.place,
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
  }, [visible, here, ayanamsa]);

  // `here` is re-checked, not assumed from `data`: losing the location
  // re-renders before the effect can clear the last chart.
  if (!visible || !here || !data) return null;

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
            {here.place
              ? ` · ${t(here.source === "birth" ? "now.castForBirth" : "now.castFor", {
                  place: here.place,
                })}`
              : ""}
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
