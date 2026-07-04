import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Clock4,
  Sparkles,
  AlertTriangle,
  ArrowRight,
  Check,
  Plus,
  Trash2,
  CalendarHeart,
  MessageCircle,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useProfile } from "../contexts/ProfileContext";
import { useSettings } from "../contexts/SettingsContext";
import { astrologyService } from "../services/api";
import { useRestoreReading } from "../hooks/useRestoreReading";
import { errorMessage } from "../utils/format";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { ChatComposer } from "../components/chat/ChatComposer";
import { ChatBubble } from "../components/chat/ChatBubble";
import { AYANAMSAS } from "../constants/jyotish";
import "../styles/Dashboard.css";
import "../styles/Shared.css";
import "../styles/Chat.css";

// The three BV Raman suddhi methods the backend exposes. `needsGender` gates the
// gender selector (janma suddhi is the only one that needs it).
const METHODS = [
  { key: "nakshatra", labelKey: "rectify.methodNakshatra", needsGender: false },
  { key: "lagna", labelKey: "rectify.methodLagna", needsGender: false },
  { key: "janma", labelKey: "rectify.methodJanma", needsGender: true },
];

// Event types for the event-based mode. Keys must match the backend
// EVENT_SIGNIFICATORS map.
const EVENT_TYPES = [
  "marriage", "childbirth", "career", "promotion", "education", "wealth",
  "property", "relocation", "illness", "accident", "father_death", "mother_death",
];

const WINDOWS = [
  { minutes: 120, labelKey: "rectify.window2h" },
  { minutes: 360, labelKey: "rectify.window6h" },
  { minutes: 720, labelKey: "rectify.windowDay" },
];

// Read the model the user already picked in "Ask Astrologer".
const readModelConfig = () => {
  const providerType = localStorage.getItem("ai_provider_type") || "ollama";
  return {
    providerType,
    model: localStorage.getItem("ai_model") || "",
    baseUrl: providerType === "ollama" ? localStorage.getItem("ai_base_url") || undefined : undefined,
    legacyProvider: providerType === "ollama" ? "qwen" : providerType,
    maxTokens: parseInt(localStorage.getItem("ai_max_tokens") || "0", 10) || undefined,
  };
};

export const BirthTimeRectificationPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { selectedProfile, updateProfile } = useProfile();

  // Top-level mode: rule-based (śuddhi) vs event-based.
  const [mode, setMode] = useState(() => localStorage.getItem("rectify_mode") || "rule");

  // Rule-mode state.
  const [method, setMethod] = useState(
    () => localStorage.getItem("rectify_method") || "nakshatra"
  );
  const [gender, setGender] = useState(null); // 0=male, 1=female (janma only)

  // Event-mode state.
  const [events, setEvents] = useState([{ type: "marriage", date: "" }]);
  const [windowMinutes, setWindowMinutes] = useState(120);

  // Conversational-mode state.
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [collectedEvents, setCollectedEvents] = useState([]);
  const [chatReady, setChatReady] = useState(false);
  const [chatStarted, setChatStarted] = useState(false);

  const { settings } = useSettings();
  const chartStyle = settings.chartStyle;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);

  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");
  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");
  // Reopen a saved reading from History (restore method/gender + saved text).
  const [pendingReading, setPendingReading] = useState(null);
  useRestoreReading((r) => {
    if (r.context?.method) setMethod(r.context.method);
    if (r.context?.gender != null) setGender(r.context.gender);
    setPendingReading({ reading: r.reading, model: r.model });
  });
  useEffect(() => {
    if (pendingReading && !loading) {
      setAiAnalysis(pendingReading.reading);
      setAiModel(pendingReading.model);
      setPendingReading(null);
    }
  }, [pendingReading, loading]);

  const ayanamsa = settings.ayanamsa;
  const ayanamsaLabel = AYANAMSAS.find((a) => a.value === ayanamsa)?.label || ayanamsa;

  const activeMethod = METHODS.find((m) => m.key === method) || METHODS[0];

  const chooseMode = (m) => {
    setMode(m);
    localStorage.setItem("rectify_mode", m);
    setResult(null);
    setError("");
    setApplied(false);
    setAiAnalysis("");
    setAiError("");
    setChatStarted(false);
    setChatMessages([]);
    setCollectedEvents([]);
    setChatReady(false);
  };

  const chooseMethod = (key) => {
    setMethod(key);
    localStorage.setItem("rectify_method", key);
  };

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

  const resetOutputs = () => {
    setApplied(false);
    setAiAnalysis("");
    setAiError("");
    setAiModel("");
  };

  // Rule mode auto-runs when the method/gender changes.
  const rectifyByRule = useCallback(async () => {
    if (!birthDetails) return;
    if (activeMethod.needsGender && gender == null) {
      setResult(null);
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    resetOutputs();
    try {
      const res = await astrologyService.rectifyBirthTime(
        birthDetails,
        method,
        activeMethod.needsGender ? gender : null,
        ayanamsa
      );
      setResult(res.data);
    } catch (err) {
      setError(errorMessage(err, t("rectify.calcError")));
    } finally {
      setLoading(false);
    }
  }, [birthDetails, method, gender, activeMethod, ayanamsa, t]);

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    if (mode === "rule") rectifyByRule();
  }, [selectedProfile, navigate, mode, rectifyByRule]);

  // The events that produced the current result (form list or chat-collected),
  // so the AI "why it fits" explanation uses exactly the same set.
  const [resultEvents, setResultEvents] = useState([]);

  // Shared: rectify from a given set of {type, date} events.
  const runRectifyForEvents = async (evts) => {
    if (!birthDetails || !evts || evts.length === 0) return;
    setLoading(true);
    setError("");
    setResult(null);
    resetOutputs();
    setResultEvents(evts);
    try {
      const res = await astrologyService.rectifyByEvents(
        birthDetails,
        evts,
        windowMinutes,
        ayanamsa
      );
      setResult(res.data);
    } catch (err) {
      setError(errorMessage(err, t("rectify.calcError")));
    } finally {
      setLoading(false);
    }
  };

  // Event mode runs on explicit submit (needs dated events).
  const validEvents = events.filter((e) => e.type && e.date);
  const runEventRectify = () => runRectifyForEvents(validEvents);

  const addEvent = () => setEvents((ev) => [...ev, { type: "childbirth", date: "" }]);
  const removeEvent = (i) => setEvents((ev) => ev.filter((_, idx) => idx !== i));
  const updateEvent = (i, patch) =>
    setEvents((ev) => ev.map((e, idx) => (idx === i ? { ...e, ...patch } : e)));

  // ---- Conversational mode ----
  const mergeEvents = (prev, next) => {
    const seen = new Set(prev.map((e) => `${e.type}|${e.date}`));
    const out = [...prev];
    (next || []).forEach((e) => {
      const k = `${e.type}|${e.date}`;
      if (!seen.has(k)) {
        seen.add(k);
        out.push(e);
      }
    });
    return out;
  };

  const sendChatTurn = async (userText, history) => {
    setChatBusy(true);
    try {
      const res = await astrologyService.rectifyChat(
        birthDetails,
        history,
        collectedEvents,
        { personName: birthDetails.name },
        { ...readModelConfig(), ayanamsa }
      );
      const reply = res.data.reply || "";
      setChatMessages([...history, { role: "assistant", content: reply }]);
      setCollectedEvents((prev) => mergeEvents(prev, res.data.events));
      setChatReady(Boolean(res.data.ready));
    } catch (err) {
      setChatMessages([
        ...history,
        { role: "assistant", content: errorMessage(err, t("rectify.aiError")), error: true },
      ]);
    } finally {
      setChatBusy(false);
    }
  };

  const startChat = () => {
    setChatStarted(true);
    setChatMessages([]);
    setCollectedEvents([]);
    setChatReady(false);
    setResult(null);
    // Kick off with the interviewer's opening question.
    sendChatTurn("", []);
  };

  const handleChatSend = () => {
    const text = chatInput.trim();
    if (!text || chatBusy) return;
    const history = [...chatMessages, { role: "user", content: text }];
    setChatMessages(history);
    setChatInput("");
    sendChatTurn(text, history);
  };

  const handleApply = async () => {
    if (!result?.suggested || !selectedProfile) return;
    if (!window.confirm(t("rectify.applyConfirm", { time: result.suggested.tob }))) return;
    setApplying(true);
    try {
      const newDetails = {
        ...selectedProfile.birth_details,
        dob: result.suggested.dob,
        tob: result.suggested.tob,
      };
      const res = await updateProfile(
        selectedProfile._id,
        selectedProfile.profile_name,
        newDetails
      );
      if (res?.success) setApplied(true);
      else setError(res?.error || t("rectify.applyError"));
    } catch (err) {
      setError(errorMessage(err, t("rectify.applyError")));
    } finally {
      setApplying(false);
    }
  };

  const handleAi = async () => {
    if (!birthDetails) return;
    setAiLoading(true);
    setAiError("");
    try {
      let res;
      if (mode !== "rule") {
        res = await astrologyService.explainEventRectificationAI(
          birthDetails,
          { events: resultEvents, windowMinutes, personName: birthDetails.name },
          { ...readModelConfig(), ayanamsa }
        );
      } else {
        res = await astrologyService.explainRectificationAI(
          birthDetails,
          {
            method,
            gender: activeMethod.needsGender ? gender : undefined,
            personName: birthDetails.name,
          },
          { ...readModelConfig(), ayanamsa }
        );
      }
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(errorMessage(err, t("rectify.aiError")));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const Kundali = chartStyle === "south" ? SouthIndianChart : NorthIndianChart;
  const needGender = mode === "rule" && activeMethod.needsGender && gender == null;
  const suggested = result?.suggested;
  const before = result?.before || {};
  const after = result?.after || {};
  // Event- and chat-mode results carry a fit % + per-event matches.
  const isEventResult = result?.confidence != null;

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Clock4 size={24} />}
        title={t("rectify.title")}
        subtitle={t("rectify.subtitle")}
        accent="terracotta"
      />

      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />

        {/* Experimental disclaimer — always visible, this is the core caveat. */}
        <div className="readonly-banner" style={{ display: "flex", gap: "0.6rem", alignItems: "flex-start" }}>
          <AlertTriangle size={20} style={{ flexShrink: 0, marginTop: "0.1rem" }} />
          <span>{t("rectify.experimental")}</span>
        </div>

        {/* Mode toggle */}
        <div className="page-controls">
          <div className="controls-group">
            <label className="control-label">{t("rectify.mode")}</label>
            <div className="chart-toggle">
              <button
                className={`chart-toggle__btn${mode === "rule" ? " is-active" : ""}`}
                onClick={() => chooseMode("rule")}
              >
                {t("rectify.modeRule")}
              </button>
              <button
                className={`chart-toggle__btn${mode === "events" ? " is-active" : ""}`}
                onClick={() => chooseMode("events")}
              >
                {t("rectify.modeEvents")}
              </button>
              <button
                className={`chart-toggle__btn${mode === "chat" ? " is-active" : ""}`}
                onClick={() => chooseMode("chat")}
              >
                {t("rectify.modeChat")}
              </button>
            </div>
          </div>
        </div>

        {/* ---- Rule mode controls ---- */}
        {mode === "rule" && (
          <>
            <div className="page-controls">
              <div className="controls-group">
                <label className="control-label">
                  <Clock4 size={18} style={{ color: "var(--saffron)" }} />
                  {t("rectify.method")}
                </label>
                <div className="chart-toggle">
                  {METHODS.map((m) => (
                    <button
                      key={m.key}
                      className={`chart-toggle__btn${method === m.key ? " is-active" : ""}`}
                      onClick={() => chooseMethod(m.key)}
                    >
                      {t(m.labelKey)}
                    </button>
                  ))}
                </div>
              </div>

              {activeMethod.needsGender && (
                <div className="controls-group">
                  <label className="control-label">{t("rectify.gender")}</label>
                  <div className="chart-toggle">
                    <button
                      className={`chart-toggle__btn${gender === 0 ? " is-active" : ""}`}
                      onClick={() => setGender(0)}
                    >
                      {t("rectify.male")}
                    </button>
                    <button
                      className={`chart-toggle__btn${gender === 1 ? " is-active" : ""}`}
                      onClick={() => setGender(1)}
                    >
                      {t("rectify.female")}
                    </button>
                  </div>
                </div>
              )}
            </div>
            <p className="card-intro">{t(`rectify.methodDesc.${method}`)}</p>
          </>
        )}

        {/* ---- Event mode controls ---- */}
        {mode === "events" && (
          <div className="ui-card ui-card--accent ui-card--flush">
            <h3 className="ui-card-header ui-card-header--sm">
              <CalendarHeart size={18} />
              {t("rectify.eventsTitle")}
            </h3>
            <p className="card-intro">{t("rectify.eventsIntro")}</p>

            {events.map((ev, i) => (
              <div
                key={i}
                className="controls-group"
                style={{ gap: "0.5rem", marginBottom: "0.5rem", flexWrap: "wrap" }}
              >
                <select
                  className="form-select"
                  value={ev.type}
                  onChange={(e) => updateEvent(i, { type: e.target.value })}
                >
                  {EVENT_TYPES.map((et) => (
                    <option key={et} value={et}>
                      {t(`rectify.event.${et}`)}
                    </option>
                  ))}
                </select>
                <input
                  type="date"
                  className="control-input"
                  value={ev.date}
                  onChange={(e) => updateEvent(i, { date: e.target.value })}
                />
                <button
                  type="button"
                  className="control-btn"
                  onClick={() => removeEvent(i)}
                  aria-label={t("rectify.removeEvent")}
                  disabled={events.length <= 1}
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}

            <button type="button" className="control-btn" onClick={addEvent}>
              <Plus size={16} /> {t("rectify.addEvent")}
            </button>

            <div className="controls-group" style={{ marginTop: "1rem" }}>
              <label className="control-label">{t("rectify.searchWindow")}</label>
              <div className="chart-toggle">
                {WINDOWS.map((w) => (
                  <button
                    key={w.minutes}
                    className={`chart-toggle__btn${windowMinutes === w.minutes ? " is-active" : ""}`}
                    onClick={() => setWindowMinutes(w.minutes)}
                  >
                    {t(w.labelKey)}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-xl">
              <button
                className="ui-btn ui-btn--primary"
                onClick={runEventRectify}
                disabled={loading || validEvents.length === 0}
              >
                {loading ? t("rectify.loading") : t("rectify.runEvents")}
              </button>
              {validEvents.length === 0 && (
                <p className="card-note">{t("rectify.eventsPrompt")}</p>
              )}
            </div>
          </div>
        )}

        {/* ---- Conversational mode ---- */}
        {mode === "chat" && (
          <div className="ui-card ui-card--accent ui-card--flush">
            <h3 className="ui-card-header ui-card-header--sm">
              <MessageCircle size={18} />
              {t("rectify.chatTitle")}
            </h3>
            <p className="card-intro">{t("rectify.chatIntro")}</p>

            {!chatStarted ? (
              <button className="ui-btn ui-btn--primary" onClick={startChat} disabled={chatBusy}>
                <MessageCircle size={18} /> {t("rectify.chatStart")}
              </button>
            ) : (
              <>
                <div className="rectify-chat__log">
                  {chatMessages.map((m, i) => (
                    <ChatBubble
                      key={i}
                      role={m.role}
                      content={m.content}
                      error={m.error}
                    />
                  ))}
                  {chatBusy && (
                    <ChatBubble
                      role="assistant"
                      content=""
                      streaming
                      thinkingLabel={t("rectify.chatThinking")}
                    />
                  )}
                </div>

                <ChatComposer
                  value={chatInput}
                  onChange={setChatInput}
                  onSubmit={handleChatSend}
                  busy={chatBusy}
                  placeholder={t("rectify.chatPlaceholder")}
                  multiline={false}
                />

                {/* Collected events + run button */}
                {collectedEvents.length > 0 && (
                  <div className="mt-xl">
                    <div className="fw-600 text-secondary" style={{ marginBottom: "0.4rem" }}>
                      {t("rectify.collected")}:
                    </div>
                    <div className="info-pills">
                      {collectedEvents.map((e, i) => (
                        <span key={i} className="info-pill">
                          {t(`rectify.event.${e.type}`)}{" "}
                          <strong className="text-saffron">{e.date}</strong>
                        </span>
                      ))}
                    </div>
                    <div className="mt-xl">
                      <button
                        className={`ui-btn ui-btn--primary${chatReady ? " fade-in" : ""}`}
                        onClick={() => runRectifyForEvents(collectedEvents)}
                        disabled={loading || collectedEvents.length === 0}
                      >
                        {loading ? t("rectify.loading") : t("rectify.runEvents")}
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        <ErrorBanner message={error} />

        {needGender ? (
          <Card>
            <p className="card-note">{t("rectify.genderPrompt")}</p>
          </Card>
        ) : loading ? (
          <Card>
            <LoadingState message={t("rectify.loading")} />
          </Card>
        ) : result ? (
          <div className="fade-in">
            {/* Outcome summary */}
            <div className="info-pills mt-xl">
              <span className="info-pill">
                {t("rectify.entered")}:{" "}
                <strong className="text-indigo">{result.entered?.tob}</strong>
              </span>
              {suggested ? (
                <>
                  <span className="info-pill">
                    {t("rectify.suggested")}:{" "}
                    <strong className="text-saffron">{suggested.tob}</strong>
                    {suggested.dob !== result.entered?.dob ? ` (${suggested.dob})` : ""}
                  </span>
                  <span className="info-pill">
                    {t("rectify.delta")}:{" "}
                    <strong className="text-vermillion">
                      {result.delta_minutes > 0 ? "+" : ""}
                      {result.delta_minutes} {t("rectify.minutes")}
                    </strong>
                  </span>
                </>
              ) : (
                <span className="info-pill">
                  <strong className="text-saffron">
                    {result.already_consistent
                      ? t("rectify.alreadyConsistent")
                      : isEventResult
                      ? t("rectify.eventsNoChange")
                      : t("rectify.notConverged")}
                  </strong>
                </span>
              )}
              {isEventResult && result.confidence != null && (
                <span className="info-pill">
                  {t("rectify.fit")}:{" "}
                  <strong className="text-saffron">{result.confidence}%</strong>
                </span>
              )}
              <span className="info-pill">
                {t("transit.ayanamsa")}: <strong className="text-indigo">{ayanamsaLabel}</strong>
              </span>
            </div>

            <p className="card-note">{result.note}</p>

            {/* Event-match breakdown */}
            {isEventResult && result.events?.length > 0 && (
              <div className="ui-card ui-card--accent-gold ui-card--flush mt-xl">
                <h3 className="ui-card-header ui-card-header--sm">{t("rectify.eventMatches")}</h3>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{t("rectify.eventCol")}</th>
                        <th>{t("rectify.dateCol")}</th>
                        <th>{t("rectify.periodCol")}</th>
                        <th>{t("rectify.whyCol")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.events.map((e, i) => (
                        <tr key={i}>
                          <td className="fw-700 text-indigo">{t(`rectify.event.${e.type}`)}</td>
                          <td className="text-secondary">{e.date}</td>
                          <td className="text-secondary">
                            {e.maha} / {e.bhukti}
                          </td>
                          <td className="text-secondary" style={{ fontSize: "0.85rem" }}>
                            {e.matched?.length ? (
                              <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>
                                {e.matched.map((m, j) => (
                                  <li key={j}>{m}</li>
                                ))}
                              </ul>
                            ) : (
                              <span className="text-muted">{t("rectify.noMatch")}</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Before / after fast-movers */}
            {suggested && (
              <div className="ui-card ui-card--accent ui-card--flush mt-xl">
                <h3 className="ui-card-header ui-card-header--sm">{t("rectify.whatMoved")}</h3>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th />
                        <th>{t("rectify.entered")}</th>
                        <th />
                        <th>{t("rectify.suggested")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td className="fw-700 text-indigo">{t("rectify.moonStar")}</td>
                        <td>
                          {before.moon?.nakshatra} · {t("rectify.pada")} {before.moon?.pada}
                        </td>
                        <td className="text-center">
                          <ArrowRight size={16} style={{ color: "var(--saffron)" }} />
                        </td>
                        <td className="fw-600 text-saffron">
                          {after.moon?.nakshatra} · {t("rectify.pada")} {after.moon?.pada}
                        </td>
                      </tr>
                      <tr>
                        <td className="fw-700 text-indigo">{t("rectify.risingSign")}</td>
                        <td>
                          {before.lagna?.sign_name}{" "}
                          <span className="text-muted">({before.lagna?.nakshatra})</span>
                        </td>
                        <td className="text-center">
                          <ArrowRight size={16} style={{ color: "var(--saffron)" }} />
                        </td>
                        <td className="fw-600 text-saffron">
                          {after.lagna?.sign_name}{" "}
                          <span className="text-muted">({after.lagna?.nakshatra})</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* Apply to profile */}
                <div className="mt-xl">
                  {applied ? (
                    <div className="info-pill" style={{ color: "var(--saffron)" }}>
                      <Check size={16} /> {t("rectify.applied")}
                    </div>
                  ) : (
                    <button
                      className="ui-btn ui-btn--primary"
                      onClick={handleApply}
                      disabled={applying}
                    >
                      {applying ? t("rectify.applying") : t("rectify.apply")}
                    </button>
                  )}
                  <p className="card-note">{t("rectify.applyNote")}</p>
                </div>
              </div>
            )}

            {/* Before / after charts */}
            {result.before_chart?.status === "success" && (
              <div className="chart-grid mt-xl">
                <Kundali
                  planets={result.before_chart.planets}
                  lagna={result.before_chart.lagna}
                  title={t("rectify.chartEntered")}
                  subtitle={result.entered?.tob}
                />
                {suggested && result.after_chart?.status === "success" && (
                  <Kundali
                    planets={result.after_chart.planets}
                    lagna={result.after_chart.lagna}
                    title={t("rectify.chartSuggested")}
                    subtitle={suggested.tob}
                  />
                )}
              </div>
            )}

            {/* AI explanation */}
            {suggested && (
              <div className="mt-xl">
                <Card title={t("rectify.aiTitle")} icon={<Sparkles size={24} />} accent="gold">
                  <ErrorBanner message={aiError} />
                  {!aiAnalysis && !aiLoading && <p className="ai-panel__hint">{t("rectify.aiHint")}</p>}
                  {aiLoading && <LoadingState message={t("rectify.aiLoading")} />}
                  {aiAnalysis && !aiLoading && (
                    <div className="sbc-ai-markdown ai-panel__reading">
                      <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                      {aiModel && (
                        <div className="ai-panel__meta">
                          {t("rectify.aiModel", { model: aiModel })}
                        </div>
                      )}
                    </div>
                  )}
                  {!aiLoading && (
                    <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                      <Sparkles size={18} />
                      {aiAnalysis ? t("rectify.aiRegenerate") : t("rectify.aiGenerate")}
                    </button>
                  )}
                  <p className="card-note">{t("rectify.disclaimer")}</p>
                </Card>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
};
