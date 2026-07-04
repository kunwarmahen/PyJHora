import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Settings as SettingsIcon, Sliders, Key, CalendarDays, User, Sparkles, Check, LogOut, Mail, ShieldOff, Trash2, Bell, Activity, AlertTriangle } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { useSettings } from "../contexts/SettingsContext";
import { useAuth } from "../contexts/AuthContext";
import { useProfile } from "../contexts/ProfileContext";
import { authService, astrologyService, notificationsService, setTokens } from "../services/api";
import { enablePush, disablePush, pushSupported, pushUnavailableReason } from "../utils/push";
import { formatDate } from "../utils/format";
import { AYANAMSAS } from "../constants/jyotish";
import { LANGUAGES } from "../i18n";
import { SITE_TITLE } from "../config/branding";
import "../styles/Settings.css";

const KEYED_PROVIDERS = ["gemini", "openai", "openai-compatible"];
const MT_MIN = 512;
const MT_MAX = 8192;
const MT_STEP = 256;

export const SettingsPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { settings, updateSetting } = useSettings();
  const { user, logout, reloadUser } = useAuth();
  const { profiles, loadProfiles } = useProfile();

  const [tab, setTab] = useState("general");
  const [savedFlash, setSavedFlash] = useState("");

  // Notifications (daily digest + push)
  const [notif, setNotif] = useState(null); // prefs
  const [notifMeta, setNotifMeta] = useState({ push_available: false, email_available: false, vapid_public_key: "" });
  const [notifMsg, setNotifMsg] = useState({ type: "", text: "" });

  // Providers for the AI model picker
  const [providers, setProviders] = useState([]);

  // API keys status
  const [keyStatus, setKeyStatus] = useState({});
  const [keyInputs, setKeyInputs] = useState({});

  // System health / diagnostics
  const [health, setHealth] = useState(null);
  const [healthErr, setHealthErr] = useState(false);
  const [healthLoading, setHealthLoading] = useState(false);

  // Account
  const [pw, setPw] = useState({ current: "", next: "", confirm: "" });
  const [pwMsg, setPwMsg] = useState({ type: "", text: "" });
  const [emailInput, setEmailInput] = useState("");
  const [emailMsg, setEmailMsg] = useState({ type: "", text: "" });
  const [acctMsg, setAcctMsg] = useState({ type: "", text: "" });
  const [delConfirm, setDelConfirm] = useState({ open: false, password: "" });
  const [busy, setBusy] = useState("");

  const flash = (text) => {
    setSavedFlash(text || t("settings.saved"));
    setTimeout(() => setSavedFlash(""), 1500);
  };

  const set = (key, value) => {
    updateSetting(key, value);
    flash();
  };

  useEffect(() => {
    let cancelled = false;
    astrologyService
      .getLlmProviders()
      .then((resp) => {
        if (!cancelled) setProviders(resp.data?.providers || []);
      })
      .catch(() => {
        if (!cancelled) setProviders([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const loadKeys = () => {
    astrologyService
      .getApiKeys()
      .then((resp) => setKeyStatus(resp.data?.keys || {}))
      .catch(() => setKeyStatus({}));
  };
  useEffect(loadKeys, []);

  const loadHealth = () => {
    setHealthLoading(true);
    setHealthErr(false);
    astrologyService
      .getHealth()
      .then((resp) => setHealth(resp.data || null))
      .catch(() => {
        setHealth(null);
        setHealthErr(true);
      })
      .finally(() => setHealthLoading(false));
  };
  useEffect(loadHealth, []);

  // Load notification prefs + profiles once.
  useEffect(() => {
    notificationsService
      .getPrefs()
      .then((r) => {
        setNotif(r.data?.prefs || null);
        setNotifMeta({
          push_available: !!r.data?.push_available,
          email_available: !!r.data?.email_available,
          vapid_public_key: r.data?.vapid_public_key || "",
        });
      })
      .catch(() => setNotif(null));
    loadProfiles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const saveNotif = async (patch) => {
    const next = { ...(notif || {}), ...patch };
    setNotif(next);
    try {
      const r = await notificationsService.setPrefs(patch);
      setNotif(r.data?.prefs || next);
      flash();
    } catch {
      setNotifMsg({ type: "error", text: t("settings.notifications.saveError") });
    }
  };

  const togglePush = async (on) => {
    setNotifMsg({ type: "", text: "" });
    if (on) {
      const res = await enablePush(notifMeta.vapid_public_key);
      if (!res.ok) {
        setNotifMsg({ type: "error", text: t(`settings.notifications.pushError.${res.reason}`, t("settings.notifications.pushError.error")) });
        return;
      }
      await saveNotif({ push: true });
    } else {
      await disablePush();
      await saveNotif({ push: false });
    }
  };

  const sendTestDigest = async () => {
    setNotifMsg({ type: "", text: "" });
    try {
      const r = await notificationsService.sendDigestNow();
      const s = r.data?.sent || {};
      setNotifMsg({
        type: "ok",
        text: t("settings.notifications.testSent", {
          email: s.email ? "✓" : "✗",
          push: s.push || 0,
        }),
      });
    } catch (err) {
      setNotifMsg({ type: "error", text: err.response?.data?.detail || t("settings.notifications.testError") });
    }
  };

  const activeProvider = providers.find((p) => p.type === settings.aiProviderType) || null;
  const models = activeProvider?.models || [];
  const isLocalProvider =
    settings.aiProviderType === "ollama" || settings.aiProviderType === "openai-compatible";

  const saveKey = async (provider) => {
    const val = (keyInputs[provider] || "").trim();
    if (!val) return;
    try {
      await astrologyService.setApiKey(provider, val);
      setKeyInputs((p) => ({ ...p, [provider]: "" }));
      loadKeys();
      flash();
    } catch {
      flash(t("settings.apiKeys.saveError"));
    }
  };

  const removeKey = async (provider) => {
    try {
      await astrologyService.deleteApiKey(provider);
      loadKeys();
      flash();
    } catch {
      /* ignore */
    }
  };

  const submitPassword = async (e) => {
    e.preventDefault();
    setPwMsg({ type: "", text: "" });
    if (pw.next !== pw.confirm) {
      setPwMsg({ type: "error", text: t("settings.account.mismatch") });
      return;
    }
    if ((pw.next || "").length < 6) {
      setPwMsg({ type: "error", text: t("settings.account.tooShort") });
      return;
    }
    try {
      await authService.changePassword(pw.current, pw.next);
      setPw({ current: "", next: "", confirm: "" });
      setPwMsg({ type: "ok", text: t("settings.account.changed") });
    } catch (err) {
      const detail = err?.response?.data?.detail || t("settings.account.changeError");
      setPwMsg({ type: "error", text: typeof detail === "string" ? detail : t("settings.account.changeError") });
    }
  };

  useEffect(() => {
    if (user?.email) setEmailInput(user.email);
  }, [user?.email]);

  const submitEmail = async (e) => {
    e.preventDefault();
    setEmailMsg({ type: "", text: "" });
    const next = (emailInput || "").trim();
    if (!next || next === user?.email) return;
    setBusy("email");
    try {
      await authService.updateEmail(next);
      await reloadUser();
      setEmailMsg({ type: "ok", text: t("settings.account.emailUpdated") });
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setEmailMsg({
        type: "error",
        text: typeof detail === "string" ? detail : t("settings.account.emailError"),
      });
    } finally {
      setBusy("");
    }
  };

  const handleLogoutOthers = async () => {
    setAcctMsg({ type: "", text: "" });
    setBusy("logoutOthers");
    try {
      const resp = await authService.logoutOtherDevices();
      // The current session's refresh token was revoked too — store the fresh
      // pair the endpoint hands back so this device stays signed in.
      setTokens(resp.data);
      setAcctMsg({ type: "ok", text: t("settings.account.loggedOutOthers") });
    } catch {
      setAcctMsg({ type: "error", text: t("settings.account.logoutOthersError") });
    } finally {
      setBusy("");
    }
  };

  const handleDeleteAccount = async (e) => {
    e.preventDefault();
    setAcctMsg({ type: "", text: "" });
    setBusy("delete");
    try {
      await authService.deleteAccount(delConfirm.password);
      // Account (and its refresh tokens) are gone — clear the local session.
      await logout();
      navigate("/login");
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setAcctMsg({
        type: "error",
        text: typeof detail === "string" ? detail : t("settings.account.deleteError"),
      });
      setBusy("");
    }
  };

  const TABS = [
    { key: "general", label: t("settings.tabs.general"), icon: <SettingsIcon size={16} /> },
    { key: "ai", label: t("settings.tabs.ai"), icon: <Sliders size={16} /> },
    { key: "apiKeys", label: t("settings.tabs.apiKeys"), icon: <Key size={16} /> },
    { key: "almanac", label: t("settings.tabs.almanac"), icon: <CalendarDays size={16} /> },
    { key: "notifications", label: t("settings.tabs.notifications"), icon: <Bell size={16} /> },
    { key: "system", label: t("settings.tabs.system"), icon: <Activity size={16} /> },
    { key: "account", label: t("settings.tabs.account"), icon: <User size={16} /> },
  ];

  // Health-check items surfaced in the System tab. `ok` maps to a green/grey pill.
  const healthChecks = health
    ? [
        { key: "server", label: t("settings.system.server"), ok: health.status === "healthy" },
        { key: "pyjhora", label: t("settings.system.pyjhora"), ok: !!health.engine_available },
        { key: "qwen", label: t("settings.system.qwen"), ok: !!health.qwen_enabled, optional: true },
        { key: "mapPicker", label: t("settings.system.mapPicker"), ok: !!health.map_picker_enabled, optional: true },
      ]
    : [];

  const mtOn = Number(settings.aiMaxTokens) > 0;

  return (
    <div className="dashboard-container">
      <PageHeader
        icon={<SettingsIcon size={22} />}
        title={t("settings.title")}
        subtitle={t("settings.subtitle")}
        accent="indigo"
      />

      <div className="dashboard-content">
        {savedFlash && (
          <div className="settings-flash">
            <Check size={14} /> {savedFlash}
          </div>
        )}

        <div className="settings-tabs" role="tablist">
          {TABS.map((tb) => (
            <button
              key={tb.key}
              type="button"
              role="tab"
              aria-selected={tab === tb.key}
              className={`settings-tab${tab === tb.key ? " is-active" : ""}`}
              onClick={() => setTab(tb.key)}
            >
              {tb.icon}
              <span>{tb.label}</span>
            </button>
          ))}
        </div>

        {/* GENERAL */}
        {tab === "general" && (
          <div className="ui-card settings-panel">
            <div className="settings-row">
              <label className="settings-label">{t("settings.general.language")}</label>
              <select
                className="form-select"
                value={settings.language}
                onChange={(e) => set("language", e.target.value)}
              >
                {LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.native}
                  </option>
                ))}
              </select>
            </div>

            <div className="settings-row">
              <label className="settings-label">{t("settings.general.chartStyle")}</label>
              <div className="settings-segment">
                {[
                  { v: "north", l: t("settings.general.north") },
                  { v: "south", l: t("settings.general.south") },
                ].map((o) => (
                  <button
                    key={o.v}
                    type="button"
                    className={`settings-seg-btn${settings.chartStyle === o.v ? " is-active" : ""}`}
                    onClick={() => set("chartStyle", o.v)}
                  >
                    {o.l}
                  </button>
                ))}
              </div>
            </div>

            <div className="settings-row">
              <label className="settings-label">{t("settings.general.ayanamsa")}</label>
              <select
                className="form-select"
                value={settings.ayanamsa}
                onChange={(e) => set("ayanamsa", e.target.value)}
              >
                {AYANAMSAS.map((a) => (
                  <option key={a.value} value={a.value}>
                    {a.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )}

        {/* AI */}
        {tab === "ai" && (
          <div className="ui-card settings-panel">
            <div className="settings-row">
              <label className="settings-label">{t("settings.ai.provider")}</label>
              <select
                className="form-select"
                value={settings.aiProviderType}
                onChange={(e) => set("aiProviderType", e.target.value)}
              >
                {(providers.length
                  ? providers
                  : [{ type: settings.aiProviderType, label: settings.aiProviderType }]
                ).map((p) => (
                  <option key={p.type} value={p.type}>
                    {p.label || p.type}
                    {p.available === false ? ` — ${t("settings.ai.unavailable")}` : ""}
                  </option>
                ))}
              </select>
            </div>
            {activeProvider && activeProvider.available === false && activeProvider.reason && (
              <p className="settings-hint settings-hint--warn">{activeProvider.reason}</p>
            )}

            <div className="settings-row">
              <label className="settings-label">{t("settings.ai.model")}</label>
              {models.length ? (
                <select
                  className="form-select"
                  value={settings.aiModel}
                  onChange={(e) => set("aiModel", e.target.value)}
                >
                  <option value="">{activeProvider?.default_model || t("settings.ai.defaultModel")}</option>
                  {models.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  className="control-input"
                  type="text"
                  value={settings.aiModel}
                  placeholder={t("settings.ai.modelPlaceholder")}
                  onChange={(e) => set("aiModel", e.target.value)}
                />
              )}
            </div>

            {isLocalProvider && (
              <div className="settings-row">
                <label className="settings-label">{t("settings.ai.endpoint")}</label>
                <input
                  className="control-input"
                  type="text"
                  value={settings.aiBaseUrl}
                  placeholder="http://localhost:11434"
                  onChange={(e) => set("aiBaseUrl", e.target.value)}
                />
              </div>
            )}

            <div className="settings-row">
              <label className="settings-label">{t("settings.ai.answerMode")}</label>
              <div className="settings-segment">
                {[
                  { v: "pass_all", l: t("settings.ai.modeFull") },
                  { v: "tools", l: t("settings.ai.modeSmart") },
                ].map((o) => (
                  <button
                    key={o.v}
                    type="button"
                    className={`settings-seg-btn${settings.aiMode === o.v ? " is-active" : ""}`}
                    onClick={() => set("aiMode", o.v)}
                  >
                    {o.l}
                  </button>
                ))}
              </div>
            </div>

            {/* Max response length */}
            <div className="settings-row settings-row--stack">
              <label className="settings-label">
                {t("settings.ai.maxTokens")}
                <span className="settings-mt-value">
                  {mtOn ? settings.aiMaxTokens : t("settings.ai.mtDefault")}
                </span>
              </label>
              <label className="settings-check">
                <input
                  type="checkbox"
                  checked={!mtOn}
                  onChange={(e) => set("aiMaxTokens", e.target.checked ? 0 : 2048)}
                />
                <span>{t("settings.ai.mtUseDefault")}</span>
              </label>
              <input
                className="settings-slider"
                type="range"
                min={MT_MIN}
                max={MT_MAX}
                step={MT_STEP}
                value={mtOn ? settings.aiMaxTokens : 2048}
                disabled={!mtOn}
                onChange={(e) => set("aiMaxTokens", parseInt(e.target.value, 10))}
              />
              <p className="settings-hint">{t("settings.ai.maxTokensHint")}</p>
            </div>

            <div className="settings-links">
              <button type="button" className="settings-link" onClick={() => setTab("apiKeys")}>
                <Key size={14} /> {t("settings.ai.manageKeys")}
              </button>
              <button type="button" className="settings-link" onClick={() => navigate("/ai-tools")}>
                <Sparkles size={14} /> {t("settings.ai.viewCapabilities")}
              </button>
            </div>
          </div>
        )}

        {/* API KEYS */}
        {tab === "apiKeys" && (
          <div className="ui-card settings-panel">
            <p className="settings-hint">{t("settings.apiKeys.hint")}</p>
            {KEYED_PROVIDERS.map((prov) => {
              const status = keyStatus[prov];
              const masked = status?.masked || status?.status;
              return (
                <div key={prov} className="settings-key-row">
                  <div className="settings-key-head">
                    <span className="settings-key-name">{prov}</span>
                    <span className={`settings-key-status${masked ? " is-set" : ""}`}>
                      {masked || t("settings.apiKeys.notSet")}
                    </span>
                  </div>
                  <div className="settings-key-controls">
                    <input
                      className="control-input"
                      type="password"
                      value={keyInputs[prov] || ""}
                      placeholder={t("settings.apiKeys.placeholder")}
                      onChange={(e) => setKeyInputs((p) => ({ ...p, [prov]: e.target.value }))}
                    />
                    <button type="button" className="control-btn" onClick={() => saveKey(prov)}>
                      {t("settings.apiKeys.save")}
                    </button>
                    {masked && (
                      <button
                        type="button"
                        className="control-btn control-btn--ghost"
                        onClick={() => removeKey(prov)}
                      >
                        {t("settings.apiKeys.remove")}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* ALMANAC */}
        {tab === "almanac" && (
          <div className="ui-card settings-panel">
            <div className="settings-row">
              <label className="settings-label">{t("settings.almanac.engine")}</label>
              <div className="settings-segment">
                {[
                  { v: "drik", l: t("settings.almanac.drik") },
                  { v: "surya_siddhanta", l: t("settings.almanac.surya") },
                ].map((o) => (
                  <button
                    key={o.v}
                    type="button"
                    className={`settings-seg-btn${settings.panchangaSystem === o.v ? " is-active" : ""}`}
                    onClick={() => set("panchangaSystem", o.v)}
                  >
                    {o.l}
                  </button>
                ))}
              </div>
            </div>
            <p className="settings-hint">{t("settings.almanac.hint")}</p>
          </div>
        )}

        {/* NOTIFICATIONS */}
        {tab === "notifications" && (
          <div className="ui-card settings-panel">
            <h3 className="settings-section-title">{t("settings.notifications.title")}</h3>
            <p className="settings-hint">{t("settings.notifications.intro")}</p>

            {notifMsg.text && (
              <div className={`settings-msg settings-msg--${notifMsg.type}`}>{notifMsg.text}</div>
            )}

            {/* Master switch */}
            <div className="settings-row">
              <label className="settings-label">{t("settings.notifications.dailyDigest")}</label>
              <label className="settings-switch">
                <input
                  type="checkbox"
                  checked={!!notif?.daily_digest}
                  onChange={(e) => saveNotif({ daily_digest: e.target.checked })}
                />
                <span />
              </label>
            </div>

            {notif?.daily_digest && (
              <>
                {/* Which profile */}
                <div className="settings-row">
                  <label className="settings-label">{t("settings.notifications.profile")}</label>
                  <select
                    className="form-select"
                    value={notif?.profile_id || ""}
                    onChange={(e) => saveNotif({ profile_id: e.target.value || null })}
                  >
                    <option value="">{t("settings.notifications.defaultProfile")}</option>
                    {(profiles || []).map((p) => (
                      <option key={p._id} value={p._id}>
                        {p.profile_name || p.birth_details?.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Preferred hour */}
                <div className="settings-row">
                  <label className="settings-label">{t("settings.notifications.hour")}</label>
                  <select
                    className="form-select"
                    value={notif?.hour ?? 7}
                    onChange={(e) => saveNotif({ hour: parseInt(e.target.value, 10) })}
                  >
                    {Array.from({ length: 24 }, (_, h) => (
                      <option key={h} value={h}>
                        {String(h).padStart(2, "0")}:00
                      </option>
                    ))}
                  </select>
                </div>

                {/* Email channel */}
                <div className="settings-row">
                  <label className="settings-label">
                    {t("settings.notifications.email")}
                    {!notifMeta.email_available && (
                      <span className="settings-badge">{t("settings.notifications.emailUnavailable")}</span>
                    )}
                  </label>
                  <label className="settings-switch">
                    <input
                      type="checkbox"
                      disabled={!notifMeta.email_available}
                      checked={!!notif?.email}
                      onChange={(e) => saveNotif({ email: e.target.checked })}
                    />
                    <span />
                  </label>
                </div>

                {/* Push channel. Reason precedence: server not configured →
                    insecure page (needs HTTPS/localhost) → old browser. */}
                {(() => {
                  const pushReason = !notifMeta.push_available
                    ? "server"
                    : pushUnavailableReason() || (!pushSupported() ? "unsupported" : "");
                  const pushBlocked = !!pushReason;
                  const reasonText = t(`settings.notifications.pushReason.${pushReason || "unsupported"}`, { brand: SITE_TITLE });
                  return (
                    <>
                      <div className="settings-row">
                        <label className="settings-label">
                          {t("settings.notifications.push")}
                          {pushBlocked && (
                            <span className="settings-badge" title={reasonText}>
                              {t("settings.notifications.pushUnavailable")}
                            </span>
                          )}
                        </label>
                        <label className="settings-switch">
                          <input
                            type="checkbox"
                            disabled={pushBlocked}
                            checked={!!notif?.push}
                            onChange={(e) => togglePush(e.target.checked)}
                          />
                          <span />
                        </label>
                      </div>
                      {pushBlocked && <p className="settings-hint">{reasonText}</p>}
                    </>
                  );
                })()}

                <button type="button" className="settings-link" onClick={sendTestDigest}>
                  {t("settings.notifications.sendTest")}
                </button>
              </>
            )}
            <p className="settings-hint">{t("settings.notifications.note")}</p>
          </div>
        )}

        {/* SYSTEM HEALTH */}
        {tab === "system" && (
          <div className="ui-card settings-panel">
            <div className="settings-key-head" style={{ marginBottom: 12 }}>
              <h3 className="settings-section-title" style={{ margin: 0 }}>
                {t("settings.system.title")}
              </h3>
              <button
                type="button"
                className="settings-link"
                onClick={loadHealth}
                disabled={healthLoading}
              >
                {healthLoading ? t("settings.system.checking") : t("settings.system.recheck")}
              </button>
            </div>

            {healthErr && (
              <p className="settings-hint settings-hint--warn">
                <AlertTriangle size={14} style={{ verticalAlign: "-2px", marginRight: 4 }} />
                {t("settings.system.unreachable")}
              </p>
            )}

            {!healthErr &&
              healthChecks.map((c) => (
                <div className="settings-health-row" key={c.key}>
                  <span className="settings-health-name">{c.label}</span>
                  <span className={`settings-health-badge${c.ok ? " is-ok" : c.optional ? " is-off" : " is-bad"}`}>
                    {c.ok ? t("settings.system.ok") : c.optional ? t("settings.system.disabled") : t("settings.system.down")}
                  </span>
                </div>
              ))}

            <p className="settings-hint">{t("settings.system.note")}</p>
          </div>
        )}

        {/* ACCOUNT */}
        {tab === "account" && (
          <div className="ui-card settings-panel">
            {/* Account overview */}
            <h3 className="settings-section-title">{t("settings.account.title")}</h3>
            <dl className="settings-account-info">
              <div>
                <dt>{t("settings.account.username")}</dt>
                <dd>{user?.username || "—"}</dd>
              </div>
              <div>
                <dt>{t("settings.account.memberSince")}</dt>
                <dd>{formatDate(user?.created_at)}</dd>
              </div>
            </dl>

            {/* Email */}
            <hr className="settings-divider" />
            <h3 className="settings-section-title">{t("settings.account.email")}</h3>
            {emailMsg.text && (
              <div className={`settings-pw-msg settings-pw-msg--${emailMsg.type}`}>{emailMsg.text}</div>
            )}
            <form onSubmit={submitEmail} className="settings-pw-form">
              <input
                className="control-input"
                type="email"
                autoComplete="email"
                placeholder={t("settings.account.emailPlaceholder")}
                value={emailInput}
                onChange={(e) => setEmailInput(e.target.value)}
                required
              />
              <button
                type="submit"
                className="control-btn"
                disabled={busy === "email" || !emailInput.trim() || emailInput.trim() === user?.email}
              >
                <Mail size={14} /> {t("settings.account.updateEmail")}
              </button>
            </form>

            {/* Change password */}
            <hr className="settings-divider" />
            <h3 className="settings-section-title">{t("settings.account.changePassword")}</h3>
            {pwMsg.text && (
              <div className={`settings-pw-msg settings-pw-msg--${pwMsg.type}`}>{pwMsg.text}</div>
            )}
            <form onSubmit={submitPassword} className="settings-pw-form">
              <input
                className="control-input"
                type="password"
                autoComplete="current-password"
                placeholder={t("settings.account.current")}
                value={pw.current}
                onChange={(e) => setPw((p) => ({ ...p, current: e.target.value }))}
                required
              />
              <input
                className="control-input"
                type="password"
                autoComplete="new-password"
                placeholder={t("settings.account.new")}
                value={pw.next}
                onChange={(e) => setPw((p) => ({ ...p, next: e.target.value }))}
                required
              />
              <input
                className="control-input"
                type="password"
                autoComplete="new-password"
                placeholder={t("settings.account.confirm")}
                value={pw.confirm}
                onChange={(e) => setPw((p) => ({ ...p, confirm: e.target.value }))}
                required
              />
              <button type="submit" className="control-btn">
                {t("settings.account.changeBtn")}
              </button>
            </form>
            <p className="settings-hint">{t("settings.account.changeNote")}</p>

            {/* Sessions */}
            <hr className="settings-divider" />
            <h3 className="settings-section-title">{t("settings.account.sessions")}</h3>
            {acctMsg.text && (
              <div className={`settings-pw-msg settings-pw-msg--${acctMsg.type}`}>{acctMsg.text}</div>
            )}
            <div className="settings-account-actions">
              <button
                type="button"
                className="control-btn control-btn--ghost"
                onClick={handleLogoutOthers}
                disabled={busy === "logoutOthers"}
              >
                <ShieldOff size={14} /> {t("settings.account.logoutOthers")}
              </button>
              <button
                type="button"
                className="control-btn control-btn--ghost"
                onClick={async () => {
                  await logout();
                  navigate("/login");
                }}
              >
                <LogOut size={14} /> {t("settings.account.logout")}
              </button>
            </div>
            <p className="settings-hint">{t("settings.account.logoutOthersNote")}</p>

            {/* Danger zone: delete account */}
            <hr className="settings-divider" />
            <div className="settings-danger">
              <h3 className="settings-section-title settings-danger-title">
                {t("settings.account.deleteTitle")}
              </h3>
              <p className="settings-hint settings-hint--warn">{t("settings.account.deleteWarn")}</p>
              {!delConfirm.open ? (
                <button
                  type="button"
                  className="control-btn control-btn--danger"
                  onClick={() => {
                    setAcctMsg({ type: "", text: "" });
                    setDelConfirm({ open: true, password: "" });
                  }}
                >
                  <Trash2 size={14} /> {t("settings.account.deleteBtn")}
                </button>
              ) : (
                <form onSubmit={handleDeleteAccount} className="settings-pw-form">
                  <input
                    className="control-input"
                    type="password"
                    autoComplete="current-password"
                    placeholder={t("settings.account.deleteConfirmPrompt")}
                    value={delConfirm.password}
                    onChange={(e) => setDelConfirm((p) => ({ ...p, password: e.target.value }))}
                    required
                  />
                  <div className="settings-account-actions">
                    <button
                      type="submit"
                      className="control-btn control-btn--danger"
                      disabled={!delConfirm.password || busy === "delete"}
                    >
                      <Trash2 size={14} /> {t("settings.account.deleteConfirmBtn")}
                    </button>
                    <button
                      type="button"
                      className="control-btn control-btn--ghost"
                      onClick={() => setDelConfirm({ open: false, password: "" })}
                    >
                      {t("settings.account.deleteCancel")}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
