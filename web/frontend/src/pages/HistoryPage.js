import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { History, Trash2, MessageCircle, Sparkles, User, Mail } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { PageHeader } from "../components/PageHeader";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { intlLocale } from "../utils/format";
import "../styles/Dashboard.css";
import "../styles/Shared.css";
import "../styles/Chat.css";

// A digest that was delivered by email or push is a third kind alongside chats and
// one-shot readings — it wasn't asked for, it arrived. It gets its own icon and
// filter so "the reading I was sent this morning" is findable as such.
const kindIcon = (kind) => {
  if (kind === "chat") return <MessageCircle size={12} style={{ verticalAlign: "-1px" }} />;
  if (kind === "digest") return <Mail size={12} style={{ verticalAlign: "-1px" }} />;
  return <Sparkles size={12} style={{ verticalAlign: "-1px" }} />;
};

// The unified AI history: every chat + saved reading across all tools, plus the
// digests actually delivered. Clicking an item deep-links back to the tool that
// produced it and re-shows the exact reading.
export const HistoryPage = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const { profiles, selectProfile, loadProfiles } = useProfile();

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all"); // all | chat | reading | digest

  const fmt = (iso) => {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleString(locale, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (e) {
      return "";
    }
  };

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const resp = await astrologyService.listHistory();
      setItems(resp.data.conversations || []);
    } catch (err) {
      setError(err.response?.data?.detail || t("history.loadError"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    load();
    // The provider only auto-loads the *selected* profile, so pull the full list
    // here — needed to label groups by profile and to switch to a reading's
    // profile before opening it.
    if (profiles.length === 0 && loadProfiles) loadProfiles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  const profileName = useCallback(
    (pid) => {
      if (!pid) return null;
      const p = profiles.find((x) => x._id === pid);
      return p?.profile_name || p?.birth_details?.name || null;
    },
    [profiles]
  );

  const open = (item) => {
    // Restore the reading under the profile it was made for, so the target page
    // recomputes for the right chart before showing the saved snapshot.
    if (item.profile_id) {
      const p = profiles.find((x) => x._id === item.profile_id);
      if (p) selectProfile(p);
    }
    const route = item.route || "/ask-astrologer";
    navigate(`${route}?reading=${item.id}`);
  };

  const remove = async (id, e) => {
    e.stopPropagation();
    try {
      await astrologyService.deleteConversation(id);
      setItems((prev) => prev.filter((c) => c.id !== id));
    } catch (err) {
      setError(err.response?.data?.detail || t("history.deleteError"));
    }
  };

  const visible = useMemo(
    () => items.filter((c) => filter === "all" || (c.kind || "reading") === filter),
    [items, filter]
  );

  // Group by profile (with a "No profile" bucket for location-driven tools), each
  // group ordered by the backend's newest-first list order.
  const groups = useMemo(() => {
    const map = new Map();
    for (const c of visible) {
      const key = c.profile_id || "__none__";
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(c);
    }
    return Array.from(map.entries()).map(([key, list]) => ({
      key,
      name:
        key === "__none__" ? t("history.noProfile") : profileName(key) || t("history.noProfile"),
      list,
    }));
  }, [visible, profileName, t]);

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<History size={24} />}
        title={t("history.title")}
        subtitle={t("history.subtitle")}
        accent="gold"
      />

      <div className="dashboard-content">
        <ErrorBanner message={error} />

        <div className="history-filters" style={{ marginBottom: "1rem" }}>
          {["all", "chat", "reading", "digest"].map((f) => (
            <button
              key={f}
              className={`history-filter${filter === f ? " is-active" : ""}`}
              onClick={() => setFilter(f)}
            >
              {t(`history.filter.${f}`)}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="ui-card ui-card--pad-lg">
            <LoadingState message={t("history.loading")} />
          </div>
        ) : visible.length === 0 ? (
          <div className="ui-card ui-card--pad-lg">
            <p className="text-secondary" style={{ margin: 0 }}>
              {t("history.empty")}
            </p>
          </div>
        ) : (
          groups.map((g) => (
            <div key={g.key} className="ui-card ui-card--accent ui-card--flush mb-xl">
              <h3 className="ui-card-header ui-card-header--sm">
                <User size={18} />
                {g.name}
                <span className="text-muted" style={{ fontWeight: 400, marginLeft: "0.4rem" }}>
                  ({g.list.length})
                </span>
              </h3>
              <div className="history-list">
                {g.list.map((c) => (
                  <div key={c.id} className="history-item" onClick={() => open(c)}>
                    <div className="history-item__main">
                      <div className="history-item__title">
                        <span className="history-source-badge">
                          {kindIcon(c.kind)} {c.label || c.source}
                        </span>
                        {c.title}
                      </div>
                      {c.preview && <div className="history-item__preview">{c.preview}…</div>}
                      <div className="history-item__meta">
                        {c.kind === "digest" && c.delivered?.email ? (
                          <>
                            <Mail size={11} style={{ verticalAlign: "-1px" }} />{" "}
                            {t("history.deliveredEmail")} ·{" "}
                          </>
                        ) : null}
                        {c.last_model ? `${c.last_model} · ` : ""}
                        {fmt(c.updated_at)}
                      </div>
                    </div>
                    <button
                      className="history-item__delete"
                      onClick={(e) => remove(c.id, e)}
                      title={t("history.delete")}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
