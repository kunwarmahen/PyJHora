import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import {
  MessageCircle,
  Send,
  Bot,
  User,
  Sparkles,
  ArrowLeft,
  Star,
  Info,
  X,
  History,
  Plus,
  Trash2,
} from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { formatDate, orDash } from "../utils/format";
import { VARGAS } from "../constants/jyotish";
import { astrologyService, streamAskQuestion } from "../services/api";
import { NorthIndianChart } from "../components/NorthIndianChart";
import "../styles/Dashboard.css";
import "../styles/Chat.css";

const selectStyle = {
  width: "100%",
  marginTop: "var(--space-xs)",
  padding: "var(--space-sm) var(--space-md)",
  borderRadius: "var(--radius-md)",
  border: "1px solid var(--sandalwood)",
  background: "var(--sacred-white)",
  color: "var(--cosmic-indigo)",
  fontSize: "0.9375rem",
  fontFamily: "inherit",
};

export const AskAstrologerPage = () => {
  const navigate = useNavigate();
  const { selectedProfile } = useProfile();

  const [chartData, setChartData] = useState(null);
  const [messages, setMessages] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showInfoModal, setShowInfoModal] = useState(false);
  // The actual structured context the backend assembled for the last answer
  const [lastContext, setLastContext] = useState(null);

  // Conversation persistence + multi-turn
  const [conversationId, setConversationId] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  // AI provider / model selection
  const [providers, setProviders] = useState([]);
  const [providersLoading, setProvidersLoading] = useState(true);
  const [providerType, setProviderType] = useState(
    () => localStorage.getItem("ai_provider_type") || "ollama"
  );
  const [model, setModel] = useState(
    () => localStorage.getItem("ai_model") || ""
  );
  const [baseUrl, setBaseUrl] = useState(
    () => localStorage.getItem("ai_base_url") || ""
  );
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Divisional charts to include in the AI context (D1 is always the natal base)
  const [selectedVargas, setSelectedVargas] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("ai_vargas"));
      if (Array.isArray(saved) && saved.length) return saved;
    } catch (e) {
      /* ignore */
    }
    return [1, 9, 10];
  });

  useEffect(() => {
    localStorage.setItem("ai_vargas", JSON.stringify(selectedVargas));
  }, [selectedVargas]);

  const toggleVarga = (value) => {
    setSelectedVargas((prev) =>
      prev.includes(value)
        ? prev.filter((v) => v !== value)
        : [...prev, value].sort((a, b) => a - b)
    );
  };

  const PROVIDER_ICONS = {
    ollama: "🤖",
    "openai-compatible": "💻",
    gemini: "✨",
    openai: "🧠",
  };

  const selectedProvider =
    providers.find((p) => p.type === providerType) || null;

  // Persist choices
  useEffect(() => {
    localStorage.setItem("ai_provider_type", providerType);
  }, [providerType]);
  useEffect(() => {
    localStorage.setItem("ai_model", model || "");
  }, [model]);
  useEffect(() => {
    localStorage.setItem("ai_base_url", baseUrl || "");
  }, [baseUrl]);

  // Load available providers + models on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setProvidersLoading(true);
      try {
        const resp = await astrologyService.getLlmProviders();
        if (cancelled) return;
        const list = resp.data.providers || [];
        setProviders(list);

        // Pick a sensible provider: keep saved choice if it exists, else first available
        const saved = list.find((p) => p.type === providerType);
        const target =
          saved || list.find((p) => p.available) || list[0] || null;
        if (target) {
          if (target.type !== providerType) setProviderType(target.type);
          // Pick a model: keep saved if valid for this provider, else default/first
          const validModel =
            (target.type === providerType &&
              model &&
              (target.models.length === 0 || target.models.includes(model)) &&
              model) ||
            target.default_model ||
            target.models[0] ||
            "";
          setModel(validModel);
          setBaseUrl(target.editable_base_url ? target.base_url || "" : "");
        }
      } catch (e) {
        if (!cancelled) setProviders([]);
      } finally {
        if (!cancelled) setProvidersLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // When the provider changes, reset model + base URL to that provider's defaults
  const handleProviderChange = (newType) => {
    setProviderType(newType);
    const p = providers.find((x) => x.type === newType);
    if (p) {
      setModel(p.default_model || p.models[0] || "");
      setBaseUrl(p.editable_base_url ? p.base_url || "" : "");
    } else {
      setModel("");
      setBaseUrl("");
    }
  };

  const exampleQuestions = [
    "What are my strengths and weaknesses based on my chart?",
    "When is a good time for marriage?",
    "Which career path suits me best?",
    "What remedies can help with current challenges?",
    "How will the next 6 months be for me?",
    "What does my moon sign reveal about my personality?",
  ];

  // Redirect if no profile selected
  useEffect(() => {
    if (!selectedProfile) {
      navigate('/profile-selection');
      return;
    }

    // Auto-calculate chart + load saved conversations on mount
    calculateChart();
    refreshConversations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProfile, navigate]);

  const calculateChart = async () => {
    if (!selectedProfile) return;

    setLoading(true);
    setError("");

    try {
      const birthDetails = {
        name: selectedProfile.birth_details.name,
        dob: selectedProfile.birth_details.dob,
        tob: selectedProfile.birth_details.tob,
        place: selectedProfile.birth_details.place,
        latitude: parseFloat(selectedProfile.birth_details.latitude),
        longitude: parseFloat(selectedProfile.birth_details.longitude),
        timezone: parseFloat(selectedProfile.birth_details.timezone),
      };

      // Fetch both chart data and dasha data
      const [chartResponse, dashaResponse] = await Promise.all([
        astrologyService.calculateBirthChart(birthDetails),
        astrologyService.getDhasa(birthDetails, "vimsottari")
      ]);

      // Combine chart data with dasha data
      setChartData({
        ...chartResponse.data,
        dashas: dashaResponse.data
      });
      setMessages([
        {
          type: "system",
          content: `Chart ready for ${selectedProfile.birth_details.name || selectedProfile.profile_name}. Ask me anything about this birth chart!`,
        },
      ]);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to calculate chart");
    } finally {
      setLoading(false);
    }
  };

  const buildBirthDetails = () => ({
    name: selectedProfile.birth_details.name,
    dob: selectedProfile.birth_details.dob,
    tob: selectedProfile.birth_details.tob,
    place: selectedProfile.birth_details.place,
    latitude: parseFloat(selectedProfile.birth_details.latitude),
    longitude: parseFloat(selectedProfile.birth_details.longitude),
    timezone: parseFloat(selectedProfile.birth_details.timezone),
  });

  // Update the most recent AI message in place (used while streaming)
  const updateLastAi = (updater) =>
    setMessages((prev) => {
      const next = [...prev];
      for (let i = next.length - 1; i >= 0; i--) {
        if (next[i].type === "ai") {
          next[i] = updater(next[i]);
          break;
        }
      }
      return next;
    });

  const handleAskQuestion = (question) => {
    if (!question.trim() || !selectedProfile || loading) return;

    const now = new Date().toLocaleTimeString();
    setMessages((prev) => [
      ...prev,
      { type: "user", content: question, timestamp: now },
      {
        type: "ai",
        content: "",
        streaming: true,
        provider: providerType,
        model,
        timestamp: new Date().toLocaleTimeString(),
      },
    ]);
    setCurrentQuestion("");
    setLoading(true);
    setError("");

    streamAskQuestion(
      buildBirthDetails(),
      question,
      {
        providerType,
        model,
        baseUrl: selectedProvider?.editable_base_url ? baseUrl : undefined,
        legacyProvider: providerType === "ollama" ? "qwen" : providerType,
        vargas: selectedVargas,
        conversationId,
        profileId: selectedProfile._id,
      },
      {
        onMeta: (m) => {
          if (m.context) setLastContext(m.context);
          updateLastAi((msg) => ({
            ...msg,
            provider: m.provider || msg.provider,
            model: m.model || msg.model,
          }));
        },
        onToken: (t) =>
          updateLastAi((msg) => ({ ...msg, content: msg.content + t })),
        onDone: (d) => {
          if (d.conversation_id) setConversationId(d.conversation_id);
          updateLastAi((msg) => ({ ...msg, streaming: false }));
          setLoading(false);
          refreshConversations();
        },
        onError: (e) => {
          updateLastAi((msg) => ({
            ...msg,
            streaming: false,
            error: !msg.content,
            content: msg.content || `Error: ${e.message}`,
          }));
          setError(e.message || "Failed to get answer from AI");
          setLoading(false);
        },
      }
    );
  };

  const handleExampleClick = (question) => {
    handleAskQuestion(question);
  };

  // ── Conversation history ────────────────────────────────────────────
  const refreshConversations = async () => {
    if (!selectedProfile?._id) return;
    try {
      const resp = await astrologyService.listConversations(selectedProfile._id);
      setConversations(resp.data.conversations || []);
    } catch (e) {
      /* non-fatal */
    }
  };

  const startNewConversation = () => {
    setConversationId(null);
    setLastContext(null);
    setMessages([
      {
        type: "system",
        content: `New conversation for ${
          selectedProfile.birth_details.name || selectedProfile.profile_name
        }. Ask me anything about this birth chart!`,
      },
    ]);
    setShowHistory(false);
  };

  const loadConversation = async (id) => {
    try {
      const resp = await astrologyService.getConversation(id);
      const conv = resp.data;
      const msgs = (conv.messages || []).map((m) =>
        m.role === "user"
          ? { type: "user", content: m.content }
          : { type: "ai", content: m.content, provider: m.provider, model: m.model }
      );
      setMessages(
        msgs.length
          ? msgs
          : [{ type: "system", content: "This conversation is empty." }]
      );
      setConversationId(id);
      setShowHistory(false);
    } catch (e) {
      setError("Failed to load conversation");
    }
  };

  const handleDeleteConversation = async (id, e) => {
    e.stopPropagation();
    try {
      await astrologyService.deleteConversation(id);
      if (id === conversationId) startNewConversation();
      refreshConversations();
    } catch (err) {
      /* non-fatal */
    }
  };

  const getChartDataForLLM = () => {
    if (!chartData) return "No chart data available";

    const moonData = chartData.d1_chart?.Moon || {};
    const sunData = chartData.d1_chart?.Sun || {};

    return {
      birth_details: {
        dob: selectedProfile.birth_details.dob,
        tob: selectedProfile.birth_details.tob,
        place: selectedProfile.birth_details.place,
      },
      lagna: chartData.lagna,
      moon_sign: {
        sign_name: moonData.sign_name || "Unknown",
        rasi: moonData.rasi || 0,
        nakshatra: moonData.nakshatra || "Unknown",
        nakshatra_pada: moonData.nakshatra_pada || 0,
      },
      sun_sign: {
        sign_name: sunData.sign_name || "Unknown",
        rasi: sunData.rasi || 0,
        nakshatra: sunData.nakshatra || "Unknown",
        nakshatra_pada: sunData.nakshatra_pada || 0,
      },
      planetary_positions: chartData.d1_chart || {},
      current_dasha: chartData.dashas?.current_dasha || {},
      next_dasha: chartData.dashas?.next_dasha || {},
      current_bhukthi: chartData.dashas?.current_bhukthi || {},
      dasha_sequence: chartData.dashas?.dasha_sequence || []
    };
  };

  if (!selectedProfile) {
    return null;
  }

  return (
    <div className="dashboard-container mandala-bg">
      {/* Navbar */}
      <nav className="navbar">
        <div className="navbar-brand">
          <button onClick={() => navigate('/dashboard')} style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-sm)',
            color: 'var(--saffron)',
            padding: 'var(--space-sm) var(--space-md)',
            borderRadius: 'var(--radius-md)',
            transition: 'all 0.3s ease'
          }}
          onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255, 153, 51, 0.1)'}
          onMouseOut={(e) => e.currentTarget.style.background = 'none'}>
            <ArrowLeft size={20} />
            <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>Back</span>
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)', marginLeft: 'var(--space-lg)' }}>
            <div style={{
              width: '48px',
              height: '48px',
              background: 'linear-gradient(135deg, var(--terracotta) 0%, var(--vermillion) 100%)',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white'
            }}>
              <MessageCircle size={24} />
            </div>
            <div>
              <h1 style={{ margin: 0, fontSize: '1.5rem' }}>Ask AI Astrologer</h1>
              <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                Get personalized insights from AI
              </p>
            </div>
          </div>
        </div>
      </nav>

      {/* Content */}
      <div className="dashboard-content">
        {/* Profile Banner */}
        <div className="profile-banner fade-in">
          <div className="profile-banner-left">
            <div className="profile-avatar-large">
              <User size={32} />
            </div>
            <div className="profile-info">
              <h2>{selectedProfile.profile_name}</h2>
              <div className="profile-meta">
                <span>{selectedProfile.birth_details.name || 'Anonymous'}</span>
                <span className="separator">•</span>
                <span>{formatDate(selectedProfile.birth_details.dob)}</span>
                <span className="separator">•</span>
                <span>{orDash(selectedProfile.birth_details.place)}</span>
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap' }}>
            <button onClick={startNewConversation} className="change-profile-btn">
              <Plus size={16} />
              <span>New Chat</span>
            </button>
            <button
              onClick={() => { setShowHistory((v) => !v); refreshConversations(); }}
              className="change-profile-btn"
            >
              <History size={16} />
              <span>History{conversations.length ? ` (${conversations.length})` : ""}</span>
            </button>
            <button onClick={() => navigate('/profile-selection')} className="change-profile-btn">
              <Star size={16} />
              <span>Change Chart</span>
            </button>
          </div>
        </div>

        {/* History panel */}
        {showHistory && (
          <div style={{
            background: 'white',
            borderRadius: 'var(--radius-xl)',
            padding: 'var(--space-xl)',
            boxShadow: 'var(--shadow-lg)',
            borderTop: '4px solid var(--saffron)',
            marginBottom: 'var(--space-xl)',
          }}>
            <h3 style={{
              display: 'flex', alignItems: 'center', gap: 'var(--space-sm)',
              marginBottom: 'var(--space-lg)', color: 'var(--cosmic-indigo)',
              fontSize: '1.25rem', fontWeight: 700,
            }}>
              <History size={20} style={{ color: 'var(--saffron)' }} />
              Saved Conversations
            </h3>
            {conversations.length === 0 ? (
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', margin: 0 }}>
                No saved conversations yet. Ask a question to start one.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
                {conversations.map((c) => (
                  <div
                    key={c.id}
                    onClick={() => loadConversation(c.id)}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      gap: 'var(--space-md)', padding: 'var(--space-md)',
                      borderRadius: 'var(--radius-md)', cursor: 'pointer',
                      border: `1px solid ${c.id === conversationId ? 'var(--saffron)' : 'var(--sandalwood)'}`,
                      background: c.id === conversationId ? 'rgba(255, 153, 51, 0.08)' : 'white',
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <div style={{
                        fontWeight: 600, color: 'var(--cosmic-indigo)', fontSize: '0.9375rem',
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        {c.title}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                        {Math.floor((c.message_count || 0) / 2)} Q&A
                        {c.last_model ? ` · ${c.last_model}` : ""}
                        {c.updated_at ? ` · ${formatDate(c.updated_at)}` : ""}
                      </div>
                    </div>
                    <button
                      onClick={(e) => handleDeleteConversation(c.id, e)}
                      title="Delete conversation"
                      style={{
                        background: 'none', border: 'none', cursor: 'pointer',
                        color: 'var(--text-secondary)', padding: 'var(--space-xs)',
                        display: 'flex', flexShrink: 0,
                      }}
                      onMouseOver={(e) => (e.currentTarget.style.color = 'var(--vermillion)')}
                      onMouseOut={(e) => (e.currentTarget.style.color = 'var(--text-secondary)')}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Display Birth Chart */}
        {chartData && (
          <div style={{ opacity: 0, animation: 'fadeIn 0.6s ease-out 0.2s forwards' }}>
            <NorthIndianChart chartData={chartData} />
          </div>
        )}

        {/* AI Model Selector and Examples */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: 'var(--space-lg)',
          marginBottom: 'var(--space-xl)',
          opacity: 0,
          animation: 'fadeIn 0.6s ease-out 0.4s forwards'
        }}>
          {/* LLM Selector Card */}
          <div style={{
            background: 'white',
            borderRadius: 'var(--radius-xl)',
            padding: 'var(--space-xl)',
            boxShadow: 'var(--shadow-lg)',
            borderTop: '4px solid var(--saffron)'
          }}>
            <h3 style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-sm)',
              marginBottom: 'var(--space-lg)',
              color: 'var(--cosmic-indigo)',
              fontSize: '1.25rem',
              fontWeight: 700
            }}>
              <Bot size={20} style={{ color: 'var(--saffron)' }} />
              AI Model
              <button
                onClick={() => setShowInfoModal(true)}
                style={{
                  marginLeft: 'auto',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--saffron)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-xs)',
                  padding: 'var(--space-xs)',
                  borderRadius: 'var(--radius-sm)',
                  transition: 'all 0.3s ease'
                }}
                onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255, 153, 51, 0.1)'}
                onMouseOut={(e) => e.currentTarget.style.background = 'none'}
                title="View chart data sent to AI"
              >
                <Info size={18} />
                <span style={{ fontSize: '0.75rem', fontWeight: 500 }}>Info</span>
              </button>
            </h3>
            {providersLoading ? (
              <div style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                Detecting available models…
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
                {/* Provider */}
                <label style={{ display: 'block' }}>
                  <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                    Provider
                  </span>
                  <select
                    value={providerType}
                    onChange={(e) => handleProviderChange(e.target.value)}
                    style={selectStyle}
                  >
                    {providers.map((p) => (
                      <option key={p.type} value={p.type}>
                        {PROVIDER_ICONS[p.type] || "•"} {p.label}
                        {p.available ? "" : " — unavailable"}
                      </option>
                    ))}
                  </select>
                </label>

                {/* Model */}
                <label style={{ display: 'block' }}>
                  <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                    Model
                  </span>
                  {selectedProvider && selectedProvider.models.length > 0 ? (
                    <select
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      style={selectStyle}
                    >
                      {!selectedProvider.models.includes(model) && model && (
                        <option value={model}>{model} (custom)</option>
                      )}
                      {selectedProvider.models.map((m) => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      placeholder="Enter model name (e.g. llama3.1:8b)"
                      style={selectStyle}
                    />
                  )}
                </label>

                {/* Availability note */}
                {selectedProvider && !selectedProvider.available && (
                  <div style={{
                    fontSize: '0.8125rem',
                    color: 'var(--vermillion)',
                    background: 'rgba(229, 57, 53, 0.08)',
                    border: '1px solid rgba(229, 57, 53, 0.25)',
                    borderRadius: 'var(--radius-md)',
                    padding: 'var(--space-sm) var(--space-md)',
                  }}>
                    ⚠ {selectedProvider.reason || "This provider is not reachable."}
                  </div>
                )}

                {/* Advanced: editable base URL for local providers */}
                {selectedProvider && selectedProvider.editable_base_url && (
                  <div>
                    <button
                      type="button"
                      onClick={() => setShowAdvanced((v) => !v)}
                      style={{
                        background: 'none', border: 'none', cursor: 'pointer',
                        color: 'var(--saffron)', fontSize: '0.8125rem', fontWeight: 600,
                        padding: 0,
                      }}
                    >
                      {showAdvanced ? "▾" : "▸"} Advanced (endpoint URL)
                    </button>
                    {showAdvanced && (
                      <input
                        type="text"
                        value={baseUrl}
                        onChange={(e) => setBaseUrl(e.target.value)}
                        placeholder={selectedProvider.base_url}
                        style={{ ...selectStyle, marginTop: 'var(--space-sm)' }}
                      />
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Examples Card */}
          <div style={{
            background: 'white',
            borderRadius: 'var(--radius-xl)',
            padding: 'var(--space-xl)',
            boxShadow: 'var(--shadow-lg)',
            borderTop: '4px solid var(--saffron)'
          }}>
            <h3 style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-sm)',
              marginBottom: 'var(--space-lg)',
              color: 'var(--cosmic-indigo)',
              fontSize: '1.25rem',
              fontWeight: 700
            }}>
              <MessageCircle size={20} style={{ color: 'var(--saffron)' }} />
              Example Questions
            </h3>
            {exampleQuestions.map((q, index) => (
              <button
                key={index}
                className="example-question"
                onClick={() => handleExampleClick(q)}
                disabled={loading}
              >
                {q}
              </button>
            ))}
          </div>

          {/* Divisional Charts (Vargas) Card */}
          <div style={{
            background: 'white',
            borderRadius: 'var(--radius-xl)',
            padding: 'var(--space-xl)',
            boxShadow: 'var(--shadow-lg)',
            borderTop: '4px solid var(--saffron)'
          }}>
            <h3 style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-sm)',
              marginBottom: 'var(--space-xs)',
              color: 'var(--cosmic-indigo)',
              fontSize: '1.25rem',
              fontWeight: 700
            }}>
              <Star size={20} style={{ color: 'var(--saffron)' }} />
              Charts to Consult
            </h3>
            <p style={{ margin: '0 0 var(--space-md)', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
              Pick which divisional charts the AI should weigh. D1 (Rasi) is always included.
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)' }}>
              {VARGAS.map((v) => {
                const active = selectedVargas.includes(v.value);
                const isD1 = v.value === 1;
                return (
                  <button
                    key={v.value}
                    type="button"
                    onClick={() => !isD1 && toggleVarga(v.value)}
                    disabled={isD1}
                    title={`${v.name} — ${v.significance}`}
                    style={{
                      cursor: isD1 ? 'default' : 'pointer',
                      padding: 'var(--space-xs) var(--space-md)',
                      borderRadius: 'var(--radius-md)',
                      fontSize: '0.8125rem',
                      fontWeight: 600,
                      border: `1px solid ${active ? 'var(--saffron)' : 'var(--sandalwood)'}`,
                      background: active ? 'rgba(255, 153, 51, 0.12)' : 'white',
                      color: active ? 'var(--vermillion)' : 'var(--text-secondary)',
                      opacity: isD1 ? 0.8 : 1,
                    }}
                  >
                    {v.code}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Chat Area */}
        <div style={{
          background: 'white',
          borderRadius: 'var(--radius-xl)',
          boxShadow: 'var(--shadow-lg)',
          borderTop: '4px solid var(--saffron)',
          display: 'flex',
          flexDirection: 'column',
          minHeight: '500px',
          maxHeight: '700px',
          opacity: 0,
          animation: 'fadeIn 0.6s ease-out 0.6s forwards'
        }}>
          <div className="messages-container" style={{
            flex: 1,
            overflowY: 'auto',
            padding: 'var(--space-xl)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-lg)',
            background: 'var(--sacred-white)'
          }}>
            {messages.map((message, index) => (
              <div key={index} className={`message ${message.type}`}>
                {message.type === "user" && (
                  <div className="message-header">
                    <User size={18} />
                    <span>You</span>
                    <span className="timestamp">{message.timestamp}</span>
                  </div>
                )}
                {message.type === "ai" && (
                  <div className="message-header">
                    <Bot size={18} />
                    <span>
                      AI Astrologer
                      {message.model
                        ? ` · ${message.model}`
                        : message.provider
                        ? ` (${message.provider})`
                        : ""}
                    </span>
                    <span className="timestamp">{message.timestamp}</span>
                  </div>
                )}
                {message.type === "system" && (
                  <div className="message-header">
                    <Sparkles size={18} />
                    <span>System</span>
                  </div>
                )}
                <div className="message-content">
                  {message.type === "ai" ? (
                    message.streaming && !message.content ? (
                      <div className="loading">
                        <div className="typing-indicator">
                          <span></span>
                          <span></span>
                          <span></span>
                        </div>
                        Consulting the chart…
                      </div>
                    ) : (
                      <>
                        <ReactMarkdown>{message.content}</ReactMarkdown>
                        {message.streaming && (
                          <span className="stream-cursor">▍</span>
                        )}
                      </>
                    )
                  ) : (
                    message.content
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="chat-input-container" style={{
            display: 'flex',
            gap: 'var(--space-sm)',
            padding: 'var(--space-lg)',
            borderTop: '2px solid var(--sandalwood)',
            background: 'white'
          }}>
            <input
              type="text"
              className="chat-input"
              placeholder="Ask a question about your birth chart..."
              value={currentQuestion}
              onChange={(e) => setCurrentQuestion(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === "Enter" && !loading) {
                  handleAskQuestion(currentQuestion);
                }
              }}
              disabled={loading}
            />
            <button
              className="btn-send"
              onClick={() => handleAskQuestion(currentQuestion)}
              disabled={loading || !currentQuestion.trim()}
            >
              <Send size={20} />
            </button>
          </div>
        </div>

        {/* Info Modal */}
        {showInfoModal && (
          <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: 'var(--space-lg)',
            animation: 'fadeIn 0.3s ease-out'
          }}
          onClick={() => setShowInfoModal(false)}>
            <div style={{
              background: 'white',
              borderRadius: 'var(--radius-xl)',
              maxWidth: '800px',
              width: '100%',
              maxHeight: '80vh',
              overflow: 'auto',
              boxShadow: '0 20px 60px rgba(0, 0, 0, 0.3)',
              animation: 'slideIn 0.3s ease-out'
            }}
            onClick={(e) => e.stopPropagation()}>
              {/* Modal Header */}
              <div style={{
                padding: 'var(--space-xl)',
                borderBottom: '2px solid var(--sandalwood)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                position: 'sticky',
                top: 0,
                background: 'white',
                zIndex: 1
              }}>
                <h3 style={{
                  margin: 0,
                  fontSize: '1.5rem',
                  color: 'var(--cosmic-indigo)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-sm)'
                }}>
                  <Info size={24} style={{ color: 'var(--saffron)' }} />
                  Chart Data Sent to AI
                </h3>
                <button
                  onClick={() => setShowInfoModal(false)}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'var(--text-secondary)',
                    padding: 'var(--space-sm)',
                    borderRadius: 'var(--radius-md)',
                    transition: 'all 0.3s ease'
                  }}
                  onMouseOver={(e) => {
                    e.currentTarget.style.background = 'var(--sandalwood)';
                    e.currentTarget.style.color = 'var(--vermillion)';
                  }}
                  onMouseOut={(e) => {
                    e.currentTarget.style.background = 'none';
                    e.currentTarget.style.color = 'var(--text-secondary)';
                  }}
                >
                  <X size={24} />
                </button>
              </div>

              {/* Modal Content */}
              <div style={{
                padding: 'var(--space-xl)',
                fontSize: '0.875rem',
                lineHeight: '1.6'
              }}>
                <div style={{
                  background: 'linear-gradient(135deg, rgba(255, 153, 51, 0.05) 0%, rgba(255, 153, 51, 0.1) 100%)',
                  padding: 'var(--space-lg)',
                  borderRadius: 'var(--radius-lg)',
                  marginBottom: 'var(--space-lg)',
                  border: '1px solid var(--saffron)'
                }}>
                  <p style={{ margin: 0, color: 'var(--cosmic-indigo)', fontWeight: 500 }}>
                    {lastContext
                      ? "This is the exact structured context the backend assembled and sent to the AI model for your last question:"
                      : "This is the chart information that will be sent to the AI model. The backend also adds your full running dasha chain, yogas, doshas and current transits — visible here after you ask a question:"}
                  </p>
                </div>

                <pre style={{
                  background: 'var(--sacred-white)',
                  padding: 'var(--space-lg)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--sandalwood)',
                  overflow: 'auto',
                  fontFamily: 'monospace',
                  fontSize: '0.8125rem',
                  lineHeight: '1.8',
                  color: 'var(--cosmic-indigo)'
                }}>
{JSON.stringify(lastContext || getChartDataForLLM(), null, 2)}
                </pre>

                <div style={{
                  marginTop: 'var(--space-lg)',
                  padding: 'var(--space-md)',
                  background: 'rgba(52, 73, 94, 0.05)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--cosmic-indigo)',
                  fontSize: '0.8125rem'
                }}>
                  <p style={{ margin: '0 0 var(--space-sm) 0', color: 'var(--cosmic-indigo)', fontWeight: 600 }}>
                    📝 Note:
                  </p>
                  <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
                    The AI model receives this structured data along with your question: your Lagna, planetary positions and nakshatras, the currently-active Vimsottari dasha chain (Maha → Bhukti → Antara → Sookshma), yogas and doshas present in the chart, and current planetary transits (Gochara).
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
