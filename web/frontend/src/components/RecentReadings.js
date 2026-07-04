import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { History, ChevronDown, Trash2 } from "lucide-react";
import { astrologyService } from "../services/api";
import { intlLocale } from "../utils/format";
import "../styles/Chat.css";

// A compact, collapsible "Recent readings" panel for a single tool page. It lists
// this tool's own saved AI readings (filtered by `source`, optionally by profile)
// and reopens one in place by deep-linking `?reading=<id>` on the current page —
// the page's useRestoreReading hook then restores the inputs + saved snapshot.
// Renders nothing when the tool has no saved readings yet.
export const RecentReadings = ({ source, profileId, limit = 8 }) => {
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const navigate = useNavigate();
  const location = useLocation();

  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      const resp = await astrologyService.listHistory();
      const all = resp.data.conversations || [];
      setItems(
        all.filter(
          (c) =>
            c.source === source &&
            (!profileId || c.profile_id === profileId)
        )
      );
    } catch (e) {
      /* history is best-effort — a failed fetch just hides the panel */
    }
  }, [source, profileId]);

  useEffect(() => {
    load();
  }, [load]);

  const fmt = (iso) => {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleString(locale, {
        month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
      });
    } catch (e) {
      return "";
    }
  };

  const openReading = (id) => {
    setOpen(false);
    navigate(`${location.pathname}?reading=${id}`);
  };

  const remove = async (id, e) => {
    e.stopPropagation();
    try {
      await astrologyService.deleteConversation(id);
      setItems((prev) => prev.filter((c) => c.id !== id));
    } catch (err) {
      /* ignore */
    }
  };

  if (items.length === 0) return null;
  const shown = items.slice(0, limit);

  return (
    <div className="recent-readings">
      <button
        className="recent-readings__toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <History size={16} />
        {t("recent.title")} ({items.length})
        <ChevronDown
          size={16}
          className={`recent-readings__chev${open ? " is-open" : ""}`}
        />
      </button>
      {open && (
        <div className="history-list recent-readings__list">
          {shown.map((c) => (
            <div key={c.id} className="history-item" onClick={() => openReading(c.id)}>
              <div className="history-item__main">
                <div className="history-item__title">{c.title}</div>
                {c.preview && <div className="history-item__preview">{c.preview}…</div>}
                <div className="history-item__meta">
                  {c.last_model ? `${c.last_model} · ` : ""}
                  {fmt(c.updated_at)}
                </div>
              </div>
              <button
                className="history-item__delete"
                onClick={(e) => remove(c.id, e)}
                title={t("recent.delete")}
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
