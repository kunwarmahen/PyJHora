import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { Target, Check, X } from "lucide-react";
import { astrologyService } from "../services/api";
import { todayISO } from "../utils/format";
import { VERDICTS } from "../config/outcomes";
import "../styles/Outcome.css";


const CATEGORIES = [
  "career", "relationship", "family", "health", "finance",
  "move", "education", "spiritual", "loss", "milestone", "other",
];

export const VerdictChip = ({ verdict }) => {
  const { t } = useTranslation();
  if (!verdict) return null;
  return (
    <span className={`outcome-chip outcome-chip--${verdict}`}>
      <Target size={11} style={{ verticalAlign: "-1px" }} />{" "}
      {t(`outcome.verdict.${verdict}`)}
    </span>
  );
};

/**
 * "Did this land?" on one saved reading (§68.7) — the join between a prediction
 * and what actually happened.
 *
 * This is not the thumbs up/down on a chat message: that rates the *answer* as it
 * arrives, this rates the *prediction* months later, against a life. The optional
 * journal half writes an astro-journal entry in the same request, so the verdict
 * and the life-event it refers to can never be half-saved against each other.
 *
 * Rendered inside a clickable history row, so every interaction stops propagation
 * — clicking "partly" must not also reopen the reading.
 */
export const OutcomeControl = ({ item, profileId, onSaved }) => {
  const { t } = useTranslation();
  const existing = item.outcome || null;

  const [open, setOpen] = useState(false);
  const [verdict, setVerdict] = useState(existing?.verdict || "");
  const [note, setNote] = useState(existing?.note || "");
  const [withJournal, setWithJournal] = useState(false);
  const [jDate, setJDate] = useState(existing?.outcome_date || todayISO());
  const [jTitle, setJTitle] = useState("");
  const [jCategory, setJCategory] = useState("milestone");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const stop = (e) => e.stopPropagation();

  const expand = (e) => {
    stop(e);
    setVerdict(existing?.verdict || "");
    setNote(existing?.note || "");
    setJTitle(item.title || "");
    setWithJournal(false);
    setError("");
    setOpen(true);
  };

  const save = async (e) => {
    stop(e);
    if (!verdict) return;
    setSaving(true);
    setError("");
    try {
      const payload = { verdict, note, outcome_date: jDate, profile_id: profileId || item.profile_id };
      // Only send the journal half when the user asked for it AND gave it a
      // title — an untitled entry is rejected by the journal itself.
      if (withJournal && jTitle.trim()) {
        payload.journal = {
          date: jDate,
          title: jTitle.trim(),
          category: jCategory,
          notes: note,
          profile_id: profileId || item.profile_id,
        };
      }
      const { data } = await astrologyService.setReadingOutcome(item.id, payload);
      setOpen(false);
      if (onSaved) onSaved(item.id, data);
    } catch (err) {
      setError(err.response?.data?.detail || t("outcome.saveError"));
    } finally {
      setSaving(false);
    }
  };

  const clear = async (e) => {
    stop(e);
    setSaving(true);
    try {
      await astrologyService.clearReadingOutcome(item.id);
      setOpen(false);
      if (onSaved) onSaved(item.id, null);
    } catch (err) {
      setError(err.response?.data?.detail || t("outcome.saveError"));
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return (
      <button className="outcome-trigger" onClick={expand} title={t("outcome.ask")}>
        {existing ? (
          <VerdictChip verdict={existing.verdict} />
        ) : (
          <>
            <Target size={12} style={{ verticalAlign: "-1px" }} /> {t("outcome.ask")}
          </>
        )}
      </button>
    );
  }

  return (
    <div className="outcome-editor" onClick={stop}>
      <div className="outcome-editor__head">
        <strong>{t("outcome.ask")}</strong>
        <button className="outcome-x" onClick={(e) => { stop(e); setOpen(false); }}
                title={t("outcome.cancel")}>
          <X size={14} />
        </button>
      </div>

      <div className="outcome-verdicts">
        {VERDICTS.map((v) => (
          <button
            key={v}
            type="button"
            className={`outcome-verdict outcome-verdict--${v}${verdict === v ? " is-active" : ""}`}
            onClick={(e) => { stop(e); setVerdict(v); }}
            aria-pressed={verdict === v}
          >
            {verdict === v ? <Check size={12} style={{ verticalAlign: "-1px" }} /> : null}{" "}
            {t(`outcome.verdict.${v}`)}
          </button>
        ))}
      </div>

      <label className="outcome-field">
        <span>{t("outcome.noteLabel")}</span>
        <textarea
          rows={3}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder={t("outcome.notePlaceholder")}
        />
      </label>

      <label className="outcome-field outcome-field--row">
        <span>{t("outcome.whenLabel")}</span>
        <input type="date" value={jDate} onChange={(e) => setJDate(e.target.value)} />
      </label>

      <label className="outcome-check">
        <input
          type="checkbox"
          checked={withJournal}
          onChange={(e) => setWithJournal(e.target.checked)}
        />
        <span>{t("outcome.addJournal")}</span>
      </label>

      {withJournal && (
        <div className="outcome-journal">
          <label className="outcome-field">
            <span>{t("outcome.journalTitle")}</span>
            <input
              value={jTitle}
              onChange={(e) => setJTitle(e.target.value)}
              placeholder={t("outcome.journalTitlePlaceholder")}
            />
          </label>
          <label className="outcome-field outcome-field--row">
            <span>{t("outcome.journalCategory")}</span>
            <select value={jCategory} onChange={(e) => setJCategory(e.target.value)}>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>{t(`journal.cat.${c}`)}</option>
              ))}
            </select>
          </label>
          <p className="outcome-hint">{t("outcome.journalHint")}</p>
        </div>
      )}

      {error && <p className="outcome-error">{error}</p>}

      <div className="outcome-actions">
        <button className="outcome-save" onClick={save} disabled={!verdict || saving}>
          {saving ? t("outcome.saving") : t("outcome.save")}
        </button>
        {existing && (
          <button className="outcome-clear" onClick={clear} disabled={saving}>
            {t("outcome.clear")}
          </button>
        )}
      </div>
    </div>
  );
};
