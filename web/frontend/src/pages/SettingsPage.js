import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Settings as SettingsIcon, Sliders, Key, CalendarDays, User, Sparkles, Check, LogOut, Mail, ShieldOff, Trash2, Bell, Activity, AlertTriangle, Rss, Copy, Terminal, Plus } from "lucide-react";
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

  // Google-only accounts have no password yet; offer "Set" instead of "Change".
  // Undefined (older profile payloads) defaults to true so nothing regresses.
  const hasPassword = user?.has_password !== false;

  const [tab, setTab] = useState("general");
  const [savedFlash, setSavedFlash] = useState("");

  // iCal feed (§5.10): resolve a signed subscribe URL for a chosen profile.
  const [calProfileId, setCalProfileId] = useState("");
  const [calUrl, setCalUrl] = useState("");
  const [calBusy, setCalBusy] = useState(false);
  const [calCopied, setCalCopied] = useState(false);
  const [calError, setCalError] = useState("");

  useEffect(() => {
    if (tab !== "calendar" || !profiles?.length) return;
    const pid = calProfileId || profiles[0]?._id;
    if (!pid) return;
    if (calProfileId !== pid) setCalProfileId(pid);
    let cancelled = false;
    setCalBusy(true);
    setCalError("");
    setCalUrl("");
    astrologyService
      .getCalendarToken(pid)
      .then((res) => {
        if (cancelled) return;
        const origin = window.location.origin;
        setCalUrl(origin + res.data.path);
      })
      .catch((err) => {
        if (!cancelled) setCalError(err.response?.data?.detail || t("settings.calendar.error"));
      })
      .finally(() => !cancelled && setCalBusy(false));
    return () => {
      cancelled = true;
    };
  }, [tab, calProfileId, profiles, t]);

  const copyCalUrl = async () => {
    try {
      await navigator.clipboard.writeText(calUrl);
      setCalCopied(true);
      setTimeout(() => setCalCopied(false), 1800);
    } catch {
      /* clipboard unavailable — user can select manually */
    }
  };

  // API access — public-API / MCP tokens (§2.3)
  const [apiTokens, setApiTokens] = useState([]);
  const [apiTokLabel, setApiTokLabel] = useState("");
  const [apiTokBusy, setApiTokBusy] = useState(false);
  const [apiTokError, setApiTokError] = useState("");
  const [newApiToken, setNewApiToken] = useState(""); // shown once, after create
  const [apiTokCopied, setApiTokCopied] = useState(false);

  // Load the user's API tokens when the API-access tab opens.
  useEffect(() => {
    if (tab !== "apiAccess") return;
    let cancelled = false;
    setApiTokError("");
    authService
      .listApiTokens()
      .then((res) => !cancelled && setApiTokens(res.data.tokens || []))
      .catch((err) => !cancelled && setApiTokError(err.response?.data?.detail || t("settings.apiAccess.loadError")));
    return () => {
      cancelled = true;
    };
  }, [tab, t]);

  const createApiToken = async () => {
    setApiTokBusy(true);
    setApiTokError("");
    setNewApiToken("");
    try {
      const res = await authService.createApiToken(apiTokLabel.trim());
      setNewApiToken(res.data.token);
      setApiTokLabel("");
      const list = await authService.listApiTokens();
      setApiTokens(list.data.tokens || []);
    } catch (err) {
      setApiTokError(err.response?.data?.detail || t("settings.apiAccess.createError"));
    } finally {
      setApiTokBusy(false);
    }
  };

  const revokeApiToken = async (id) => {
    setApiTokError("");
    try {
      await authService.revokeApiToken(id);
      setApiTokens((prev) => prev.filter((tk) => tk.id !== id));
    } catch (err) {
      setApiTokError(err.response?.data?.detail || t("settings.apiAccess.revokeError"));
    }
  };

  const copyNewApiToken = async () => {
    try {
      await navigator.clipboard.writeText(newApiToken);
      setApiTokCopied(true);
      setTimeout(() => setApiTokCopied(false), 1800);
    } catch {
      /* clipboard unavailable — user can select manually */
    }
  };

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
  const [nameInput, setNameInput] = useState("");
  const [nameMsg, setNameMsg] = useState({ type: "", text: "" });
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

  const sendTestDigest = async (cadence = "daily") => {
    setNotifMsg({ type: "", text: "" });
    try {
      const r = await notificationsService.sendDigestNow(cadence);
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
      // A Google-only account has no password yet; send an empty current password.
      await authService.changePassword(hasPassword ? pw.current : "", pw.next);
      setPw({ current: "", next: "", confirm: "" });
      await reloadUser();
      setPwMsg({ type: "ok", text: t(hasPassword ? "settings.account.changed" : "settings.account.passwordSet") });
    } catch (err) {
      const detail = err?.response?.data?.detail || t("settings.account.changeError");
      setPwMsg({ type: "error", text: typeof detail === "string" ? detail : t("settings.account.changeError") });
    }
  };

  useEffect(() => {
    if (user?.email) setEmailInput(user.email);
  }, [user?.email]);

  useEffect(() => {
    setNameInput(user?.name || "");
  }, [user?.name]);

  const submitName = async (e) => {
    e.preventDefault();
    setNameMsg({ type: "", text: "" });
    const next = (nameInput || "").trim();
    if (!next || next === (user?.name || "")) return;
    setBusy("name");
    try {
      await authService.updateName(next);
      await reloadUser();
      setNameMsg({ type: "ok", text: t("settings.account.nameUpdated") });
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setNameMsg({
        type: "error",
        text: typeof detail === "string" ? detail : t("settings.account.nameError"),
      });
    } finally {
      setBusy("");
    }
  };

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
    { key: "apiAccess", label: t("settings.tabs.apiAccess"), icon: <Terminal size={16} /> },
    { key: "almanac", label: t("settings.tabs.almanac"), icon: <CalendarDays size={16} /> },
    { key: "notifications", label: t("settings.tabs.notifications"), icon: <Bell size={16} /> },
    { key: "calendar", label: t("settings.tabs.calendar"), icon: <Rss size={16} /> },
    { key: "system", label: t("settings.tabs.system"), icon: <Activity size={16} /> },
    { key: "account", label: t("settings.tabs.account"), icon: <User size={16} /> },
  ];

  // Health-check items surfaced in the System tab. `ok` maps to a green/grey pill.
  const healthChecks = health
    ? [
        { key: "server", label: t("settings.system.server"), ok: health.status === "healthy" },
        { key: "pyjhora", label: t("settings.system.pyjhora"), ok: !!health.engine_available },
        {
          key: "localAi",
          label: t("settings.system.localAi"),
          ok: !!health.local_ai?.available,
          optional: true,
          // Show the actual configured local model + endpoint (from OLLAMA_URL /
          // OLLAMA_DEFAULT_MODEL) so the value is visible even when unreachable.
          value: health.local_ai?.model
            ? `${health.local_ai.model}${health.local_ai.base_url ? ` · ${health.local_ai.base_url}` : ""}`
            : "",
        },
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

            {/* Default pravesha ladder for the period readings. Individual pages
                (Monthly, Varshaphal) can override it locally. */}
            <div className="settings-row settings-row--stack">
              <label className="settings-label">{t("settings.general.praveshaBasis")}</label>
              <div className="settings-segment">
                {[
                  { v: "solar", l: t("settings.general.basisSolar") },
                  { v: "lunar", l: t("settings.general.basisLunar") },
                ].map((o) => (
                  <button
                    key={o.v}
                    type="button"
                    className={`settings-seg-btn${settings.praveshaBasis === o.v ? " is-active" : ""}`}
                    onClick={() => set("praveshaBasis", o.v)}
                  >
                    {o.l}
                  </button>
                ))}
              </div>
              <p className="settings-hint">{t("settings.general.praveshaBasisHint")}</p>
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
                  placeholder={activeProvider?.default_model || t("settings.ai.modelPlaceholder")}
                  onChange={(e) => set("aiModel", e.target.value)}
                />
              )}
            </div>
            {/* When left blank the server falls back to its configured default
                (OLLAMA_DEFAULT_MODEL), so surface it rather than making the user
                retype it — this survives redeploys since it lives server-side. */}
            {!settings.aiModel && activeProvider?.default_model && (
              <p className="settings-hint">
                {t("settings.ai.serverDefault", { model: activeProvider.default_model })}
              </p>
            )}

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

        {/* API ACCESS — public API + MCP tokens (§2.3) */}
        {tab === "apiAccess" && (
          <div className="ui-card settings-panel">
            <h3 className="settings-section-title">{t("settings.apiAccess.title")}</h3>
            <p className="settings-hint">{t("settings.apiAccess.intro")}</p>

            {apiTokError && <div className="settings-msg settings-msg--error">{apiTokError}</div>}

            {/* Freshly-created token — shown once */}
            {newApiToken && (
              <div className="settings-token-new">
                <p className="settings-token-new__label">{t("settings.apiAccess.newTokenLabel")}</p>
                <div className="settings-cal-url">
                  <input type="text" readOnly value={newApiToken} onFocus={(e) => e.target.select()} />
                  <button type="button" className="ui-btn ui-btn--ghost" onClick={copyNewApiToken}>
                    {apiTokCopied ? <Check size={16} /> : <Copy size={16} />}
                    {apiTokCopied ? t("settings.apiAccess.copied") : t("settings.apiAccess.copy")}
                  </button>
                </div>
                <p className="settings-hint settings-token-new__warn">{t("settings.apiAccess.newTokenWarn")}</p>
              </div>
            )}

            {/* Create */}
            <div className="settings-row settings-token-create">
              <input
                className="settings-input"
                type="text"
                value={apiTokLabel}
                placeholder={t("settings.apiAccess.labelPlaceholder")}
                maxLength={80}
                onChange={(e) => setApiTokLabel(e.target.value)}
              />
              <button
                type="button"
                className="ui-btn ui-btn--primary"
                onClick={createApiToken}
                disabled={apiTokBusy}
              >
                <Plus size={16} />
                {apiTokBusy ? t("settings.apiAccess.creating") : t("settings.apiAccess.create")}
              </button>
            </div>

            {/* Existing tokens */}
            {apiTokens.length === 0 ? (
              <p className="settings-hint">{t("settings.apiAccess.empty")}</p>
            ) : (
              <div className="settings-token-list">
                {apiTokens.map((tk) => (
                  <div key={tk.id} className="settings-key-row settings-token-row">
                    <div className="settings-key-head">
                      <span className="settings-key-name">{tk.label}</span>
                      <span className="settings-token-preview">{tk.preview}</span>
                    </div>
                    <div className="settings-token-meta">
                      <span className="settings-hint">
                        {t("settings.apiAccess.lastUsed")}:{" "}
                        {tk.last_used_at ? formatDate(tk.last_used_at) : t("settings.apiAccess.never")}
                      </span>
                      <button
                        type="button"
                        className="control-btn control-btn--ghost"
                        onClick={() => revokeApiToken(tk.id)}
                      >
                        {t("settings.apiAccess.revoke")}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <p className="settings-hint settings-token-docs">{t("settings.apiAccess.docs")}</p>
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

            {/* Cadence switches: daily / fortnightly / monthly, each with its own
                schedule. The delivery channels + profile picks below are shared. */}
            {(() => {
              const hourOptions = Array.from({ length: 24 }, (_, h) => (
                <option key={h} value={h}>{String(h).padStart(2, "0")}:00</option>
              ));
              const anyDigest = !!(notif?.daily_digest || notif?.fortnightly || notif?.monthly);
              return (
                <>
                  {/* Daily */}
                  <div className="settings-row">
                    <label className="settings-label">{t("settings.notifications.dailyDigest")}</label>
                    <label className="settings-switch">
                      <input type="checkbox" checked={!!notif?.daily_digest}
                        onChange={(e) => saveNotif({ daily_digest: e.target.checked })} />
                      <span />
                    </label>
                  </div>
                  {notif?.daily_digest && (
                    <div className="settings-row">
                      <label className="settings-label">{t("settings.notifications.hour")}</label>
                      <select className="form-select" value={notif?.hour ?? 7}
                        onChange={(e) => saveNotif({ hour: parseInt(e.target.value, 10) })}>
                        {hourOptions}
                      </select>
                    </div>
                  )}

                  {/* Fortnightly — the paksha boundary IS the schedule, so there's
                      no day picker: it fires when a new lunar fortnight opens. */}
                  <div className="settings-row">
                    <label className="settings-label">{t("settings.notifications.fortnightlyDigest")}</label>
                    <label className="settings-switch">
                      <input type="checkbox" checked={!!notif?.fortnightly}
                        onChange={(e) => saveNotif({ fortnightly: e.target.checked })} />
                      <span />
                    </label>
                  </div>
                  {notif?.fortnightly && (
                    <>
                      <div className="settings-row">
                        <label className="settings-label">{t("settings.notifications.hour")}</label>
                        <select className="form-select" value={notif?.fortnightly_hour ?? 7}
                          onChange={(e) => saveNotif({ fortnightly_hour: parseInt(e.target.value, 10) })}>
                          {hourOptions}
                        </select>
                      </div>
                      <p className="settings-hint">{t("settings.notifications.fortnightlyNote")}</p>
                    </>
                  )}

                  {/* Monthly */}
                  <div className="settings-row">
                    <label className="settings-label">{t("settings.notifications.monthlyDigest")}</label>
                    <label className="settings-switch">
                      <input type="checkbox" checked={!!notif?.monthly}
                        onChange={(e) => saveNotif({ monthly: e.target.checked })} />
                      <span />
                    </label>
                  </div>
                  {notif?.monthly && (
                    <>
                      <div className="settings-row">
                        <label className="settings-label">{t("settings.notifications.dayOfMonth")}</label>
                        <select className="form-select" value={notif?.monthly_dom ?? 1}
                          onChange={(e) => saveNotif({ monthly_dom: parseInt(e.target.value, 10) })}>
                          {Array.from({ length: 28 }, (_, i) => (
                            <option key={i + 1} value={i + 1}>{i + 1}</option>
                          ))}
                        </select>
                      </div>
                      <div className="settings-row">
                        <label className="settings-label">{t("settings.notifications.hour")}</label>
                        <select className="form-select" value={notif?.monthly_hour ?? 7}
                          onChange={(e) => saveNotif({ monthly_hour: parseInt(e.target.value, 10) })}>
                          {hourOptions}
                        </select>
                      </div>
                    </>
                  )}

                  {!anyDigest ? null : (
                  <>
                {/* Which profiles — an "all" shortcut plus a per-profile pick list.
                    Falls back to the legacy single profile_id when neither is set. */}
                <div className="settings-row settings-row--stack">
                  <label className="settings-label">{t("settings.notifications.profiles")}</label>
                  <label className="settings-check">
                    <input
                      type="checkbox"
                      checked={!!notif?.all_profiles}
                      onChange={(e) => saveNotif({ all_profiles: e.target.checked })}
                    />
                    <span>{t("settings.notifications.allProfiles")}</span>
                  </label>
                  {!notif?.all_profiles && (
                    <div className="settings-checklist">
                      {(profiles || []).map((p) => {
                        const selected = notif?.profile_ids || [];
                        const legacyOnly = selected.length === 0 && notif?.profile_id;
                        const isOn = selected.includes(p._id) || legacyOnly === p._id;
                        return (
                          <label key={p._id} className="settings-check">
                            <input
                              type="checkbox"
                              checked={!!isOn}
                              onChange={(e) => {
                                const base = selected.length === 0 && notif?.profile_id
                                  ? [notif.profile_id]
                                  : selected;
                                const next = e.target.checked
                                  ? [...new Set([...base, p._id])]
                                  : base.filter((id) => id !== p._id);
                                saveNotif({ profile_ids: next, profile_id: null });
                              }}
                            />
                            <span>{p.profile_name || p.birth_details?.name}</span>
                          </label>
                        );
                      })}
                      {(profiles || []).length === 0 && (
                        <p className="settings-hint">{t("settings.notifications.noProfiles")}</p>
                      )}
                    </div>
                  )}
                </div>

                {/* Which pravesha ladder the delivered readings are cast on. */}
                <div className="settings-row settings-row--stack">
                  <label className="settings-label">{t("settings.notifications.basis")}</label>
                  <select
                    className="form-select"
                    value={notif?.basis || "solar"}
                    onChange={(e) => saveNotif({ basis: e.target.value })}
                  >
                    <option value="solar">{t("settings.notifications.basisSolar")}</option>
                    <option value="lunar">{t("settings.notifications.basisLunar")}</option>
                  </select>
                  <p className="settings-hint">{t("settings.notifications.basisHint")}</p>
                </div>

                {/* AI "how the day/fortnight/month looks" narrative */}
                <div className="settings-row">
                  <label className="settings-label">{t("settings.notifications.includeAi")}</label>
                  <label className="settings-switch">
                    <input
                      type="checkbox"
                      checked={notif?.include_ai !== false}
                      onChange={(e) => saveNotif({ include_ai: e.target.checked })}
                    />
                    <span />
                  </label>
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

                {/* Per-cadence "send me one now" tests, only for enabled cadences. */}
                <div className="settings-test-row">
                  {notif?.daily_digest && (
                    <button type="button" className="settings-link" onClick={() => sendTestDigest("daily")}>
                      {t("settings.notifications.sendTestDaily")}
                    </button>
                  )}
                  {notif?.fortnightly && (
                    <button type="button" className="settings-link" onClick={() => sendTestDigest("fortnightly")}>
                      {t("settings.notifications.sendTestFortnightly")}
                    </button>
                  )}
                  {notif?.monthly && (
                    <button type="button" className="settings-link" onClick={() => sendTestDigest("monthly")}>
                      {t("settings.notifications.sendTestMonthly")}
                    </button>
                  )}
                </div>
                  </>
                  )}
                </>
              );
            })()}
            <p className="settings-hint">{t("settings.notifications.note")}</p>
          </div>
        )}

        {/* SYSTEM HEALTH */}
        {/* CALENDAR (iCal feed) */}
        {tab === "calendar" && (
          <div className="ui-card settings-panel">
            <h3 className="settings-section-title">{t("settings.calendar.title")}</h3>
            <p className="settings-hint">{t("settings.calendar.intro")}</p>

            {calError && <div className="settings-msg settings-msg--error">{calError}</div>}

            {profiles?.length > 1 && (
              <div className="settings-row">
                <label className="settings-label">{t("settings.calendar.profile")}</label>
                <select
                  className="settings-input"
                  value={calProfileId}
                  onChange={(e) => setCalProfileId(e.target.value)}
                >
                  {profiles.map((p) => (
                    <option key={p._id} value={p._id}>
                      {p.profile_name || p.birth_details?.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <label className="settings-label">{t("settings.calendar.url")}</label>
            <div className="settings-cal-url">
              <input
                type="text"
                readOnly
                value={calBusy ? t("settings.calendar.loading") : calUrl}
                onFocus={(e) => e.target.select()}
              />
              <button
                type="button"
                className="ui-btn ui-btn--ghost"
                onClick={copyCalUrl}
                disabled={!calUrl}
              >
                {calCopied ? <Check size={16} /> : <Copy size={16} />}
                {calCopied ? t("settings.calendar.copied") : t("settings.calendar.copy")}
              </button>
            </div>
            <p className="settings-hint">{t("settings.calendar.help")}</p>
            <p className="settings-hint">{t("settings.calendar.privacy")}</p>
          </div>
        )}

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
                  <span className="settings-health-name">
                    {c.label}
                    {c.value && <span className="settings-health-value">{c.value}</span>}
                  </span>
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
                <dt>{t("settings.account.name")}</dt>
                <dd>{user?.name || "—"}</dd>
              </div>
              <div>
                <dt>{t("settings.account.username")}</dt>
                <dd>{user?.username || "—"}</dd>
              </div>
              <div>
                <dt>{t("settings.account.memberSince")}</dt>
                <dd>{formatDate(user?.created_at)}</dd>
              </div>
            </dl>

            {/* Name */}
            <hr className="settings-divider" />
            <h3 className="settings-section-title">{t("settings.account.name")}</h3>
            {nameMsg.text && (
              <div className={`settings-pw-msg settings-pw-msg--${nameMsg.type}`}>{nameMsg.text}</div>
            )}
            <form onSubmit={submitName} className="settings-pw-form">
              <input
                className="control-input"
                type="text"
                autoComplete="name"
                placeholder={t("settings.account.namePlaceholder")}
                value={nameInput}
                onChange={(e) => setNameInput(e.target.value)}
                required
              />
              <button
                type="submit"
                className="control-btn"
                disabled={busy === "name" || !nameInput.trim() || nameInput.trim() === (user?.name || "")}
              >
                <User size={14} /> {t("settings.account.updateName")}
              </button>
            </form>

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

            {/* Change / set password */}
            <hr className="settings-divider" />
            <h3 className="settings-section-title">
              {t(hasPassword ? "settings.account.changePassword" : "settings.account.setPassword")}
            </h3>
            {pwMsg.text && (
              <div className={`settings-pw-msg settings-pw-msg--${pwMsg.type}`}>{pwMsg.text}</div>
            )}
            <form onSubmit={submitPassword} className="settings-pw-form">
              {hasPassword && (
                <input
                  className="control-input"
                  type="password"
                  autoComplete="current-password"
                  placeholder={t("settings.account.current")}
                  value={pw.current}
                  onChange={(e) => setPw((p) => ({ ...p, current: e.target.value }))}
                  required
                />
              )}
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
                {t(hasPassword ? "settings.account.changeBtn" : "settings.account.setBtn")}
              </button>
            </form>
            <p className="settings-hint">
              {t(hasPassword ? "settings.account.changeNote" : "settings.account.setNote")}
            </p>

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
