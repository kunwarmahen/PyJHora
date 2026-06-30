import React, { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Sparkles, ChevronDown, ChevronUp } from "lucide-react";
import { streamAskQuestion } from "../services/api";
import { DEFAULT_AYANAMSA } from "../constants/jyotish";
import { ChatBubble } from "./chat/ChatBubble";
import { ChatComposer } from "./chat/ChatComposer";
import { SuggestionChips } from "./chat/SuggestionChips";
import "../styles/Chat.css";

// Slow movers whose gochara is the high-signal stuff for a "what's happening to
// me now" reading. Used to surface smart suggestion chips from the live data.
const SLOW = new Set(["Jupiter", "Saturn", "Rahu", "Ketu"]);

// Read the model config the user already picked in "Ask Astrologer". The server
// resolves the actual API key (per-user stored key → env key), so we only need
// the provider/model selection here — no key handling in this widget.
const readModelConfig = () => {
  const providerType = localStorage.getItem("ai_provider_type") || "ollama";
  return {
    providerType,
    model: localStorage.getItem("ai_model") || "",
    // base_url only matters for the self-hosted (ollama) provider; sending it for
    // hosted providers could override their API base, so scope it to ollama.
    baseUrl: providerType === "ollama" ? localStorage.getItem("ai_base_url") || undefined : undefined,
    legacyProvider: providerType === "ollama" ? "qwen" : providerType,
  };
};

/**
 * Embedded, transit-scoped AI chat. Reuses the existing /ask/stream endpoint but
 * seeds it with *only* the gochara + running-dasha context (pass_all mode), so the
 * model interprets exactly the transits the user is looking at — no redundant tool
 * call, no drift from the displayed chart. Keeps its own conversation thread.
 */
export const TransitChat = ({ birthDetails, profile, result, ayanamsa = DEFAULT_AYANAMSA }) => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]); // { role: "user"|"ai", content, streaming?, error? }
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const convIdRef = useRef(null);
  const abortRef = useRef(null);
  const scrollRef = useRef(null);

  // The model is inherited from "Ask AI Astrologer" (same localStorage keys). Show
  // the current selection; fall back to the provider name when no specific model is
  // set (e.g. the default local Ollama provider), or a generic label if neither.
  const cfg = readModelConfig();
  const configuredModelLabel = cfg.model || cfg.providerType || t("transitChat.modelDefault");

  // Smart suggestion chips derived from what's actually on screen. Saturn's
  // gochara from the natal Moon (12th/1st/2nd) is Sade Sati; retrogrades and
  // upcoming slow-mover ingresses are the other natural "what does this mean"
  // questions for the current sky.
  const chips = useMemo(() => {
    const out = [];
    const planets = result?.planets || {};
    const sat = planets.Saturn;
    if (sat && [12, 1, 2].includes(sat.house_from_moon)) {
      out.push(t("transitChat.chipSadeSati"));
    }
    const retro = Object.entries(planets)
      .filter(([, p]) => p.retrograde)
      .map(([name]) => name);
    if (retro.length) {
      out.push(t("transitChat.chipRetro", { planet: retro[0] }));
    }
    const ingress = (result?.upcoming || []).find((u) => SLOW.has(u.planet));
    if (ingress) {
      out.push(
        t("transitChat.chipIngress", { planet: ingress.planet, sign: ingress.to_sign })
      );
    }
    out.push(t("transitChat.chipSummary"));
    out.push(t("transitChat.chipMostImportant"));
    // De-dup and cap so the row stays tidy.
    return [...new Set(out)].slice(0, 4);
  }, [result, t]);

  const scrollToEnd = () => {
    requestAnimationFrame(() => {
      const el = scrollRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    });
  };

  const send = (questionRaw) => {
    const question = (questionRaw ?? input).trim();
    if (!question || busy || !birthDetails || !profile) return;

    setInput("");
    setBusy(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: question },
      { role: "ai", content: "", streaming: true },
    ]);
    scrollToEnd();

    const updateLastAi = (updater) =>
      setMessages((prev) => {
        const next = [...prev];
        for (let i = next.length - 1; i >= 0; i--) {
          if (next[i].role === "ai") {
            next[i] = updater(next[i]);
            break;
          }
        }
        return next;
      });

    abortRef.current = streamAskQuestion(
      birthDetails,
      question,
      {
        ...readModelConfig(),
        // Transit reading: natal D1 is always sent; add gochara + the running
        // dasha (the classic timing co-factor), and drop the heavier sections.
        sections: {
          transits: true,
          dasha_tree: true,
          yogas: false,
          doshas: false,
          ashtakavarga: false,
          shadbala: false,
        },
        vargas: [1],
        mode: "pass_all",
        source: "transit",
        ayanamsa,
        conversationId: convIdRef.current,
        profileId: profile._id,
      },
      {
        onMeta: (meta) =>
          updateLastAi((m) => ({
            ...m,
            provider: meta.provider || m.provider,
            model: meta.model || m.model,
          })),
        onToken: (tok) =>
          updateLastAi((m) => ({ ...m, content: m.content + tok })),
        onDone: (d) => {
          if (d.conversation_id) convIdRef.current = d.conversation_id;
          updateLastAi((m) => ({ ...m, streaming: false }));
          setBusy(false);
          abortRef.current = null;
          scrollToEnd();
        },
        onError: (e) => {
          updateLastAi((m) => ({
            ...m,
            streaming: false,
            error: !m.content,
            content: m.content || `${t("transitChat.error")}: ${e.message}`,
          }));
          setBusy(false);
          abortRef.current = null;
        },
      }
    );
  };

  const stop = () => {
    if (abortRef.current) abortRef.current();
    abortRef.current = null;
    setBusy(false);
    setMessages((prev) => {
      const next = [...prev];
      for (let i = next.length - 1; i >= 0; i--) {
        if (next[i].role === "ai" && next[i].streaming) {
          next[i] = { ...next[i], streaming: false };
          break;
        }
      }
      return next;
    });
  };

  if (!result) return null;

  return (
    <div className="transit-chat">
      {/* Header / toggle */}
      <button type="button" className="transit-chat__toggle" onClick={() => setOpen((o) => !o)}>
        <Sparkles size={20} style={{ color: "var(--saffron)" }} />
        <span className="transit-chat__title">{t("transitChat.title")}</span>
        {open ? (
          <ChevronUp size={20} style={{ color: "var(--text-muted)" }} />
        ) : (
          <ChevronDown size={20} style={{ color: "var(--text-muted)" }} />
        )}
      </button>

      {open && (
        <div className="transit-chat__body">
          <p className="transit-chat__intro">{t("transitChat.intro")}</p>

          {/* Where the model comes from — inherited from "Ask AI Astrologer". */}
          <p className="transit-chat__model">
            {t("transitChat.modelSource", { model: configuredModelLabel })}{" "}
            <Link to="/ask-astrologer">{t("transitChat.modelChange")}</Link>
          </p>

          {/* Messages */}
          {messages.length > 0 && (
            <div ref={scrollRef} className="chat-messages transit-chat__messages">
              {messages.map((m, i) => (
                <ChatBubble
                  key={i}
                  role={m.role}
                  content={m.content}
                  streaming={m.streaming}
                  error={m.error}
                  thinkingLabel={t("transitChat.thinking")}
                  meta={
                    !m.streaming && !m.error && (m.model || m.provider)
                      ? t("transitChat.answeredBy", { model: m.model || m.provider })
                      : null
                  }
                />
              ))}
            </div>
          )}

          {/* Suggestion chips (shown until the user has a thread going) */}
          {messages.length === 0 && (
            <div className="transit-chat__chips">
              <SuggestionChips chips={chips} onSelect={send} disabled={busy} />
            </div>
          )}

          {/* Input */}
          <ChatComposer
            value={input}
            onChange={setInput}
            onSubmit={() => send()}
            onStop={stop}
            busy={busy}
            placeholder={t("transitChat.placeholder")}
            sendTitle={t("transitChat.send")}
            stopTitle={t("transitChat.stop")}
          />
          <p className="transit-chat__disclaimer">{t("transitChat.disclaimer")}</p>
        </div>
      )}
    </div>
  );
};
