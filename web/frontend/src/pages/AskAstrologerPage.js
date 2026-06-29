import React, { useState, useEffect, useLayoutEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import {
  MessageCircle,
  Send,
  Bot,
  User,
  Sparkles,
  Star,
  Info,
  X,
  History,
  Plus,
  Trash2,
  Copy,
  Check,
  RefreshCw,
  ThumbsUp,
  ThumbsDown,
  Square,
  Download,
  KeyRound,
  ChevronDown,
  FileText,
  FileType,
  Wrench,
} from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { formatDate } from "../utils/format";
import { VARGAS } from "../constants/jyotish";
import { astrologyService, streamAskQuestion } from "../services/api";
import { exportConversationPdf } from "../utils/exportConversation";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
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

/**
 * A dropdown menu rendered in a portal on document.body with fixed positioning,
 * anchored to a trigger element. This escapes every ancestor stacking context /
 * overflow on the page (the chart cards below the banner create stacking
 * contexts via their fade-in transform, which otherwise hide an in-flow menu).
 * Auto-flips above the anchor when there isn't room below.
 */
const PortalMenu = ({ anchorRef, open, onClose, align = "left", width = 220, children }) => {
  const [pos, setPos] = useState(null);

  useLayoutEffect(() => {
    if (!open || !anchorRef.current) {
      setPos(null);
      return;
    }
    const place = () => {
      const r = anchorRef.current.getBoundingClientRect();
      const openUp = window.innerHeight - r.bottom < 300;
      setPos({
        left: Math.max(8, align === "right" ? r.right - width : r.left),
        top: openUp ? undefined : r.bottom + 4,
        bottom: openUp ? window.innerHeight - r.top + 4 : undefined,
      });
    };
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open, align, width, anchorRef]);

  if (!open || !pos) return null;
  return createPortal(
    <>
      <div className="menu-backdrop" onClick={onClose} />
      <div
        className="portal-menu"
        role="menu"
        style={{ top: pos.top, bottom: pos.bottom, left: pos.left, minWidth: width }}
      >
        {children}
      </div>
    </>,
    document.body
  );
};

export const AskAstrologerPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { selectedProfile } = useProfile();

  const [chartData, setChartData] = useState(null);
  const [messages, setMessages] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showInfoModal, setShowInfoModal] = useState(false);
  // The actual structured context the backend assembled for the last answer
  const [lastContext, setLastContext] = useState(null);
  // Data currently shown in the info modal (last answer, or a specific message)
  const [modalData, setModalData] = useState(null);

  const openInfo = (data) => {
    setModalData(data || null);
    setShowInfoModal(true);
  };

  // Compact "1.2k" style token count; full breakdown goes in the tooltip.
  const formatTokens = (n) => (n == null ? "" : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n}`);

  const usageLabel = (u) => {
    if (!u) return null;
    const total = u.total_tokens ?? (u.prompt_tokens || 0) + (u.completion_tokens || 0);
    if (!total) return null;
    const parts = [];
    if (u.prompt_tokens != null) parts.push(`${u.prompt_tokens} ${t("ask.promptTokens")}`);
    if (u.completion_tokens != null)
      parts.push(`${u.completion_tokens} ${t("ask.completionTokens")}`);
    const tokensWord = t("ask.tokens");
    return {
      short: `${formatTokens(total)} ${tokensWord}`,
      title: parts.length
        ? `${parts.join(" + ")} = ${total} ${tokensWord}`
        : `${total} ${tokensWord}`,
    };
  };

  // What to show for a single AI message: its own context snapshot if we have it
  // (answers from this session), else the metadata stored with the message. In tool
  // mode we also surface the seed + the tools the model called to answer.
  const messageInfo = (m) => {
    const isTools = m.mode === "tools" || (m.toolSteps && m.toolSteps.length > 0);
    if (isTools) {
      return {
        mode: "tools",
        provider: m.provider,
        model: m.model,
        seed_context: m.context || { note: t("ask.snapshotNote") },
        tools_used: (m.toolSteps || []).map((s) =>
          s.notice ? { notice: s.notice } : { tool: s.name, args: s.args, ok: s.ok }
        ),
      };
    }
    return (
      m.context || {
        provider: m.provider,
        model: m.model,
        vargas: m.vargas,
        sections: m.sections,
        note: t("ask.snapshotNote"),
      }
    );
  };

  // Conversation persistence + multi-turn
  const [conversationId, setConversationId] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  // 8.7 polish: in-flight stream control + per-answer affordances
  const abortRef = useRef(null);
  const [copiedIdx, setCopiedIdx] = useState(null);
  // Which messages' "behind the scenes" tool-call trace is expanded (by index).
  const [openTrace, setOpenTrace] = useState({});
  // "Regenerate with a different model" dropdown
  const [regenMenuOpen, setRegenMenuOpen] = useState(false);
  const regenBtnRef = useRef(null);
  // Export menu (Markdown / PDF)
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const exportBtnRef = useRef(null);
  // conversationId stays current across turns via a ref so callbacks see it
  const conversationIdRef = useRef(null);
  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);

  // 8.6 per-user API keys
  const [showKeysModal, setShowKeysModal] = useState(false);
  const [keyStatus, setKeyStatus] = useState({});
  const [keyInputs, setKeyInputs] = useState({});
  const [keySaving, setKeySaving] = useState("");
  const KEY_PROVIDERS = [
    { id: "gemini", label: "Google Gemini", hint: "aistudio.google.com/app/apikey" },
    { id: "openai", label: "OpenAI (ChatGPT)", hint: "platform.openai.com/api-keys" },
    {
      id: "openai-compatible",
      label: "Local / OpenAI-compatible",
      hint: "Optional — only if your endpoint needs a key",
    },
  ];

  // AI provider / model selection
  const [providers, setProviders] = useState([]);
  const [providersLoading, setProvidersLoading] = useState(true);
  const [providerType, setProviderType] = useState(
    () => localStorage.getItem("ai_provider_type") || "ollama"
  );
  const [model, setModel] = useState(() => localStorage.getItem("ai_model") || "");
  const [baseUrl, setBaseUrl] = useState(() => localStorage.getItem("ai_base_url") || "");
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Answer mode: "pass_all" (pre-send the full context) vs "tools" (let the model
  // fetch chart data on demand). Chosen per conversation; locked once a thread has
  // started (its first turn fixes the mode server-side). Default from last choice.
  const [mode, setMode] = useState(() => localStorage.getItem("ai_mode") || "pass_all");
  useEffect(() => {
    localStorage.setItem("ai_mode", mode);
  }, [mode]);

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

  const selectedProvider = providers.find((p) => p.type === providerType) || null;

  // The mode is fixed once a conversation has any AI turn (the backend locks it on
  // the first turn). A brand-new/empty thread can still switch modes.
  const modeLocked = !!conversationId || messages.some((m) => m.type === "ai");

  // "get_dasha_chain" -> "dasha chain" for the step labels.
  const fmtTool = (n) => (n || "").replace(/^get_/, "").replace(/_/g, " ");

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
        const target = saved || list.find((p) => p.available) || list[0] || null;
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

  const exampleQuestions = t("ask.exampleQuestions", { returnObjects: true });

  // Redirect if no profile selected
  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
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
        astrologyService.getDhasa(birthDetails, "vimsottari"),
      ]);

      // Combine chart data with dasha data
      setChartData({
        ...chartResponse.data,
        dashas: dashaResponse.data,
      });
      setMessages([
        {
          type: "system",
          content: `Chart ready for ${selectedProfile.birth_details.name || selectedProfile.profile_name}. Ask me anything about this birth chart!`,
        },
      ]);
    } catch (err) {
      setError(err.response?.data?.detail || t("ask.errChart"));
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

  // Core streaming call — used by both a fresh question and "Regenerate".
  // `override` lets Regenerate run against a different provider/model than the
  // one currently selected in the picker.
  const runStream = (question, { regenerate = false, override = null } = {}) => {
    setLoading(true);
    setError("");

    const useType = override?.providerType || providerType;
    const useModel = override?.model || model;
    const useProvider = providers.find((p) => p.type === useType) || selectedProvider;
    const useBaseUrl = useProvider?.editable_base_url ? (override?.baseUrl ?? baseUrl) : undefined;

    abortRef.current = streamAskQuestion(
      buildBirthDetails(),
      question,
      {
        providerType: useType,
        model: useModel,
        baseUrl: useBaseUrl,
        legacyProvider: useType === "ollama" ? "qwen" : useType,
        vargas: selectedVargas,
        mode,
        conversationId: conversationIdRef.current,
        profileId: selectedProfile._id,
        regenerate,
      },
      {
        onMeta: (m) => {
          if (m.context) setLastContext(m.context);
          updateLastAi((msg) => ({
            ...msg,
            provider: m.provider || msg.provider,
            model: m.model || msg.model,
            mode: m.mode || msg.mode,
            context: m.context || msg.context,
            vargas: m.vargas || msg.vargas,
            sections: m.sections || msg.sections,
          }));
        },
        onToken: (t) => updateLastAi((msg) => ({ ...msg, content: msg.content + t })),
        onToolCall: (e) =>
          updateLastAi((msg) => ({
            ...msg,
            toolSteps: [...(msg.toolSteps || []), { name: e.name, args: e.args, ok: null }],
          })),
        onToolResult: (e) =>
          updateLastAi((msg) => {
            const steps = [...(msg.toolSteps || [])];
            for (let i = steps.length - 1; i >= 0; i--) {
              if (steps[i].name === e.name && steps[i].ok === null) {
                steps[i] = { ...steps[i], ok: e.ok, result: e.result };
                break;
              }
            }
            return { ...msg, toolSteps: steps };
          }),
        onNotice: (e) =>
          updateLastAi((msg) => ({
            ...msg,
            toolSteps: [...(msg.toolSteps || []), { notice: e.text }],
          })),
        onDone: (d) => {
          if (d.conversation_id) setConversationId(d.conversation_id);
          updateLastAi((msg) => ({
            ...msg,
            streaming: false,
            elapsed_ms: d.elapsed_ms ?? msg.elapsed_ms,
            usage: d.usage || msg.usage,
            question, // remember the prompt so Regenerate can replay it
          }));
          setLoading(false);
          abortRef.current = null;
          refreshConversations();
        },
        onError: (e) => {
          updateLastAi((msg) => ({
            ...msg,
            streaming: false,
            error: !msg.content,
            content: msg.content || `Error: ${e.message}`,
          }));
          setError(e.message || t("ask.errAnswer"));
          setLoading(false);
          abortRef.current = null;
        },
      }
    );
  };

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
        question,
        timestamp: new Date().toLocaleTimeString(),
      },
    ]);
    setCurrentQuestion("");
    runStream(question, { regenerate: false });
  };

  // Re-ask the prompt behind the last AI answer; replaces it server-side too.
  // `override` ({ providerType, model }) regenerates with a different model and
  // makes it the active selection going forward.
  const handleRegenerate = (message, override = null) => {
    const question = message?.question;
    if (!question || loading) return;
    setRegenMenuOpen(false);
    const useType = override?.providerType || providerType;
    const useModel = override?.model || model;
    if (override) {
      setProviderType(useType);
      setModel(useModel);
      const p = providers.find((x) => x.type === useType);
      if (p) setBaseUrl(p.editable_base_url ? p.base_url || "" : "");
    }
    updateLastAi((msg) => ({
      ...msg,
      content: "",
      streaming: true,
      error: false,
      elapsed_ms: undefined,
      usage: undefined,
      feedback: undefined,
      toolSteps: undefined,
      provider: useType,
      model: useModel,
      timestamp: new Date().toLocaleTimeString(),
    }));
    runStream(question, { regenerate: true, override });
  };

  // Stop an in-flight generation (aborts the SSE fetch).
  const handleStop = () => {
    if (abortRef.current) {
      abortRef.current();
      abortRef.current = null;
    }
    updateLastAi((msg) => ({ ...msg, streaming: false }));
    setLoading(false);
  };

  // Copy an answer to the clipboard.
  const handleCopy = async (text, idx) => {
    try {
      await navigator.clipboard.writeText(text || "");
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx((c) => (c === idx ? null : c)), 1500);
    } catch (e) {
      /* clipboard unavailable */
    }
  };

  // Backend stores only user/assistant messages; map a UI index to that array.
  const backendIndexFor = (uiIndex) =>
    messages.slice(0, uiIndex + 1).filter((m) => m.type === "user" || m.type === "ai").length - 1;

  const handleFeedback = async (uiIndex, rating) => {
    if (!conversationId) return;
    const current = messages[uiIndex]?.feedback;
    const next = current === rating ? null : rating; // toggle off if same
    // optimistic UI
    setMessages((prev) => {
      const copy = [...prev];
      copy[uiIndex] = { ...copy[uiIndex], feedback: next };
      return copy;
    });
    try {
      await astrologyService.submitFeedback(conversationId, backendIndexFor(uiIndex), next);
    } catch (e) {
      /* non-fatal; leave optimistic state */
    }
  };

  const conversationName = () =>
    selectedProfile?.birth_details?.name || selectedProfile?.profile_name || "chart";

  // Export the current conversation as a Markdown file.
  const handleExport = () => {
    setExportMenuOpen(false);
    const name = conversationName();
    const lines = [
      `# AI Astrologer — ${name}`,
      "",
      `_Exported ${new Date().toLocaleString()}_`,
      "",
      "> Astrological guidance for reflection only — not medical, financial, or legal advice.",
      "",
    ];
    messages.forEach((m) => {
      if (m.type === "user") {
        lines.push(`## ❓ ${m.content}`, "");
      } else if (m.type === "ai" && m.content) {
        const tag = m.model ? ` _(${m.model})_` : "";
        lines.push(`### 🔮 Astrologer${tag}`, "", m.content, "");
      }
    });
    const blob = new Blob([lines.join("\n")], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `astrologer-${name.replace(/\s+/g, "-").toLowerCase()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Export the current conversation as a PDF.
  const handleExportPdf = async () => {
    setExportMenuOpen(false);
    const totalTokens = messages.reduce(
      (sum, m) => sum + (m.type === "ai" && m.usage?.total_tokens ? m.usage.total_tokens : 0),
      0
    );
    try {
      await exportConversationPdf(messages, conversationName(), { totalTokens });
    } catch (e) {
      setError(t("ask.errPdf"));
    }
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
      const raw = conv.messages || [];
      const msgs = raw.map((m, i) =>
        m.role === "user"
          ? { type: "user", content: m.content }
          : {
              type: "ai",
              content: m.content,
              provider: m.provider,
              model: m.model,
              mode: conv.mode,
              vargas: m.vargas,
              sections: m.sections,
              elapsed_ms: m.elapsed_ms,
              usage: m.usage,
              feedback: m.feedback,
              // rebuild the tool-call steps from the persisted trace
              toolSteps: (m.tool_trace || []).map((tc) => ({
                name: tc.name,
                args: tc.args,
                ok: tc.ok ?? true,
                result: tc.result,
              })),
              // remember the prompt behind this answer (for Regenerate)
              question: raw[i - 1]?.role === "user" ? raw[i - 1].content : undefined,
            }
      );
      setMessages(msgs.length ? msgs : [{ type: "system", content: t("ask.emptyConversation") }]);
      setConversationId(id);
      if (conv.mode) setMode(conv.mode);
      setShowHistory(false);
    } catch (e) {
      setError(t("ask.errLoadConv"));
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

  // ── Per-user API keys (8.6) ─────────────────────────────────────────
  const refreshKeyStatus = async () => {
    try {
      const resp = await astrologyService.getApiKeys();
      setKeyStatus(resp.data.keys || {});
    } catch (e) {
      /* non-fatal */
    }
  };

  const refreshProviders = async () => {
    try {
      const resp = await astrologyService.getLlmProviders();
      setProviders(resp.data.providers || []);
    } catch (e) {
      /* non-fatal */
    }
  };

  const openKeysModal = () => {
    setKeyInputs({});
    refreshKeyStatus();
    setShowKeysModal(true);
  };

  const handleSaveKey = async (provider) => {
    const value = (keyInputs[provider] || "").trim();
    if (!value) return;
    setKeySaving(provider);
    try {
      await astrologyService.setApiKey(provider, value);
      setKeyInputs((prev) => ({ ...prev, [provider]: "" }));
      await refreshKeyStatus();
      await refreshProviders(); // availability may have flipped to "ready"
    } catch (e) {
      setError(e.response?.data?.detail || t("ask.errSaveKey"));
    } finally {
      setKeySaving("");
    }
  };

  const handleClearKey = async (provider) => {
    setKeySaving(provider);
    try {
      await astrologyService.deleteApiKey(provider);
      await refreshKeyStatus();
      await refreshProviders();
    } catch (e) {
      /* non-fatal */
    } finally {
      setKeySaving("");
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
      dasha_sequence: chartData.dashas?.dasha_sequence || [],
    };
  };

  if (!selectedProfile) {
    return null;
  }

  // Index of the most recent AI message (only it can be regenerated).
  const lastAiIndex = messages.reduce((acc, m, i) => (m.type === "ai" ? i : acc), -1);

  // Flat list of pickable models across available providers (for "Regenerate
  // with a different model").
  const modelOptions = providers
    .filter((p) => p.available)
    .flatMap((p) => {
      const ms = p.models && p.models.length ? p.models : p.default_model ? [p.default_model] : [];
      return ms.map((m) => ({
        providerType: p.type,
        model: m,
        providerLabel: p.label,
      }));
    });

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<MessageCircle size={24} />}
        title={t("ask.title")}
        subtitle={t("ask.subtitle")}
        accent="terracotta"
      />

      {/* Content */}
      <div className="dashboard-content">
        <ProfileBanner
          profile={selectedProfile}
          actions={
            <div style={{ display: "flex", gap: "var(--space-sm)", flexWrap: "wrap" }}>
              <button onClick={startNewConversation} className="change-profile-btn">
                <Plus size={16} />
                <span>{t("ask.newChat")}</span>
              </button>
              <button
                onClick={() => {
                  setShowHistory((v) => !v);
                  refreshConversations();
                }}
                className="change-profile-btn"
              >
                <History size={16} />
                <span>
                  {t("ask.history")}
                  {conversations.length ? ` (${conversations.length})` : ""}
                </span>
              </button>
              <button
                ref={exportBtnRef}
                onClick={() => setExportMenuOpen((v) => !v)}
                className="change-profile-btn"
                disabled={!messages.some((m) => m.type === "ai" && m.content)}
                title={t("ask.exportTitle")}
              >
                <Download size={16} />
                <span>{t("ask.export")}</span>
                <ChevronDown size={14} />
              </button>
              <PortalMenu
                anchorRef={exportBtnRef}
                open={exportMenuOpen}
                onClose={() => setExportMenuOpen(false)}
                align="left"
                width={200}
              >
                <button className="export-menu-item" onClick={handleExport}>
                  <FileText size={15} />
                  <span>{t("ask.markdown")}</span>
                </button>
                <button className="export-menu-item" onClick={handleExportPdf}>
                  <FileType size={15} />
                  <span>{t("ask.pdf")}</span>
                </button>
              </PortalMenu>
              <button
                onClick={openKeysModal}
                className="change-profile-btn"
                title={t("ask.apiKeysTitle")}
              >
                <KeyRound size={16} />
                <span>{t("ask.apiKeys")}</span>
              </button>
              <button onClick={() => navigate("/profile-selection")} className="change-profile-btn">
                <Star size={16} />
                <span>{t("common.changeChart")}</span>
              </button>
            </div>
          }
        />

        {/* History panel */}
        {showHistory && (
          <div
            style={{
              background: "white",
              borderRadius: "var(--radius-xl)",
              padding: "var(--space-xl)",
              boxShadow: "var(--shadow-lg)",
              borderTop: "4px solid var(--saffron)",
              marginBottom: "var(--space-xl)",
            }}
          >
            <h3
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-sm)",
                marginBottom: "var(--space-lg)",
                color: "var(--cosmic-indigo)",
                fontSize: "1.25rem",
                fontWeight: 700,
              }}
            >
              <History size={20} style={{ color: "var(--saffron)" }} />
              {t("ask.savedConversations")}
            </h3>
            {conversations.length === 0 ? (
              <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", margin: 0 }}>
                {t("ask.noConversations")}
              </p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
                {conversations.map((c) => (
                  <div
                    key={c.id}
                    onClick={() => loadConversation(c.id)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: "var(--space-md)",
                      padding: "var(--space-md)",
                      borderRadius: "var(--radius-md)",
                      cursor: "pointer",
                      border: `1px solid ${c.id === conversationId ? "var(--saffron)" : "var(--sandalwood)"}`,
                      background: c.id === conversationId ? "rgba(255, 153, 51, 0.08)" : "white",
                    }}
                  >
                    <div style={{ minWidth: 0 }}>
                      <div
                        style={{
                          fontWeight: 600,
                          color: "var(--cosmic-indigo)",
                          fontSize: "0.9375rem",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {c.title}
                      </div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                        {Math.floor((c.message_count || 0) / 2)} {t("ask.qa")}
                        {c.last_model ? ` · ${c.last_model}` : ""}
                        {c.updated_at ? ` · ${formatDate(c.updated_at)}` : ""}
                      </div>
                    </div>
                    <button
                      onClick={(e) => handleDeleteConversation(c.id, e)}
                      title={t("ask.deleteConversation")}
                      style={{
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                        color: "var(--text-secondary)",
                        padding: "var(--space-xs)",
                        display: "flex",
                        flexShrink: 0,
                      }}
                      onMouseOver={(e) => (e.currentTarget.style.color = "var(--vermillion)")}
                      onMouseOut={(e) => (e.currentTarget.style.color = "var(--text-secondary)")}
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
          <div style={{ opacity: 0, animation: "fadeIn 0.6s ease-out 0.2s forwards" }}>
            <NorthIndianChart chartData={chartData} />
          </div>
        )}

        {/* AI Model Selector and Examples */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
            gap: "var(--space-lg)",
            marginBottom: "var(--space-xl)",
            opacity: 0,
            animation: "fadeIn 0.6s ease-out 0.4s forwards",
          }}
        >
          {/* LLM Selector Card */}
          <div
            style={{
              background: "white",
              borderRadius: "var(--radius-xl)",
              padding: "var(--space-xl)",
              boxShadow: "var(--shadow-lg)",
              borderTop: "4px solid var(--saffron)",
            }}
          >
            <h3
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-sm)",
                marginBottom: "var(--space-lg)",
                color: "var(--cosmic-indigo)",
                fontSize: "1.25rem",
                fontWeight: 700,
              }}
            >
              <Bot size={20} style={{ color: "var(--saffron)" }} />
              {t("ask.aiModel")}
              <button
                onClick={() => openInfo(lastContext)}
                style={{
                  marginLeft: "auto",
                  background: "rgba(255, 153, 51, 0.1)",
                  border: "1px solid var(--saffron)",
                  cursor: "pointer",
                  color: "var(--saffron)",
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-xs)",
                  padding: "var(--space-xs) var(--space-sm)",
                  borderRadius: "var(--radius-sm)",
                  transition: "all 0.3s ease",
                }}
                onMouseOver={(e) => (e.currentTarget.style.background = "rgba(255, 153, 51, 0.2)")}
                onMouseOut={(e) => (e.currentTarget.style.background = "rgba(255, 153, 51, 0.1)")}
                title={t("ask.viewDataTitle")}
              >
                <Info size={18} />
                <span style={{ fontSize: "0.75rem", fontWeight: 600 }}>
                  {t("ask.viewDataSent")}
                </span>
              </button>
            </h3>
            {providersLoading ? (
              <div style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
                {t("ask.detectingModels")}
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
                {/* Provider */}
                <label style={{ display: "block" }}>
                  <span
                    style={{
                      fontSize: "0.8125rem",
                      fontWeight: 600,
                      color: "var(--text-secondary)",
                    }}
                  >
                    {t("ask.provider")}
                  </span>
                  <select
                    value={providerType}
                    onChange={(e) => handleProviderChange(e.target.value)}
                    style={selectStyle}
                  >
                    {providers.map((p) => (
                      <option key={p.type} value={p.type}>
                        {PROVIDER_ICONS[p.type] || "•"} {p.label}
                        {p.available ? "" : ` — ${t("ask.unavailable")}`}
                      </option>
                    ))}
                  </select>
                </label>

                {/* Model */}
                <label style={{ display: "block" }}>
                  <span
                    style={{
                      fontSize: "0.8125rem",
                      fontWeight: 600,
                      color: "var(--text-secondary)",
                    }}
                  >
                    {t("ask.model")}
                  </span>
                  {selectedProvider && selectedProvider.models.length > 0 ? (
                    <select
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      style={selectStyle}
                    >
                      {!selectedProvider.models.includes(model) && model && (
                        <option value={model}>
                          {model} ({t("ask.custom")})
                        </option>
                      )}
                      {selectedProvider.models.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      placeholder={t("ask.enterModel")}
                      style={selectStyle}
                    />
                  )}
                </label>

                {/* Availability note */}
                {selectedProvider && !selectedProvider.available && (
                  <div
                    style={{
                      fontSize: "0.8125rem",
                      color: "var(--vermillion)",
                      background: "rgba(229, 57, 53, 0.08)",
                      border: "1px solid rgba(229, 57, 53, 0.25)",
                      borderRadius: "var(--radius-md)",
                      padding: "var(--space-sm) var(--space-md)",
                    }}
                  >
                    ⚠ {selectedProvider.reason || t("ask.providerUnreachable")}
                  </div>
                )}

                {/* Advanced: editable base URL for local providers */}
                {selectedProvider && selectedProvider.editable_base_url && (
                  <div>
                    <button
                      type="button"
                      onClick={() => setShowAdvanced((v) => !v)}
                      style={{
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                        color: "var(--saffron)",
                        fontSize: "0.8125rem",
                        fontWeight: 600,
                        padding: 0,
                      }}
                    >
                      {showAdvanced ? "▾" : "▸"} {t("ask.advancedEndpoint")}
                    </button>
                    {showAdvanced && (
                      <input
                        type="text"
                        value={baseUrl}
                        onChange={(e) => setBaseUrl(e.target.value)}
                        placeholder={selectedProvider.base_url}
                        style={{ ...selectStyle, marginTop: "var(--space-sm)" }}
                      />
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Examples Card */}
          <div
            style={{
              background: "white",
              borderRadius: "var(--radius-xl)",
              padding: "var(--space-xl)",
              boxShadow: "var(--shadow-lg)",
              borderTop: "4px solid var(--saffron)",
            }}
          >
            <h3
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-sm)",
                marginBottom: "var(--space-lg)",
                color: "var(--cosmic-indigo)",
                fontSize: "1.25rem",
                fontWeight: 700,
              }}
            >
              <MessageCircle size={20} style={{ color: "var(--saffron)" }} />
              {t("ask.exampleTitle")}
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

          {/* Answer Mode Card */}
          <div
            style={{
              background: "white",
              borderRadius: "var(--radius-xl)",
              padding: "var(--space-xl)",
              boxShadow: "var(--shadow-lg)",
              borderTop: "4px solid var(--saffron)",
            }}
          >
            <h3
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-sm)",
                marginBottom: "var(--space-xs)",
                color: "var(--cosmic-indigo)",
                fontSize: "1.25rem",
                fontWeight: 700,
              }}
            >
              <Wrench size={20} style={{ color: "var(--saffron)" }} />
              Answer mode
            </h3>
            <p
              style={{
                margin: "0 0 var(--space-md)",
                fontSize: "0.8125rem",
                color: "var(--text-secondary)",
              }}
            >
              {modeLocked
                ? "This conversation's mode is fixed. Start a new conversation to switch."
                : "Full context sends the whole chart up front. Smart lookup sends a starting summary (the charts selected below) and lets the AI pull in extra details by itself as it answers."}
            </p>
            <div style={{ display: "flex", gap: "var(--space-sm)" }}>
              {[
                { val: "pass_all", label: "Full context" },
                { val: "tools", label: "Smart lookup" },
              ].map((o) => {
                const active = mode === o.val;
                return (
                  <button
                    key={o.val}
                    type="button"
                    onClick={() => !modeLocked && setMode(o.val)}
                    disabled={modeLocked}
                    style={{
                      cursor: modeLocked ? "not-allowed" : "pointer",
                      padding: "var(--space-xs) var(--space-md)",
                      borderRadius: "var(--radius-md)",
                      fontSize: "0.8125rem",
                      fontWeight: 600,
                      border: `1px solid ${active ? "var(--saffron)" : "var(--sandalwood)"}`,
                      background: active ? "rgba(255, 153, 51, 0.12)" : "white",
                      color: active ? "var(--vermillion)" : "var(--text-secondary)",
                      opacity: modeLocked && !active ? 0.5 : 1,
                    }}
                  >
                    {o.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Divisional Charts (Vargas) Card */}
          <div
            style={{
              background: "white",
              borderRadius: "var(--radius-xl)",
              padding: "var(--space-xl)",
              boxShadow: "var(--shadow-lg)",
              borderTop: "4px solid var(--saffron)",
            }}
          >
            <h3
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-sm)",
                marginBottom: "var(--space-xs)",
                color: "var(--cosmic-indigo)",
                fontSize: "1.25rem",
                fontWeight: 700,
              }}
            >
              <Star size={20} style={{ color: "var(--saffron)" }} />
              {t("ask.chartsToConsult")}
            </h3>
            <p
              style={{
                margin: "0 0 var(--space-md)",
                fontSize: "0.8125rem",
                color: "var(--text-secondary)",
              }}
            >
              {t("ask.chartsHint")}
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-sm)" }}>
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
                      cursor: isD1 ? "default" : "pointer",
                      padding: "var(--space-xs) var(--space-md)",
                      borderRadius: "var(--radius-md)",
                      fontSize: "0.8125rem",
                      fontWeight: 600,
                      border: `1px solid ${active ? "var(--saffron)" : "var(--sandalwood)"}`,
                      background: active ? "rgba(255, 153, 51, 0.12)" : "white",
                      color: active ? "var(--vermillion)" : "var(--text-secondary)",
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

        {/* Error banner */}
        {error && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "var(--space-md)",
              marginBottom: "var(--space-lg)",
              padding: "var(--space-md) var(--space-lg)",
              background: "rgba(229, 57, 53, 0.08)",
              border: "1px solid rgba(229, 57, 53, 0.3)",
              borderRadius: "var(--radius-md)",
              color: "var(--vermillion)",
              fontSize: "0.875rem",
            }}
          >
            <span>⚠ {error}</span>
            <button
              onClick={() => setError("")}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                color: "var(--vermillion)",
                display: "flex",
              }}
              title={t("ask.dismiss")}
            >
              <X size={16} />
            </button>
          </div>
        )}

        {/* Chat Area */}
        <div
          style={{
            background: "white",
            borderRadius: "var(--radius-xl)",
            boxShadow: "var(--shadow-lg)",
            borderTop: "4px solid var(--saffron)",
            display: "flex",
            flexDirection: "column",
            minHeight: "500px",
            maxHeight: "700px",
            opacity: 0,
            animation: "fadeIn 0.6s ease-out 0.6s forwards",
          }}
        >
          <div
            className="messages-container"
            style={{
              flex: 1,
              overflowY: "auto",
              padding: "var(--space-xl)",
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-lg)",
              background: "var(--sacred-white)",
            }}
          >
            {messages.map((message, index) => (
              <div key={index} className={`message ${message.type}`}>
                {message.type === "user" && (
                  <div className="message-header">
                    <User size={18} />
                    <span>{t("ask.you")}</span>
                    <span className="timestamp">{message.timestamp}</span>
                  </div>
                )}
                {message.type === "ai" && (
                  <div className="message-header">
                    <Bot size={18} />
                    <span>
                      {t("ask.aiAstrologer")}
                      {message.model
                        ? ` · ${message.model}`
                        : message.provider
                          ? ` (${message.provider})`
                          : ""}
                    </span>
                    {message.timestamp && <span className="timestamp">{message.timestamp}</span>}
                    {!message.streaming && message.elapsed_ms != null && (
                      <span className="timestamp" title={t("ask.generationTime")}>
                        {(message.elapsed_ms / 1000).toFixed(1)}s
                      </span>
                    )}
                    {!message.streaming &&
                      (() => {
                        const u = usageLabel(message.usage);
                        return u ? (
                          <span className="timestamp" title={u.title}>
                            {u.short}
                          </span>
                        ) : null;
                      })()}
                    {!message.streaming && (message.context || message.model) && (
                      <button
                        onClick={() => openInfo(messageInfo(message))}
                        title={t("ask.chartDataForAnswer")}
                        style={{
                          marginLeft: "auto",
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                          color: "var(--saffron)",
                          display: "flex",
                          alignItems: "center",
                          padding: "2px",
                          borderRadius: "var(--radius-sm)",
                        }}
                      >
                        <Info size={15} />
                      </button>
                    )}
                  </div>
                )}
                {message.type === "system" && (
                  <div className="message-header">
                    <Sparkles size={18} />
                    <span>{t("ask.system")}</span>
                  </div>
                )}
                {message.type === "ai" &&
                  message.toolSteps &&
                  message.toolSteps.length > 0 &&
                  (() => {
                    const realSteps = message.toolSteps.filter((s) => !s.notice);
                    return (
                      <div style={{ margin: "0 0 var(--space-sm)" }}>
                        {/* Pills timeline of the tool calls, in order */}
                        <div
                          style={{
                            display: "flex",
                            flexWrap: "wrap",
                            gap: "6px",
                            alignItems: "center",
                          }}
                        >
                          {message.toolSteps.map((s, si) =>
                            s.notice ? (
                              <span
                                key={si}
                                style={{
                                  fontSize: "12px",
                                  fontStyle: "italic",
                                  color: "var(--ink-light, #888)",
                                  alignSelf: "center",
                                }}
                              >
                                {s.notice}
                              </span>
                            ) : (
                              <span
                                key={si}
                                title={s.args ? JSON.stringify(s.args) : ""}
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "4px",
                                  fontSize: "12px",
                                  padding: "2px 8px",
                                  borderRadius: "999px",
                                  border: "1px solid var(--saffron, #e08a2c)",
                                  color:
                                    s.ok === false ? "#c0392b" : "var(--saffron, #e08a2c)",
                                  background: "rgba(224,138,44,0.06)",
                                }}
                              >
                                {s.ok === null ? (
                                  <Wrench size={12} />
                                ) : s.ok ? (
                                  <Check size={12} />
                                ) : (
                                  <X size={12} />
                                )}
                                {fmtTool(s.name)}
                                {s.args && Object.keys(s.args).length
                                  ? ` (${Object.values(s.args).join(", ")})`
                                  : ""}
                              </span>
                            )
                          )}
                          {realSteps.length > 0 && (
                            <button
                              type="button"
                              onClick={() =>
                                setOpenTrace((p) => ({ ...p, [index]: !p[index] }))
                              }
                              style={{
                                background: "none",
                                border: "none",
                                cursor: "pointer",
                                color: "var(--saffron, #e08a2c)",
                                fontSize: "12px",
                                fontWeight: 600,
                                padding: "2px 4px",
                              }}
                            >
                              {openTrace[index] ? "▾" : "▸"} Behind the scenes
                            </button>
                          )}
                        </div>

                        {/* Expanded: each tool call + the data it returned */}
                        {openTrace[index] && realSteps.length > 0 && (
                          <div
                            style={{
                              marginTop: "var(--space-sm)",
                              border: "1px solid var(--sandalwood, #e7d9c5)",
                              borderRadius: "var(--radius-md)",
                              padding: "var(--space-sm) var(--space-md)",
                              background: "var(--sacred-white, #fdfaf5)",
                            }}
                          >
                            <div
                              style={{
                                fontSize: "11px",
                                color: "var(--text-secondary)",
                                marginBottom: "6px",
                              }}
                            >
                              The AI fetched this data step by step, then reasoned over it
                              to write the answer above.
                            </div>
                            {realSteps.map((s, si) => (
                              <div
                                key={si}
                                style={{
                                  marginBottom:
                                    si < realSteps.length - 1 ? "var(--space-sm)" : 0,
                                }}
                              >
                                <div
                                  style={{
                                    fontSize: "12px",
                                    fontWeight: 600,
                                    color: "var(--cosmic-indigo)",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "4px",
                                  }}
                                >
                                  <span style={{ opacity: 0.6 }}>{si + 1}.</span>
                                  {s.ok === false ? (
                                    <X size={12} color="#c0392b" />
                                  ) : (
                                    <Check size={12} color="var(--saffron, #e08a2c)" />
                                  )}
                                  {fmtTool(s.name)}
                                  {s.args && Object.keys(s.args).length ? (
                                    <span
                                      style={{ fontWeight: 400, color: "var(--text-secondary)" }}
                                    >
                                      ({Object.entries(s.args)
                                        .map(([k, v]) => `${k}: ${v}`)
                                        .join(", ")})
                                    </span>
                                  ) : null}
                                </div>
                                {s.result !== undefined && (
                                  <pre
                                    style={{
                                      margin: "4px 0 0",
                                      fontSize: "11px",
                                      lineHeight: 1.4,
                                      maxHeight: "220px",
                                      overflow: "auto",
                                      background: "white",
                                      border: "1px solid var(--sandalwood, #e7d9c5)",
                                      borderRadius: "var(--radius-sm)",
                                      padding: "6px 8px",
                                      whiteSpace: "pre-wrap",
                                      wordBreak: "break-word",
                                    }}
                                  >
                                    {JSON.stringify(s.result, null, 2)}
                                  </pre>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })()}
                <div className="message-content">
                  {message.type === "ai" ? (
                    message.streaming && !message.content ? (
                      <div className="loading">
                        <div className="typing-indicator">
                          <span></span>
                          <span></span>
                          <span></span>
                        </div>
                        {t("ask.consulting")}
                      </div>
                    ) : (
                      <>
                        <ReactMarkdown>{message.content}</ReactMarkdown>
                        {message.streaming && <span className="stream-cursor">▍</span>}
                      </>
                    )
                  ) : (
                    message.content
                  )}
                </div>

                {/* Answer affordances: copy / regenerate / feedback */}
                {message.type === "ai" &&
                  !message.streaming &&
                  message.content &&
                  !message.error && (
                    <div className="msg-actions">
                      <button
                        className="msg-action-btn"
                        onClick={() => handleCopy(message.content, index)}
                        title={t("ask.copyTitle")}
                      >
                        {copiedIdx === index ? <Check size={13} /> : <Copy size={13} />}
                        {copiedIdx === index ? t("ask.copied") : t("ask.copy")}
                      </button>
                      {index === lastAiIndex && message.question && (
                        <div className="regen-group">
                          <button
                            className="msg-action-btn regen-main"
                            onClick={() => handleRegenerate(message)}
                            disabled={loading}
                            title={t("ask.regenCurrentTitle")}
                          >
                            <RefreshCw size={13} />
                            {t("ask.regenerate")}
                          </button>
                          <button
                            ref={regenBtnRef}
                            className="msg-action-btn regen-caret"
                            onClick={() => setRegenMenuOpen((v) => !v)}
                            disabled={loading || modelOptions.length === 0}
                            title={t("ask.regenDifferentTitle")}
                            aria-label={t("ask.regenDifferentTitle")}
                          >
                            <ChevronDown size={13} />
                          </button>
                          <PortalMenu
                            anchorRef={regenBtnRef}
                            open={regenMenuOpen}
                            onClose={() => setRegenMenuOpen(false)}
                            align="left"
                            width={220}
                          >
                            <div className="regen-menu-label">{t("ask.regenWith")}</div>
                            {modelOptions.map((opt) => {
                              const isCurrent =
                                opt.providerType === providerType && opt.model === model;
                              return (
                                <button
                                  key={`${opt.providerType}:${opt.model}`}
                                  className="regen-menu-item"
                                  onClick={() => handleRegenerate(message, opt)}
                                >
                                  <span className="regen-menu-model">
                                    {opt.model}
                                    {isCurrent ? " ✓" : ""}
                                  </span>
                                  <span className="regen-menu-provider">{opt.providerLabel}</span>
                                </button>
                              );
                            })}
                          </PortalMenu>
                        </div>
                      )}
                      {conversationId && (
                        <>
                          <button
                            className={`msg-action-btn${message.feedback === "up" ? " active-up" : ""}`}
                            onClick={() => handleFeedback(index, "up")}
                            title={t("ask.helpful")}
                          >
                            <ThumbsUp size={13} />
                          </button>
                          <button
                            className={`msg-action-btn${message.feedback === "down" ? " active-down" : ""}`}
                            onClick={() => handleFeedback(index, "down")}
                            title={t("ask.notHelpful")}
                          >
                            <ThumbsDown size={13} />
                          </button>
                        </>
                      )}
                    </div>
                  )}
              </div>
            ))}
          </div>

          <div
            className="chat-input-container"
            style={{
              display: "flex",
              gap: "var(--space-sm)",
              padding: "var(--space-lg)",
              borderTop: "2px solid var(--sandalwood)",
              background: "white",
            }}
          >
            <input
              type="text"
              className="chat-input"
              placeholder={t("ask.inputPlaceholder")}
              value={currentQuestion}
              onChange={(e) => setCurrentQuestion(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === "Enter" && !loading) {
                  handleAskQuestion(currentQuestion);
                }
              }}
              disabled={loading}
            />
            {loading ? (
              <button className="btn-stop" onClick={handleStop} title={t("ask.stopTitle")}>
                <Square size={16} fill="currentColor" />
                <span>{t("ask.stop")}</span>
              </button>
            ) : (
              <button
                className="btn-send"
                onClick={() => handleAskQuestion(currentQuestion)}
                disabled={!currentQuestion.trim()}
              >
                <Send size={20} />
              </button>
            )}
          </div>

          {/* Safety / disclaimer footer */}
          <div className="ai-disclaimer">⚠ {t("ask.disclaimer")}</div>
        </div>

        {/* Info Modal */}
        {showInfoModal && (
          <div
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: "rgba(0, 0, 0, 0.5)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 1000,
              padding: "var(--space-lg)",
              animation: "fadeIn 0.3s ease-out",
            }}
            onClick={() => setShowInfoModal(false)}
          >
            <div
              style={{
                background: "white",
                borderRadius: "var(--radius-xl)",
                maxWidth: "800px",
                width: "100%",
                maxHeight: "80vh",
                overflow: "auto",
                boxShadow: "0 20px 60px rgba(0, 0, 0, 0.3)",
                animation: "slideIn 0.3s ease-out",
              }}
              onClick={(e) => e.stopPropagation()}
            >
              {/* Modal Header */}
              <div
                style={{
                  padding: "var(--space-xl)",
                  borderBottom: "2px solid var(--sandalwood)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  position: "sticky",
                  top: 0,
                  background: "white",
                  zIndex: 1,
                }}
              >
                <h3
                  style={{
                    margin: 0,
                    fontSize: "1.5rem",
                    color: "var(--cosmic-indigo)",
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-sm)",
                  }}
                >
                  <Info size={24} style={{ color: "var(--saffron)" }} />
                  {t("ask.chartDataSentToAI")}
                </h3>
                <button
                  onClick={() => setShowInfoModal(false)}
                  style={{
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    color: "var(--text-secondary)",
                    padding: "var(--space-sm)",
                    borderRadius: "var(--radius-md)",
                    transition: "all 0.3s ease",
                  }}
                  onMouseOver={(e) => {
                    e.currentTarget.style.background = "var(--sandalwood)";
                    e.currentTarget.style.color = "var(--vermillion)";
                  }}
                  onMouseOut={(e) => {
                    e.currentTarget.style.background = "none";
                    e.currentTarget.style.color = "var(--text-secondary)";
                  }}
                >
                  <X size={24} />
                </button>
              </div>

              {/* Modal Content */}
              <div
                style={{
                  padding: "var(--space-xl)",
                  fontSize: "0.875rem",
                  lineHeight: "1.6",
                }}
              >
                <div
                  style={{
                    background:
                      "linear-gradient(135deg, rgba(255, 153, 51, 0.05) 0%, rgba(255, 153, 51, 0.1) 100%)",
                    padding: "var(--space-lg)",
                    borderRadius: "var(--radius-lg)",
                    marginBottom: "var(--space-lg)",
                    border: "1px solid var(--saffron)",
                  }}
                >
                  <p style={{ margin: 0, color: "var(--cosmic-indigo)", fontWeight: 500 }}>
                    {modalData ? t("ask.modalIntroWithData") : t("ask.modalIntroNoData")}
                  </p>
                </div>

                <pre
                  style={{
                    background: "var(--sacred-white)",
                    padding: "var(--space-lg)",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--sandalwood)",
                    overflow: "auto",
                    fontFamily: "monospace",
                    fontSize: "0.8125rem",
                    lineHeight: "1.8",
                    color: "var(--cosmic-indigo)",
                  }}
                >
                  {JSON.stringify(modalData || getChartDataForLLM(), null, 2)}
                </pre>

                <div
                  style={{
                    marginTop: "var(--space-lg)",
                    padding: "var(--space-md)",
                    background: "rgba(52, 73, 94, 0.05)",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--cosmic-indigo)",
                    fontSize: "0.8125rem",
                  }}
                >
                  <p
                    style={{
                      margin: "0 0 var(--space-sm) 0",
                      color: "var(--cosmic-indigo)",
                      fontWeight: 600,
                    }}
                  >
                    📝 {t("ask.note")}
                  </p>
                  <p style={{ margin: 0, color: "var(--text-secondary)" }}>{t("ask.noteBody")}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* API Keys Modal (8.6 — per-user, encrypted server-side) */}
        {showKeysModal && (
          <div
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: "rgba(0, 0, 0, 0.5)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 1000,
              padding: "var(--space-lg)",
              animation: "fadeIn 0.3s ease-out",
            }}
            onClick={() => setShowKeysModal(false)}
          >
            <div
              style={{
                background: "white",
                borderRadius: "var(--radius-xl)",
                maxWidth: "560px",
                width: "100%",
                maxHeight: "85vh",
                overflow: "auto",
                boxShadow: "0 20px 60px rgba(0, 0, 0, 0.3)",
                animation: "slideIn 0.3s ease-out",
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div
                style={{
                  padding: "var(--space-xl)",
                  borderBottom: "2px solid var(--sandalwood)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <h3
                  style={{
                    margin: 0,
                    fontSize: "1.5rem",
                    color: "var(--cosmic-indigo)",
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-sm)",
                  }}
                >
                  <KeyRound size={24} style={{ color: "var(--saffron)" }} />
                  {t("ask.yourApiKeys")}
                </h3>
                <button
                  onClick={() => setShowKeysModal(false)}
                  style={{
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    color: "var(--text-secondary)",
                    padding: "var(--space-sm)",
                    borderRadius: "var(--radius-md)",
                    display: "flex",
                  }}
                >
                  <X size={24} />
                </button>
              </div>

              <div style={{ padding: "var(--space-xl)" }}>
                <p
                  style={{
                    margin: "0 0 var(--space-lg)",
                    fontSize: "0.8125rem",
                    color: "var(--text-secondary)",
                    lineHeight: 1.6,
                  }}
                >
                  {t("ask.keysIntro")}
                </p>

                {KEY_PROVIDERS.map((p) => {
                  const status = keyStatus[p.id] || {};
                  const busy = keySaving === p.id;
                  return (
                    <div key={p.id} className="key-row">
                      <div className="key-row-head">
                        <span
                          style={{
                            fontWeight: 700,
                            color: "var(--cosmic-indigo)",
                            fontSize: "0.9375rem",
                          }}
                        >
                          {p.label}
                        </span>
                        <span className={`key-pill ${status.has_key ? "set" : "unset"}`}>
                          {status.has_key
                            ? t("ask.savedKey", { masked: status.masked || "" })
                            : t("ask.notSet")}
                        </span>
                      </div>
                      <div className="key-row-controls">
                        <input
                          type="password"
                          className="key-input"
                          placeholder={status.has_key ? t("ask.enterNewKey") : t("ask.pasteKey")}
                          value={keyInputs[p.id] || ""}
                          onChange={(e) =>
                            setKeyInputs((prev) => ({ ...prev, [p.id]: e.target.value }))
                          }
                          autoComplete="off"
                        />
                        <button
                          className="msg-action-btn"
                          style={{ padding: "0 var(--space-md)" }}
                          onClick={() => handleSaveKey(p.id)}
                          disabled={busy || !(keyInputs[p.id] || "").trim()}
                        >
                          {busy ? "…" : t("ask.save")}
                        </button>
                        {status.has_key && (
                          <button
                            className="msg-action-btn"
                            style={{ padding: "0 var(--space-md)" }}
                            onClick={() => handleClearKey(p.id)}
                            disabled={busy}
                            title={t("ask.removeKey")}
                          >
                            <Trash2 size={13} />
                          </button>
                        )}
                      </div>
                      <span style={{ fontSize: "0.6875rem", color: "var(--text-secondary)" }}>
                        {p.hint}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
