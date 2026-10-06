import React from "react";
import { useTranslation } from "react-i18next";
import { Sunrise, Moon, Star, BookOpen, Sparkles } from "lucide-react";
import { useLocalizeName } from "../i18n/localizeName";
import { intlLocale, parseLocalDate } from "../utils/format";
import { GlossaryTerm } from "./GlossaryTerm";
import "../styles/FirstLook.css";

/**
 * "Your chart in plain words" (§76.3) — the four things a newcomer can grasp in
 * a minute, rendered from the backend's `get_first_look` payload.
 *
 * Every sentence comes from the i18n tables keyed by sign number, star number or
 * planet (`firstLook.rising.<1-12>`, `.moon.<1-12>`, `.stars.<1-27>`,
 * `.chapter.<Planet>`), never from a model, so the screen is instant, costs
 * nothing, and translates like the rest of the app. Each card leads with the
 * plain name ("Moon sign") and shows the Sanskrit one beside it, never alone.
 *
 * Used twice: the signed-in /start page and the landing page's anonymous
 * preview. `footer` is where each puts its own next step (Ask, or sign up).
 */
export const FirstLook = ({ data, footer }) => {
  const { t, i18n } = useTranslation();
  const ln = useLocalizeName();
  if (!data) return null;
  const { rising, moon, chapter } = data;
  const fmt = (iso) =>
    iso
      ? parseLocalDate(iso).toLocaleDateString(intlLocale(i18n.language), {
          year: "numeric",
          month: "long",
          day: "numeric",
        })
      : "";
  const star = moon?.nakshatra_index
    ? t(`firstLook.stars.${moon.nakshatra_index}`, { returnObjects: true })
    : null;
  const range = moon?.day_range;

  return (
    <div className="first-look">
      <p className="first-look__intro">{t("firstLook.intro")}</p>

      <div className="first-look__cards">
        {/* Rising sign */}
        <section className="first-look__card" aria-labelledby="fl-rising">
          <header>
            <Sunrise size={22} aria-hidden="true" />
            <h2 id="fl-rising">
              {t("firstLook.risingLabel")}{" "}
              <span className="first-look__term">
                <GlossaryTerm term="Lagna">{t("firstLook.risingTerm")}</GlossaryTerm>
              </span>
            </h2>
          </header>
          {rising ? (
            <>
              <p className="first-look__sign">{ln(rising.sign_name, "rasi")}</p>
              <p>{t(`firstLook.rising.${rising.sign_num}`)}</p>
              {rising.near_edge && <p className="first-look__caveat">{t("firstLook.nearEdge")}</p>}
            </>
          ) : (
            <p className="first-look__caveat">{t("firstLook.noTimeRising")}</p>
          )}
          <p className="first-look__what">{t("firstLook.risingWhat")}</p>
        </section>

        {/* Moon sign */}
        <section className="first-look__card" aria-labelledby="fl-moon">
          <header>
            <Moon size={22} aria-hidden="true" />
            <h2 id="fl-moon">
              {t("firstLook.moonLabel")}{" "}
              <span className="first-look__term">
                <GlossaryTerm term="Rasi">{t("firstLook.moonTerm")}</GlossaryTerm>
              </span>
            </h2>
          </header>
          {moon.sign_certain ? (
            <>
              <p className="first-look__sign">{ln(moon.sign_name, "rasi")}</p>
              <p>{t(`firstLook.moon.${moon.sign_num}`)}</p>
            </>
          ) : (
            <p className="first-look__caveat">
              {t("firstLook.moonUnsure", {
                from: ln(range?.start?.sign_name, "rasi"),
                to: ln(range?.end?.sign_name, "rasi"),
              })}
            </p>
          )}
          <p className="first-look__what">{t("firstLook.moonWhat")}</p>
        </section>

        {/* Birth star */}
        <section className="first-look__card" aria-labelledby="fl-star">
          <header>
            <Star size={22} aria-hidden="true" />
            <h2 id="fl-star">
              {t("firstLook.starLabel")}{" "}
              <span className="first-look__term">
                <GlossaryTerm term="Nakshatra">{t("firstLook.starTerm")}</GlossaryTerm>
              </span>
            </h2>
          </header>
          {moon.star_certain && star ? (
            <>
              <p className="first-look__sign">
                {ln(moon.nakshatra, "nakshatra")}{" "}
                <small>{t("firstLook.padaNote", { pada: moon.pada })}</small>
              </p>
              <p>
                {t("firstLook.starLine", {
                  // "Royal throne" reads as "its symbol is a royal throne" mid-sentence;
                  // deities stay capitalised — they are names.
                  symbol: star.symbol.charAt(0).toLowerCase() + star.symbol.slice(1),
                  deity: star.deity,
                  theme: star.theme.toLowerCase(),
                })}
              </p>
            </>
          ) : (
            <p className="first-look__caveat">
              {t("firstLook.starUnsure", {
                from: ln(range?.start?.nakshatra, "nakshatra"),
                to: ln(range?.end?.nakshatra, "nakshatra"),
              })}
            </p>
          )}
          <p className="first-look__what">{t("firstLook.starWhat")}</p>
        </section>
      </div>

      {/* The chapter you're in now */}
      {chapter?.maha && (
        <section className="first-look__chapter" aria-labelledby="fl-chapter">
          <header>
            <BookOpen size={22} aria-hidden="true" />
            <h2 id="fl-chapter">
              {t("firstLook.chapterLabel")}{" "}
              <span className="first-look__term">
                <GlossaryTerm term="Dasha">{t("firstLook.chapterTerm")}</GlossaryTerm>
              </span>
            </h2>
          </header>
          {/* The dasha sequence starts from the birth star's lord, so when the
              star itself is unknown the chapter's planet is too — not just its
              dates. Say that instead of naming a period that may be wrong. */}
          {moon.star_certain ? (
            <>
              <p className="first-look__chapter-lead">
                {t("firstLook.chapterLine", {
                  lord: ln(chapter.maha.lord, "graha"),
                  start: fmt(chapter.maha.start_date),
                  end: fmt(chapter.maha.end_date),
                  theme: t(`firstLook.chapter.${chapter.maha.lord}`),
                })}
              </p>
              {chapter.antar && (
                <p>
                  {t("firstLook.subLine", {
                    lord: ln(chapter.antar.lord, "graha"),
                    end: fmt(chapter.antar.end_date),
                    theme: t(`firstLook.chapterShort.${chapter.antar.lord}`),
                  })}
                </p>
              )}
              {chapter.next_antar && (
                <p className="first-look__next">
                  {t("firstLook.nextLine", {
                    lord: ln(chapter.next_antar.lord, "graha"),
                    start: fmt(chapter.next_antar.start_date),
                  })}
                </p>
              )}
              {chapter.approximate && (
                <p className="first-look__caveat">{t("firstLook.approximate")}</p>
              )}
            </>
          ) : (
            <p className="first-look__caveat">{t("firstLook.chapterUnsure")}</p>
          )}
          <p className="first-look__what">{t("firstLook.chapterWhat")}</p>
        </section>
      )}

      {footer}

      <p className="first-look__honest">
        <Sparkles size={14} aria-hidden="true" /> {t("firstLook.honest")}
      </p>
    </div>
  );
};

export default FirstLook;
