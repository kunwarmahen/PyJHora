import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import {
  GraduationCap,
  CheckCircle2,
  XCircle,
  CircleDot,
  History as HistoryIcon,
  Sparkles,
  Trash2,
} from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { intlLocale } from "../utils/format";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { Button } from "../components/Button";
import { useSettings } from "../contexts/SettingsContext";
import "../styles/Dashboard.css";
import "../styles/Learn.css";

const TOPICS = ["planets", "yogas", "dashas", "vargas"];
const LEVELS = ["beginner", "intermediate", "advanced"];

// Read the model the user already picked in "Ask Astrologer" (same as SBC/Compare).
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

const barColor = (v) => (v >= 0.8 ? "#16a34a" : v >= 0.5 ? "#d97706" : "#dc2626");

const VerdictIcon = ({ verdict }) => {
  if (verdict === "correct") return <CheckCircle2 size={16} />;
  if (verdict === "partial") return <CircleDot size={16} />;
  return <XCircle size={16} />;
};

export const LearnChartPage = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const { selectedProfile } = useProfile();
  const { settings } = useSettings();

  const ayanamsa = settings.ayanamsa;

  // phase: setup | mcq | free | results | history
  const [phase, setPhase] = useState("setup");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // setup options
  const [topics, setTopics] = useState([...TOPICS]);
  const [level, setLevel] = useState("beginner");
  const [adaptive, setAdaptive] = useState(false);
  const [numMcq, setNumMcq] = useState(5);
  const [numFree, setNumFree] = useState(3);

  // active quiz
  const [sessionId, setSessionId] = useState(null);
  const [questions, setQuestions] = useState([]); // public items
  const [answers, setAnswers] = useState({}); // {id: value}
  const [results, setResults] = useState(null); // grade response
  const [stats, setStats] = useState(null);
  const [history, setHistory] = useState([]);

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

  const profileId = selectedProfile?.id || selectedProfile?._id || null;

  const loadStats = useCallback(async () => {
    try {
      const res = await astrologyService.getQuizStats(profileId);
      setStats(res.data);
    } catch (e) {
      /* non-fatal */
    }
  }, [profileId]);

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    loadStats();
  }, [selectedProfile, navigate, loadStats]);

  const mcqList = useMemo(() => questions.filter((q) => q.format === "mcq"), [questions]);
  const freeList = useMemo(() => questions.filter((q) => q.format === "free"), [questions]);

  const toggleTopic = (tp) =>
    setTopics((prev) => (prev.includes(tp) ? prev.filter((x) => x !== tp) : [...prev, tp]));

  // ---- generate ----
  const startQuiz = async (overrideTopics = null) => {
    if (!birthDetails) return;
    const chosen = overrideTopics || topics;
    if (chosen.length === 0) {
      setError(t("learn.errNoTopic"));
      return;
    }
    setLoading(true);
    setError("");
    setResults(null);
    setAnswers({});
    try {
      const res = await astrologyService.generateQuiz(
        birthDetails,
        {
          profileId,
          topics: chosen,
          level,
          adaptive,
          numMcq: Number(numMcq),
          numFree: Number(numFree),
        },
        { ...readModelConfig(), ayanamsa }
      );
      setSessionId(res.data.session_id);
      setQuestions(res.data.questions || []);
      setLevel(res.data.level || level);
      const hasMcq = (res.data.questions || []).some((q) => q.format === "mcq");
      setPhase(hasMcq ? "mcq" : "free");
    } catch (err) {
      setError(err.response?.data?.detail || t("learn.errGenerate"));
    } finally {
      setLoading(false);
    }
  };

  // ---- grade ----
  const submitQuiz = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await astrologyService.gradeQuiz(sessionId, answers, {
        ...readModelConfig(),
        ayanamsa,
      });
      setResults(res.data);
      setPhase("results");
      loadStats();
    } catch (err) {
      setError(err.response?.data?.detail || t("learn.errGrade"));
    } finally {
      setLoading(false);
    }
  };

  const openHistory = async () => {
    setError("");
    try {
      const res = await astrologyService.getQuizHistory(profileId);
      setHistory(res.data.sessions || []);
      setPhase("history");
    } catch (err) {
      setError(err.response?.data?.detail || t("learn.errHistory"));
    }
  };

  const deleteSession = async (id) => {
    try {
      await astrologyService.deleteQuiz(id);
      setHistory((prev) => prev.filter((s) => s.id !== id));
      loadStats();
    } catch (e) {
      /* ignore */
    }
  };

  const resetToSetup = () => {
    setPhase("setup");
    setResults(null);
    setQuestions([]);
    setAnswers({});
    setSessionId(null);
  };

  const answeredCount = Object.keys(answers).filter((k) => {
    const v = answers[k];
    return v !== undefined && v !== null && String(v).trim() !== "";
  }).length;

  // ---------------------------------------------------------------- render
  const renderSetup = () => (
    <>
      {stats && stats.sessions > 0 && (
        <Card title={t("learn.yourProgress")} icon={<Sparkles size={18} />} accent="indigo">
          <div className="learn-toggle-row" style={{ marginBottom: "var(--space-md)" }}>
            <span>
              {t("learn.sessionsTaken", { count: stats.sessions })} ·{" "}
              {t("learn.streak", { count: stats.streak })}
              {stats.overall_avg != null && (
                <>
                  {" "}
                  · {t("learn.overall")}:{" "}
                  <strong>{Math.round(stats.overall_avg * 100)}%</strong>
                </>
              )}
            </span>
          </div>
          {Object.keys(stats.topics || {}).length > 0 && (
            <div className="learn-topic-bars">
              {Object.entries(stats.topics).map(([tp, info]) => (
                <div className="learn-topic-bar" key={tp}>
                  <span>{t(`learn.topics.${tp}`)}</span>
                  <span className="learn-bar-track">
                    <span
                      className="learn-bar-fill"
                      style={{ width: `${Math.round(info.avg * 100)}%`, background: barColor(info.avg) }}
                    />
                  </span>
                  <span>{Math.round(info.avg * 100)}%</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      <Card title={t("learn.setupTitle")} icon={<GraduationCap size={18} />}>
        <div className="learn-setup-grid">
          <div>
            <span className="learn-section-label">{t("learn.topicsLabel")}</span>
            <p className="learn-hint">{t("learn.topicsHint")}</p>
            <div className="learn-chips">
              {TOPICS.map((tp) => (
                <span
                  key={tp}
                  className={`learn-chip ${topics.includes(tp) ? "is-active" : ""}`}
                  onClick={() => toggleTopic(tp)}
                  role="checkbox"
                  aria-checked={topics.includes(tp)}
                >
                  {topics.includes(tp) ? <CheckCircle2 size={14} /> : <CircleDot size={14} />}
                  {t(`learn.topics.${tp}`)}
                </span>
              ))}
            </div>
          </div>

          <div>
            <span className="learn-section-label">{t("learn.difficultyLabel")}</span>
            <label className="learn-switch" style={{ marginBottom: "var(--space-sm)" }}>
              <input
                type="checkbox"
                checked={adaptive}
                onChange={(e) => setAdaptive(e.target.checked)}
              />
              {t("learn.adaptive")} — <span className="learn-hint" style={{ margin: 0 }}>{t("learn.adaptiveHint")}</span>
            </label>
            {!adaptive && (
              <div className="learn-chips">
                {LEVELS.map((lv) => (
                  <span
                    key={lv}
                    className={`learn-chip ${level === lv ? "is-active" : ""}`}
                    onClick={() => setLevel(lv)}
                    role="radio"
                    aria-checked={level === lv}
                  >
                    {t(`learn.levels.${lv}`)}
                  </span>
                ))}
              </div>
            )}
          </div>

          <div>
            <span className="learn-section-label">{t("learn.countLabel")}</span>
            <div className="learn-toggle-row">
              <label>
                {t("learn.mcqCount")}{" "}
                <input
                  className="learn-count-input"
                  type="number"
                  min="0"
                  max="10"
                  value={numMcq}
                  onChange={(e) => setNumMcq(e.target.value)}
                />
              </label>
              <label>
                {t("learn.freeCount")}{" "}
                <input
                  className="learn-count-input"
                  type="number"
                  min="0"
                  max="10"
                  value={numFree}
                  onChange={(e) => setNumFree(e.target.value)}
                />
              </label>
            </div>
          </div>

          <div className="learn-actions" style={{ justifyContent: "space-between" }}>
            <Button variant="ghost" icon={<HistoryIcon size={16} />} onClick={openHistory}>
              {t("learn.viewHistory")}
            </Button>
            <Button icon={<GraduationCap size={16} />} onClick={() => startQuiz()} disabled={loading}>
              {t("learn.start")}
            </Button>
          </div>
        </div>
      </Card>
    </>
  );

  const renderQuestionCard = (q, idx) => (
    <Card key={q.id} className="learn-q">
      <div className="learn-q-meta">
        <span className="learn-tag">{t(`learn.topics.${q.topic}`)}</span>
        <span className="learn-tag learn-tag--diff">{t(`learn.levels.${q.difficulty}`)}</span>
      </div>
      <div className="learn-q-text">
        {idx}. {q.question}
      </div>
      {q.format === "mcq" ? (
        <div className="learn-options">
          {q.options.map((opt, oi) => (
            <label
              key={oi}
              className={`learn-option ${answers[q.id] === oi ? "is-selected" : ""}`}
            >
              <input
                type="radio"
                name={q.id}
                checked={answers[q.id] === oi}
                onChange={() => setAnswers((a) => ({ ...a, [q.id]: oi }))}
              />
              <span>{opt}</span>
            </label>
          ))}
        </div>
      ) : (
        <textarea
          className="learn-textarea"
          placeholder={t("learn.answerPlaceholder")}
          value={answers[q.id] || ""}
          onChange={(e) => setAnswers((a) => ({ ...a, [q.id]: e.target.value }))}
        />
      )}
    </Card>
  );

  const renderMcq = () => (
    <>
      <div className="learn-progress">
        <span>{t("learn.mcqRound")}</span>
        <span className="learn-progress-track">
          <span
            className="learn-progress-fill"
            style={{ width: `${(answeredCount / Math.max(questions.length, 1)) * 100}%` }}
          />
        </span>
      </div>
      {mcqList.map((q, i) => renderQuestionCard(q, i + 1))}
      <div className="learn-actions">
        <Button variant="ghost" onClick={resetToSetup}>
          {t("learn.cancel")}
        </Button>
        {freeList.length > 0 ? (
          <Button onClick={() => setPhase("free")}>{t("learn.continueFree")}</Button>
        ) : (
          <Button onClick={submitQuiz} disabled={loading}>
            {t("learn.submit")}
          </Button>
        )}
      </div>
    </>
  );

  const renderFree = () => (
    <>
      <div className="learn-progress">
        <span>{t("learn.freeRound")}</span>
        <span className="learn-progress-track">
          <span
            className="learn-progress-fill"
            style={{ width: `${(answeredCount / Math.max(questions.length, 1)) * 100}%` }}
          />
        </span>
      </div>
      {freeList.map((q, i) => renderQuestionCard(q, mcqList.length + i + 1))}
      <div className="learn-actions">
        {mcqList.length > 0 && (
          <Button variant="ghost" onClick={() => setPhase("mcq")}>
            {t("learn.back")}
          </Button>
        )}
        <Button onClick={submitQuiz} disabled={loading}>
          {t("learn.submit")}
        </Button>
      </div>
    </>
  );

  const renderResults = () => {
    if (!results) return null;
    const pct = Math.round(results.score * 100);
    const weak = stats?.weak_topics || [];
    return (
      <>
        <Card accent="gold">
          <div className="learn-score-hero">
            <div className="learn-score-num" style={{ color: barColor(results.score) }}>
              {pct}%
            </div>
            <div className="learn-score-label">{t("learn.scoreLabel")}</div>
          </div>
          {Object.keys(results.topic_scores || {}).length > 0 && (
            <div className="learn-topic-bars">
              {Object.entries(results.topic_scores).map(([tp, info]) => (
                <div className="learn-topic-bar" key={tp}>
                  <span>{t(`learn.topics.${tp}`)}</span>
                  <span className="learn-bar-track">
                    <span
                      className="learn-bar-fill"
                      style={{ width: `${Math.round(info.avg * 100)}%`, background: barColor(info.avg) }}
                    />
                  </span>
                  <span>{Math.round(info.avg * 100)}%</span>
                </div>
              ))}
            </div>
          )}
          {weak.length > 0 && (
            <div style={{ marginTop: "var(--space-md)" }}>
              <span className="learn-section-label">{t("learn.studyNext")}</span>
              <div className="learn-study-chips">
                {weak.map((tp) => (
                  <span key={tp} className="learn-chip is-active">
                    {t(`learn.topics.${tp}`)}
                  </span>
                ))}
              </div>
            </div>
          )}
        </Card>

        {results.results.map((r, i) => (
          <Card key={r.id} className={`learn-result-card v-${r.verdict}`}>
            <div className="learn-q-meta">
              <span className="learn-tag">{t(`learn.topics.${r.topic}`)}</span>
              <span className={`learn-verdict learn-verdict--${r.verdict}`}>
                <VerdictIcon verdict={r.verdict} />
                {t(`learn.verdicts.${r.verdict}`)}
              </span>
            </div>
            <div className="learn-q-text">
              {i + 1}. {r.question}
            </div>

            {r.format === "mcq" ? (
              <div className="learn-options">
                {r.options.map((opt, oi) => {
                  const isCorrect = oi === r.correct_index;
                  const isChosen = oi === r.chosen_index;
                  const cls = isCorrect ? "is-correct" : isChosen ? "is-wrong" : "";
                  return (
                    <div key={oi} className={`learn-option ${cls}`}>
                      {isCorrect ? (
                        <CheckCircle2 size={16} color="#16a34a" />
                      ) : isChosen ? (
                        <XCircle size={16} color="#dc2626" />
                      ) : (
                        <CircleDot size={16} color="var(--text-muted)" />
                      )}
                      <span>{opt}</span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <>
                <p className="learn-answer-line">
                  <span className="lbl">{t("learn.yourAnswer")}:</span>
                  {r.your_answer ? r.your_answer : <em>{t("learn.noAnswer")}</em>}
                </p>
                {r.what_was_right && (
                  <p className="learn-answer-line">
                    <span className="lbl" style={{ color: "var(--success-bright)" }}>
                      {t("learn.right")}:
                    </span>
                    {r.what_was_right}
                  </p>
                )}
                {r.what_was_wrong && (
                  <p className="learn-answer-line">
                    <span className="lbl" style={{ color: "var(--danger)" }}>
                      {t("learn.wrong")}:
                    </span>
                    {r.what_was_wrong}
                  </p>
                )}
                {r.expected_points?.length > 0 && (
                  <ul className="learn-expected">
                    {r.expected_points.map((p, pi) => (
                      <li key={pi}>{p}</li>
                    ))}
                  </ul>
                )}
              </>
            )}

            {r.reasoning && (
              <div className="learn-reasoning">
                <ReactMarkdown>{r.reasoning}</ReactMarkdown>
              </div>
            )}
          </Card>
        ))}

        <div className="learn-actions">
          {weak.length > 0 && (
            <Button variant="secondary" onClick={() => startQuiz(weak)} disabled={loading}>
              {t("learn.drillWeak")}
            </Button>
          )}
          <Button icon={<GraduationCap size={16} />} onClick={resetToSetup}>
            {t("learn.newQuiz")}
          </Button>
        </div>
      </>
    );
  };

  const renderHistory = () => (
    <Card title={t("learn.historyTitle")} icon={<HistoryIcon size={18} />}>
      {history.length === 0 ? (
        <p className="learn-hint">{t("learn.noHistory")}</p>
      ) : (
        history.map((s) => (
          <div className="learn-history-item" key={s.id}>
            <div>
              <div>
                {s.topics.map((tp) => t(`learn.topics.${tp}`)).join(", ")} ·{" "}
                {t(`learn.levels.${s.level}`)}
                {s.adaptive ? ` · ${t("learn.adaptive")}` : ""}
              </div>
              <div className="learn-history-meta">
                {s.created_at ? new Date(s.created_at).toLocaleString(locale) : ""} ·{" "}
                {t("learn.questionsCount", { count: s.question_count })}
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-md)" }}>
              {s.status === "graded" && s.score != null ? (
                <span className="learn-history-score" style={{ color: barColor(s.score) }}>
                  {Math.round(s.score * 100)}%
                </span>
              ) : (
                <span className="learn-history-meta">{t("learn.notGraded")}</span>
              )}
              <button
                className="learn-chip"
                onClick={() => deleteSession(s.id)}
                title={t("learn.delete")}
                style={{ padding: "0.35rem 0.5rem" }}
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))
      )}
      <div className="learn-actions">
        <Button variant="ghost" onClick={resetToSetup}>
          {t("learn.back")}
        </Button>
      </div>
    </Card>
  );

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<GraduationCap size={24} />}
        title={t("learn.title")}
        subtitle={t("learn.subtitle")}
        accent="saffron"
      />
      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />

        {error && <ErrorBanner message={error} />}

        {loading && (phase === "setup" || phase === "history") && (
          <Card>
            <LoadingState message={t("learn.generating")} />
          </Card>
        )}

        {loading && (phase === "mcq" || phase === "free") && (
          <Card>
            <LoadingState message={t("learn.grading")} />
          </Card>
        )}

        {!loading && phase === "setup" && renderSetup()}
        {!loading && phase === "mcq" && renderMcq()}
        {!loading && phase === "free" && renderFree()}
        {phase === "results" && !loading && renderResults()}
        {phase === "history" && !loading && renderHistory()}
      </div>
    </div>
  );
};

export default LearnChartPage;
