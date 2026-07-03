import React, { useState, useEffect, useLayoutEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  MessageCircle,
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
  Download,
  KeyRound,
  ChevronDown,
  FileText,
  FileType,
  Wrench,
} from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { formatDate } from "../utils/format";
import { VARGAS, VARGA_SUGGESTIONS } from "../constants/jyotish";
import { astrologyService, streamAskQuestion } from "../services/api";
import { exportConversationPdf } from "../utils/exportConversation";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { ChatComposer } from "../components/chat/ChatComposer";
import { StreamingMarkdown } from "../components/chat/StreamingMarkdown";
import "../styles/Dashboard.css";
import "../styles/Shared.css";
import "../styles/Chat.css";

// Toggleable context sections (must mirror the backend's DEFAULT_SECTIONS). In
// "Full context" mode each is On (seeded) or Off; in "Smart lookup" mode each is
// tri-state: Seed (pre-sent), Tool (the AI fetches it on demand) or Off.
const CONTEXT_SECTIONS = [
  { key: "dasha_tree", labelKey: "ask.sectionDashaTree" },
  { key: "yogas", labelKey: "ask.sectionYogas" },
  { key: "doshas", labelKey: "ask.sectionDoshas" },
  { key: "transits", labelKey: "ask.sectionTransits" },
  { key: "aspects", labelKey: "ask.sectionAspects" },
  { key: "arudhas", labelKey: "ask.sectionArudhas" },
  { key: "ashtakavarga", labelKey: "ask.sectionAshtakavarga" },
  { key: "shadbala", labelKey: "ask.sectionShadbala" },
];

// Default tri-state for Smart-lookup mode: seed the natal base + dasha chain,
// let the AI fetch everything else on demand. Full-context mode seeds all.
const DEFAULT_SECTION_STATE = {
  dasha_tree: "seed", yogas: "tool", doshas: "tool", transits: "tool",
  aspects: "tool", arudhas: "tool", ashtakavarga: "tool", shadbala: "tool",
};


/**
 * One node in the "Behind the scenes" timeline: a coloured dot sitting on a
 * vertical connector line, with its content to the right. `isFirst`/`isLast`
 * trim the connector so it starts/ends at the first/last dot.
 */
const TraceNode = ({ icon, dotBg, dotBorder, isFirst, isLast, children }) => (
  <div className="trace-node">
    <div className="trace-node__rail">
      {!isFirst && <div className="trace-node__line trace-node__line--top" />}
      {!isLast && <div className="trace-node__line trace-node__line--bottom" />}
      <span className="trace-node__dot" style={{ background: dotBg, borderColor: dotBorder }}>
        {icon}
      </span>
    </div>
    <div className="trace-node__body">{children}</div>
  </div>
);

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
  // Filter the history list by where a thread originated (all / astrologer / transit)
  const [historyFilter, setHistoryFilter] = useState("all");

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

  const addVargas = (values) => {
    setSelectedVargas((prev) => {
      const next = new Set(prev);
      values.forEach((v) => next.add(v));
      return Array.from(next).sort((a, b) => a - b);
    });
  };

  // Per-section context state (seed/tool/off), persisted across sessions.
  const [sections, setSections] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("ai_sections"));
      if (saved && typeof saved === "object") return { ...DEFAULT_SECTION_STATE, ...saved };
    } catch (e) {
      /* ignore */
    }
    return { ...DEFAULT_SECTION_STATE };
  });
  useEffect(() => {
    localStorage.setItem("ai_sections", JSON.stringify(sections));
  }, [sections]);

  // In Full-context mode there are no tools, so a section is only On (seed) or
  // Off; map any "tool" value to "seed" before sending so nothing silently drops.
  const effectiveSections = () => {
    if (mode === "tools") return sections;
    const out = {};
    for (const k of Object.keys(sections)) out[k] = sections[k] === "off" ? "off" : "seed";
    return out;
  };

  const cycleSection = (key) => {
    const order = mode === "tools" ? ["seed", "tool", "off"] : ["seed", "off"];
    setSections((prev) => {
      const cur = prev[key] === "tool" && mode !== "tools" ? "seed" : prev[key];
      const idx = order.indexOf(cur);
      return { ...prev, [key]: order[(idx + 1) % order.length] };
    });
  };

  // Suggest divisional charts based on keywords in the current question. Only
  // surfaces vargas the user hasn't already selected.
  const vargaSuggestions = (() => {
    const q = (currentQuestion || "").toLowerCase();
    if (!q.trim()) return [];
    const want = new Set();
    for (const rule of VARGA_SUGGESTIONS) {
      if (rule.keywords.some((k) => q.includes(k))) rule.vargas.forEach((v) => want.add(v));
    }
    return VARGAS.filter((v) => want.has(v.value) && !selectedVargas.includes(v.value));
  })();

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
        maxTokens: parseInt(localStorage.getItem("ai_max_tokens") || "0", 10) || undefined,
        vargas: selectedVargas,
        sections: effectiveSections(),
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

  // Toggle the "Behind the scenes" timeline. For a reopened answer the full per-call
  // result data isn't loaded yet — fetch it lazily by trace_id on first expand and
  // merge it onto the steps (in order; reopened steps carry no transient notices).
  const toggleTrace = async (index, message) => {
    const willOpen = !openTrace[index];
    setOpenTrace((p) => ({ ...p, [index]: willOpen }));
    if (!willOpen) return;
    const steps = message.toolSteps || [];
    const needs =
      message.trace_id && steps.some((s) => !s.notice && s.result === undefined);
    if (!needs) return;
    try {
      const resp = await astrologyService.getConversationTrace(
        conversationId,
        message.trace_id
      );
      const results = resp.data?.results || [];
      setMessages((prev) => {
        const next = [...prev];
        const msg = next[index];
        if (!msg || !msg.toolSteps) return prev;
        let ri = 0;
        const merged = msg.toolSteps.map((s) => {
          if (s.notice) return s;
          const r = results[ri++];
          return r ? { ...s, result: r.result, ok: r.ok ?? s.ok } : s;
        });
        next[index] = { ...msg, toolSteps: merged };
        return next;
      });
    } catch (e) {
      /* non-fatal: the timeline still shows the flow, just without the data blobs */
    }
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
              // rebuild the tool-call steps from the light persisted trace; the full
              // per-call result data is loaded lazily (by trace_id) on first expand
              trace_id: m.trace_id,
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

  // History list filtered by origin (Transit-page chats are saved here too).
  const convSource = (c) => c.source || "astrologer";
  const hasTransitConvos = conversations.some((c) => convSource(c) === "transit");
  const visibleConversations = conversations.filter(
    (c) => historyFilter === "all" || convSource(c) === historyFilter
  );

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
          <div className="ui-card ui-card--accent">
            <h3 className="ui-card-header ui-card-header--sm">
              <History size={20} />
              {t("ask.savedConversations")}
            </h3>
            {/* Filter chips — only shown once a Transit-page reading exists, so the
                main Ask page stays uncluttered for users who never use that chat. */}
            {hasTransitConvos && (
              <div className="history-filters">
                {["all", "astrologer", "transit"].map((f) => (
                  <button
                    key={f}
                    className={`history-filter${historyFilter === f ? " is-active" : ""}`}
                    onClick={() => setHistoryFilter(f)}
                  >
                    {t(`ask.filter.${f}`)}
                  </button>
                ))}
              </div>
            )}
            {visibleConversations.length === 0 ? (
              <p className="text-secondary" style={{ fontSize: "0.875rem", margin: 0 }}>
                {t("ask.noConversations")}
              </p>
            ) : (
              <div className="history-list">
                {visibleConversations.map((c) => (
                  <div
                    key={c.id}
                    className={`history-item${c.id === conversationId ? " is-active" : ""}`}
                    onClick={() => loadConversation(c.id)}
                  >
                    <div className="history-item__main">
                      <div className="history-item__title">
                        {convSource(c) === "transit" && (
                          <span className="history-source-badge">{t("ask.sourceTransit")}</span>
                        )}
                        {c.title}
                      </div>
                      <div className="history-item__meta">
                        {Math.floor((c.message_count || 0) / 2)} {t("ask.qa")}
                        {c.last_model ? ` · ${c.last_model}` : ""}
                        {c.updated_at ? ` · ${formatDate(c.updated_at)}` : ""}
                      </div>
                    </div>
                    <button
                      className="history-item__delete"
                      onClick={(e) => handleDeleteConversation(c.id, e)}
                      title={t("ask.deleteConversation")}
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
          <div className="fade-in fade-in--d2">
            <NorthIndianChart chartData={chartData} />
          </div>
        )}

        {/* AI Model Selector and Examples */}
        <div className="ask-grid fade-in fade-in--d4">
          {/* LLM Selector Card */}
          <div className="ask-card">
            <h3 className="ask-card__header">
              <Bot size={20} />
              {t("ask.aiModel")}
              <button
                className="ask-viewdata-btn"
                onClick={() => openInfo(lastContext)}
                title={t("ask.viewDataTitle")}
              >
                <Info size={18} />
                <span>{t("ask.viewDataSent")}</span>
              </button>
            </h3>
            {providersLoading ? (
              <div className="text-secondary" style={{ fontSize: "0.875rem" }}>
                {t("ask.detectingModels")}
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
                {/* Provider */}
                <label className="ask-field">
                  <span className="ask-field-label">{t("ask.provider")}</span>
                  <select
                    className="ask-select"
                    value={providerType}
                    onChange={(e) => handleProviderChange(e.target.value)}
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
                <label className="ask-field">
                  <span className="ask-field-label">{t("ask.model")}</span>
                  {selectedProvider && selectedProvider.models.length > 0 ? (
                    <select
                      className="ask-select"
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
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
                      className="ask-select"
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      placeholder={t("ask.enterModel")}
                    />
                  )}
                </label>

                {/* Availability note */}
                {selectedProvider && !selectedProvider.available && (
                  <div className="ask-warning">
                    ⚠ {selectedProvider.reason || t("ask.providerUnreachable")}
                  </div>
                )}

                {/* Advanced: editable base URL for local providers */}
                {selectedProvider && selectedProvider.editable_base_url && (
                  <div>
                    <button
                      type="button"
                      className="ask-link-btn"
                      onClick={() => setShowAdvanced((v) => !v)}
                    >
                      {showAdvanced ? "▾" : "▸"} {t("ask.advancedEndpoint")}
                    </button>
                    {showAdvanced && (
                      <input
                        type="text"
                        className="ask-select"
                        value={baseUrl}
                        onChange={(e) => setBaseUrl(e.target.value)}
                        placeholder={selectedProvider.base_url}
                        style={{ marginTop: "var(--space-sm)" }}
                      />
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Examples Card */}
          <div className="ask-card">
            <h3 className="ask-card__header">
              <MessageCircle size={20} />
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
          <div className="ask-card">
            <h3 className="ask-card__header ask-card__header--tight">
              <Wrench size={20} />
              {t("ask.answerMode")}
            </h3>
            <p className="ask-card__hint">
              {modeLocked ? t("ask.modeLockedHint") : t("ask.modeHint")}
            </p>
            <div className="ask-toggle-row">
              {[
                { val: "pass_all", label: t("ask.modeFullContext") },
                { val: "tools", label: t("ask.modeSmartLookup") },
              ].map((o) => {
                const active = mode === o.val;
                return (
                  <button
                    key={o.val}
                    type="button"
                    className={`ask-toggle-btn${active ? " is-active" : ""}`}
                    onClick={() => !modeLocked && setMode(o.val)}
                    disabled={modeLocked}
                    style={modeLocked && !active ? { opacity: 0.5 } : undefined}
                  >
                    {o.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Context Sections Card */}
          <div className="ask-card">
            <h3 className="ask-card__header ask-card__header--tight">
              <Wrench size={20} />
              {t("ask.contextSections")}
            </h3>
            <p className="ask-card__hint">
              {mode === "tools" ? t("ask.sectionsHintTools") : t("ask.sectionsHintFull")}
            </p>
            <div className="ask-section-list">
              {CONTEXT_SECTIONS.map((s) => {
                const state = mode === "tools"
                  ? sections[s.key]
                  : (sections[s.key] === "off" ? "off" : "seed");
                return (
                  <button
                    key={s.key}
                    type="button"
                    className={`ask-section-row ask-section-row--${state}`}
                    onClick={() => cycleSection(s.key)}
                    title={t("ask.clickToChange")}
                  >
                    <span className="ask-section-row__label">{t(s.labelKey)}</span>
                    <span className={`ask-section-row__state ask-section-row__state--${state}`}>
                      {state === "seed"
                        ? t("ask.stateSeed")
                        : state === "tool"
                          ? t("ask.stateTool")
                          : t("ask.stateOff")}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Divisional Charts (Vargas) Card */}
          <div className="ask-card">
            <h3 className="ask-card__header ask-card__header--tight">
              <Star size={20} />
              {t("ask.chartsToConsult")}
            </h3>
            <p className="ask-card__hint">{t("ask.chartsHint")}</p>
            <div className="ask-toggle-row">
              {VARGAS.map((v) => {
                const active = selectedVargas.includes(v.value);
                const isD1 = v.value === 1;
                return (
                  <button
                    key={v.value}
                    type="button"
                    className={`ask-toggle-btn${active ? " is-active" : ""}`}
                    onClick={() => !isD1 && toggleVarga(v.value)}
                    disabled={isD1}
                    title={`${v.name} — ${v.significance}`}
                    style={isD1 ? { cursor: "default", opacity: 0.8 } : undefined}
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
          <div className="ask-error">
            <span>⚠ {error}</span>
            <button
              className="ask-error__dismiss"
              onClick={() => setError("")}
              title={t("ask.dismiss")}
            >
              <X size={16} />
            </button>
          </div>
        )}

        {/* Chat Area */}
        <div className="chat-area fade-in fade-in--d6">
          <div className="messages-container">
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
                        className="msg-info-btn"
                        onClick={() => openInfo(messageInfo(message))}
                        title={t("ask.chartDataForAnswer")}
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
                      <div className="tool-steps">
                        {/* Pills timeline of the tool calls, in order */}
                        <div className="tool-pills">
                          {message.toolSteps.map((s, si) =>
                            s.notice ? (
                              <span key={si} className="tool-pill-notice">
                                {s.notice}
                              </span>
                            ) : (
                              <span
                                key={si}
                                className={`tool-pill${s.ok === false ? " tool-pill--err" : ""}`}
                                title={s.args ? JSON.stringify(s.args) : ""}
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
                              className="tool-trace-toggle"
                              onClick={() => toggleTrace(index, message)}
                            >
                              {openTrace[index] ? "▾" : "▸"} {t("ask.behindTheScenes")}
                            </button>
                          )}
                        </div>

                        {/* Expanded: a vertical timeline of the whole call flow —
                            seed → each tool call (+ the data it returned) → answer. */}
                        {openTrace[index] && realSteps.length > 0 && (
                          <div className="tool-trace-panel">
                            {/* Start: the seed sent to the model */}
                            <TraceNode
                              isFirst
                              icon={<Star size={11} />}
                              dotBg="var(--saffron, #e08a2c)"
                              dotBorder="var(--saffron, #e08a2c)"
                            >
                              <div className="trace-label">{t("ask.traceSeedSummary")}</div>
                              {(message.context || message.mode === "tools") && (
                                <button
                                  type="button"
                                  className="trace-link"
                                  onClick={() => openInfo(messageInfo(message))}
                                >
                                  {t("ask.traceViewWhatSent")}
                                </button>
                              )}
                            </TraceNode>

                            {/* Each tool call / notice, in order */}
                            {message.toolSteps.map((s, si) =>
                              s.notice ? (
                                <TraceNode
                                  key={si}
                                  icon={<span className="trace-bullet">•</span>}
                                  dotBg="var(--ink-light, #999)"
                                  dotBorder="var(--ink-light, #999)"
                                >
                                  <div className="trace-notice">{s.notice}</div>
                                </TraceNode>
                              ) : (
                                <TraceNode
                                  key={si}
                                  icon={
                                    s.ok === false ? (
                                      <X size={11} />
                                    ) : s.ok === null ? (
                                      <Wrench size={11} />
                                    ) : (
                                      <Check size={11} />
                                    )
                                  }
                                  dotBg={s.ok === false ? "#c0392b" : "var(--saffron, #e08a2c)"}
                                  dotBorder={s.ok === false ? "#c0392b" : "var(--saffron, #e08a2c)"}
                                >
                                  <div className="trace-label">
                                    {t("ask.traceLookedUp", { tool: fmtTool(s.name) })}
                                    {s.args && Object.keys(s.args).length ? (
                                      <span className="trace-label__args">
                                        {" "}
                                        ({Object.entries(s.args)
                                          .map(([k, v]) => `${k}: ${v}`)
                                          .join(", ")})
                                      </span>
                                    ) : null}
                                  </div>
                                  {s.result !== undefined && (
                                    <details className="trace-data">
                                      <summary className="trace-data__summary">{t("ask.traceViewData")}</summary>
                                      <pre className="trace-data__pre">
                                        {JSON.stringify(s.result, null, 2)}
                                      </pre>
                                    </details>
                                  )}
                                </TraceNode>
                              )
                            )}

                            {/* End: the written answer */}
                            <TraceNode
                              isLast
                              icon={<Sparkles size={11} />}
                              dotBg="var(--vermillion, #c0392b)"
                              dotBorder="var(--vermillion, #c0392b)"
                            >
                              <div className="trace-label">
                                {message.streaming
                                  ? t("ask.traceWriting")
                                  : t("ask.traceWroteAnswer")}
                              </div>
                            </TraceNode>
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
                      <StreamingMarkdown
                        content={message.content}
                        streaming={message.streaming}
                      />
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

          {vargaSuggestions.length > 0 && (
            <div className="varga-suggest-row">
              <span className="varga-suggest-row__hint">{t("ask.suggestedCharts")}</span>
              {vargaSuggestions.map((v) => (
                <button
                  key={v.value}
                  type="button"
                  className="varga-suggest-chip"
                  onClick={() => addVargas([v.value])}
                  title={`${v.name} — ${v.significance}`}
                >
                  + {v.code} <span className="varga-suggest-chip__sig">{v.significance}</span>
                </button>
              ))}
            </div>
          )}

          <div className="chat-input-container">
            <ChatComposer
              value={currentQuestion}
              onChange={setCurrentQuestion}
              onSubmit={() => handleAskQuestion(currentQuestion)}
              onStop={handleStop}
              busy={loading}
              multiline={false}
              placeholder={t("ask.inputPlaceholder")}
              sendTitle={t("ask.send")}
              stopTitle={t("ask.stopTitle")}
              stopLabel={t("ask.stop")}
            />
          </div>

          {/* Safety / disclaimer footer */}
          <div className="ai-disclaimer">⚠ {t("ask.disclaimer")}</div>
        </div>

        {/* Info Modal */}
        {showInfoModal && (
          <div className="modal-overlay" onClick={() => setShowInfoModal(false)}>
            <div className="modal-panel modal-panel--lg" onClick={(e) => e.stopPropagation()}>
              {/* Modal Header */}
              <div className="modal-header modal-header--sticky">
                <h3 className="modal-title">
                  <Info size={24} />
                  {t("ask.chartDataSentToAI")}
                </h3>
                <button className="modal-close" onClick={() => setShowInfoModal(false)}>
                  <X size={24} />
                </button>
              </div>

              {/* Modal Content */}
              <div className="modal-body" style={{ fontSize: "0.875rem", lineHeight: "1.6" }}>
                <div className="info-modal-intro">
                  <p>{modalData ? t("ask.modalIntroWithData") : t("ask.modalIntroNoData")}</p>
                </div>

                <pre className="info-modal-pre">
                  {JSON.stringify(modalData || getChartDataForLLM(), null, 2)}
                </pre>

                <div className="info-modal-note">
                  <p className="fw-600 text-indigo">📝 {t("ask.note")}</p>
                  <p className="text-secondary">{t("ask.noteBody")}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* API Keys Modal (8.6 — per-user, encrypted server-side) */}
        {showKeysModal && (
          <div className="modal-overlay" onClick={() => setShowKeysModal(false)}>
            <div className="modal-panel modal-panel--sm" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h3 className="modal-title">
                  <KeyRound size={24} />
                  {t("ask.yourApiKeys")}
                </h3>
                <button className="modal-close" onClick={() => setShowKeysModal(false)}>
                  <X size={24} />
                </button>
              </div>

              <div className="modal-body">
                <p
                  className="text-secondary"
                  style={{ margin: "0 0 var(--space-lg)", fontSize: "0.8125rem", lineHeight: 1.6 }}
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
                          className="fw-700 text-indigo"
                          style={{ fontSize: "0.9375rem" }}
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
