import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Settings as SettingsIcon, Sliders, Key, CalendarDays, User, Sparkles, Check, LogOut } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { useSettings } from "../contexts/SettingsContext";
import { useAuth } from "../contexts/AuthContext";
import { authService, astrologyService } from "../services/api";
import { AYANAMSAS } from "../constants/jyotish";
import { LANGUAGES } from "../i18n";
import "../styles/Settings.css";

const KEYED_PROVIDERS = ["gemini", "openai", "openai-compatible"];
const MT_MIN = 512;
const MT_MAX = 8192;
const MT_STEP = 256;

export const SettingsPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { settings, updateSetting } = useSettings();
  const { logout } = useAuth();

  const [tab, setTab] = useState("general");
  const [savedFlash, setSavedFlash] = useState("");

  // Providers for the AI model picker
  const [providers, setProviders] = useState([]);

  // API keys status
  const [keyStatus, setKeyStatus] = useState({});
  const [keyInputs, setKeyInputs] = useState({});

  // Account
  const [pw, setPw] = useState({ current: "", next: "", confirm: "" });
  const [pwMsg, setPwMsg] = useState({ type: "", text: "" });

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

  const TABS = [
    { key: "general", label: t("settings.tabs.general"), icon: <SettingsIcon size={16} /> },
    { key: "ai", label: t("settings.tabs.ai"), icon: <Sliders size={16} /> },
    { key: "apiKeys", label: t("settings.tabs.apiKeys"), icon: <Key size={16} /> },
    { key: "almanac", label: t("settings.tabs.almanac"), icon: <CalendarDays size={16} /> },
    { key: "account", label: t("settings.tabs.account"), icon: <User size={16} /> },
  ];

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

        {/* ACCOUNT */}
        {tab === "account" && (
          <div className="ui-card settings-panel">
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

            <hr className="settings-divider" />
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
        )}
      </div>
    </div>
  );
};
