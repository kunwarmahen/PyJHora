import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Sparkles, CheckCircle2, AlertTriangle, X } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { useAiActivity, markAiActivitySeen } from "../hooks/useAiActivity";
import "../styles/AiActivity.css";

// What the AI is working on, visible from every page. Answers are written by
// server-side jobs that outlive the tab that asked (ask_jobs / detached_http),
// but a question isn't saved until it is answered — so without this, leaving
// the page mid-answer made it look lost. Running items say so; finished ones
// open the saved answer on its own page, under the profile it was for.

const since = (iso, now) => {
  const s = Math.max(0, Math.floor((now - Date.parse(iso)) / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};

// A ticking "now" for elapsed times, only while something is running.
const useNow = (active) => {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return undefined;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active]);
  return now;
};

/** Open an activity item where it belongs: the saved answer on its own page
 * (`?reading=` — the same deep link History uses), or for a running Ask
 * question, the Ask page, which re-attaches to the stream. */
export const useOpenActivity = () => {
  const navigate = useNavigate();
  const { profiles, selectedProfile, selectProfile, loadProfiles } = useProfile();
  return async (item) => {
    // Show it under the chart it was made for. The provider only loads the
    // selected profile, so fetch the list when the item belongs to another.
    if (item.profile_id && item.profile_id !== selectedProfile?._id) {
      let list = profiles || [];
      if (!list.some((x) => x._id === item.profile_id) && loadProfiles) {
        list = (await loadProfiles()) || [];
      }
      const p = list.find((x) => x._id === item.profile_id);
      if (p) selectProfile(p);
    }
    const route = item.route || "/ask-astrologer";
    if (item.status === "done") {
      markAiActivitySeen(item.id);
      navigate(item.result_id ? `${route}?reading=${item.result_id}` : route);
    } else {
      navigate(route);
    }
  };
};

// A running Ask question can be watched live on its page; a running reading
// cannot (its panel shows only a result), so it isn't a link until it's done.
const canOpen = (item) =>
  item.status === "done" || (item.status === "running" && item.kind === "ask");

export const AiActivityList = ({ items, onAfterOpen }) => {
  const { t } = useTranslation();
  const { profiles, selectedProfile } = useProfile();
  const open = useOpenActivity();
  const now = useNow(items.some((i) => i.status === "running"));

  const profileName = (pid) => {
    // The full list is only loaded on some pages; the selected one always is.
    const p =
      pid &&
      (profiles?.find((x) => x._id === pid) || (selectedProfile?._id === pid && selectedProfile));
    return p ? p.profile_name || p.birth_details?.name : null;
  };

  const statusLine = (item) => {
    if (item.status === "running") {
      return item.kind === "ask"
        ? t("activity.writingAnswer", { time: since(item.started_at, now) })
        : t("activity.writingReading", { time: since(item.started_at, now) });
    }
    if (item.status === "done") return t("activity.ready");
    if (item.status === "cancelled") return t("activity.stopped");
    return t("activity.failed", { error: item.error || "" });
  };

  const icon = (item) =>
    item.status === "running" ? (
      <Sparkles size={15} className="ai-activity__spin" aria-hidden="true" />
    ) : item.status === "done" ? (
      <CheckCircle2 size={15} aria-hidden="true" />
    ) : (
      <AlertTriangle size={15} aria-hidden="true" />
    );

  return (
    <ul className="ai-activity__list">
      {items.map((item) => {
        const who = profileName(item.profile_id);
        const body = (
          <>
            <span className={`ai-activity__icon ai-activity__icon--${item.status}`}>
              {icon(item)}
            </span>
            <span className="ai-activity__text">
              <span className="ai-activity__title">{item.title}</span>
              <span className="ai-activity__meta">
                {statusLine(item)}
                {who ? ` · ${who}` : ""}
              </span>
            </span>
          </>
        );
        return (
          <li key={item.id} className="ai-activity__row">
            {canOpen(item) ? (
              <button
                type="button"
                className="ai-activity__open"
                onClick={() => {
                  open(item);
                  if (onAfterOpen) onAfterOpen();
                }}
              >
                {body}
              </button>
            ) : (
              <div className="ai-activity__open ai-activity__open--static">{body}</div>
            )}
            {item.status !== "running" && (
              <button
                type="button"
                className="ai-activity__dismiss"
                onClick={() => markAiActivitySeen(item.id)}
                title={t("activity.dismiss")}
                aria-label={t("activity.dismiss")}
              >
                <X size={14} />
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
};

/** The header pill. Renders nothing while there's nothing to say. */
export const AiActivityPill = () => {
  const { t } = useTranslation();
  const { items, running, ready } = useAiActivity();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  useEffect(() => {
    if (!items.length) setOpen(false);
  }, [items.length]);

  if (!items.length) return null;

  const label = running
    ? t("activity.pillRunning", { count: running })
    : t("activity.pillReady", { count: ready });

  return (
    <div className="ai-activity" ref={wrapRef}>
      <button
        type="button"
        className={`ai-activity__pill${running ? "" : " ai-activity__pill--ready"}`}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="true"
        title={label}
      >
        {running ? (
          <Sparkles size={15} className="ai-activity__spin" aria-hidden="true" />
        ) : (
          <CheckCircle2 size={15} aria-hidden="true" />
        )}
        <span className="ai-activity__pill-label">{label}</span>
        <span className="ai-activity__count" aria-hidden="true">
          {running || ready}
        </span>
      </button>
      {open && (
        <div className="ai-activity__panel" role="dialog" aria-label={t("activity.title")}>
          <div className="ai-activity__panel-head">{t("activity.title")}</div>
          <AiActivityList items={items} onAfterOpen={() => setOpen(false)} />
          {running > 0 && <p className="ai-activity__note">{t("activity.keepBrowsing")}</p>}
        </div>
      )}
    </div>
  );
};

export default AiActivityPill;
