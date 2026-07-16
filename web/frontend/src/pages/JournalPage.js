import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { BookText, Plus, Pencil, Trash2, Clock } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { Card } from "../components/Card";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { useSettings } from "../contexts/SettingsContext";
import { intlLocale } from "../utils/format";
import "../styles/Dashboard.css";
import "../styles/Shared.css";
import "../styles/Journal.css";

const fmt = (dateStr, locale) => {
  try {
    return new Date(`${dateStr}T00:00:00`).toLocaleDateString(locale, {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
};

const CATEGORIES = [
  "career", "relationship", "family", "health", "finance",
  "move", "education", "spiritual", "loss", "milestone", "other",
];

const emptyForm = () => ({
  id: null,
  date: new Date().toISOString().slice(0, 10),
  title: "",
  category: "milestone",
  notes: "",
});

export const JournalPage = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const { selectedProfile } = useProfile();
  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;

  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [form, setForm] = useState(emptyForm());
  const [saving, setSaving] = useState(false);

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

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await astrologyService.listJournal(selectedProfile?._id);
      setEntries(res.data?.entries || []);
    } catch (err) {
      setError(err.response?.data?.detail || t("journal.loadError"));
    } finally {
      setLoading(false);
    }
  }, [selectedProfile, t]);

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    load();
  }, [selectedProfile, navigate, load]);

  const save = async (e) => {
    e.preventDefault();
    if (!form.title.trim()) return;
    setSaving(true);
    setError("");
    try {
      const payload = {
        profile_id: selectedProfile?._id,
        birth_details: birthDetails,
        date: form.date,
        title: form.title,
        category: form.category,
        notes: form.notes,
        ayanamsa,
      };
      if (form.id) {
        await astrologyService.updateJournal(form.id, payload);
      } else {
        await astrologyService.createJournal(payload);
      }
      setForm(emptyForm());
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || t("journal.saveError"));
    } finally {
      setSaving(false);
    }
  };

  const edit = (entry) => {
    setForm({
      id: entry.id,
      date: entry.date,
      title: entry.title,
      category: entry.category,
      notes: entry.notes || "",
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const remove = async (entry) => {
    if (!window.confirm(t("journal.deleteConfirm"))) return;
    setError("");
    try {
      await astrologyService.deleteJournal(entry.id);
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || t("journal.deleteError"));
    }
  };

  if (!selectedProfile) return null;

  const dashaText = (d) =>
    d && d.maha ? d.maha + (d.bhukti ? `/${d.bhukti}` : "") : null;

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<BookText size={24} />}
        title={t("journal.title")}
        subtitle={t("journal.subtitle")}
        accent="terracotta"
      />

      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />
        <p className="card-note">{t("journal.intro")}</p>

        <ErrorBanner message={error} />

        {/* Editor */}
        <Card title={form.id ? t("journal.editTitle") : t("journal.addTitle")} icon={<Plus size={22} />} accent="terracotta">
          <form className="jrn-form" onSubmit={save}>
            <div className="jrn-form__row">
              <label className="jrn-field">
                <span>{t("journal.fieldDate")}</span>
                <input
                  type="date"
                  value={form.date}
                  onChange={(e) => setForm({ ...form, date: e.target.value })}
                  required
                />
              </label>
              <label className="jrn-field">
                <span>{t("journal.fieldCategory")}</span>
                <select
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                >
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {t(`journal.cat.${c}`)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="jrn-field">
              <span>{t("journal.fieldTitle")}</span>
              <input
                type="text"
                value={form.title}
                placeholder={t("journal.titlePlaceholder")}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                required
              />
            </label>
            <label className="jrn-field">
              <span>{t("journal.fieldNotes")}</span>
              <textarea
                rows={3}
                value={form.notes}
                placeholder={t("journal.notesPlaceholder")}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
              />
            </label>
            <div className="jrn-form__actions">
              {form.id && (
                <button type="button" className="ui-btn ui-btn--ghost" onClick={() => setForm(emptyForm())}>
                  {t("journal.cancel")}
                </button>
              )}
              <button type="submit" className="ui-btn" disabled={saving}>
                {saving ? t("journal.saving") : t("journal.save")}
              </button>
            </div>
          </form>
        </Card>

        {/* Timeline list */}
        <div className="mt-xl">
          {loading ? (
            <Card>
              <LoadingState message={t("journal.loading")} />
            </Card>
          ) : entries.length === 0 ? (
            <p className="card-note">{t("journal.empty")}</p>
          ) : (
            <div className="jrn-list">
              {entries.map((e) => (
                <div className="jrn-entry" key={e.id}>
                  <div className="jrn-entry__date">{fmt(e.date, locale)}</div>
                  <div className="jrn-entry__body">
                    <div className="jrn-entry__top">
                      <span className={`jrn-cat jrn-cat--${e.category}`}>{t(`journal.cat.${e.category}`)}</span>
                      <span className="jrn-entry__title">{e.title}</span>
                    </div>
                    {e.notes && <p className="jrn-entry__notes">{e.notes}</p>}
                    {dashaText(e.dasha) && (
                      <div className="jrn-entry__dasha">
                        <Clock size={14} />
                        {t("journal.running", { dasha: dashaText(e.dasha) })}
                      </div>
                    )}
                  </div>
                  <div className="jrn-entry__actions">
                    <button className="jrn-icon-btn" onClick={() => edit(e)} aria-label={t("journal.edit")}>
                      <Pencil size={16} />
                    </button>
                    <button className="jrn-icon-btn jrn-icon-btn--danger" onClick={() => remove(e)} aria-label={t("journal.delete")}>
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default JournalPage;
