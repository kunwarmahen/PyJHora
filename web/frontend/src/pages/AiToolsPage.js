import React, { useState, useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Wrench, ChevronDown, ChevronRight } from "lucide-react";
import { astrologyService } from "../services/api";
import { PageHeader } from "../components/PageHeader";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import "../styles/Dashboard.css";
import "../styles/AiTools.css";

// Renders one tool's JSON-schema parameters in a human-readable list, with the
// raw schema kept available for the curious.
const ToolSchema = ({ parameters }) => {
  const { t } = useTranslation();
  const props = (parameters && parameters.properties) || {};
  const required = new Set((parameters && parameters.required) || []);
  const names = Object.keys(props);

  if (names.length === 0) {
    return <p className="ai-tool-noparams">{t("aiTools.noParams")}</p>;
  }

  return (
    <div className="ai-tool-params">
      <div className="ai-tool-params-label">{t("aiTools.parameters")}</div>
      <ul>
        {names.map((name) => {
          const p = props[name] || {};
          const type = p.type === "array" ? `${p.items?.type || "item"}[]` : p.type;
          return (
            <li key={name}>
              <code>{name}</code>
              {type && <span className="ai-tool-param-type">{type}</span>}
              {required.has(name) && <span className="ai-tool-param-req">required</span>}
              {p.description && <span className="ai-tool-param-desc">{p.description}</span>}
            </li>
          );
        })}
      </ul>
    </div>
  );
};

const ToolCard = ({ tool }) => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <div className="ai-tool">
      <div className="ai-tool-head">
        <span className="ai-tool-label">{tool.label}</span>
        <code className="ai-tool-name">{tool.name}</code>
      </div>
      <p className="ai-tool-desc">{tool.description}</p>
      <button className="ai-tool-toggle" onClick={() => setOpen((o) => !o)}>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        {open ? t("aiTools.hideSchema") : t("aiTools.showSchema")}
      </button>
      {open && <ToolSchema parameters={tool.parameters} />}
    </div>
  );
};

export const AiToolsPage = () => {
  const { t } = useTranslation();
  const [tools, setTools] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sources, setSources] = useState(null);

  useEffect(() => {
    let cancelled = false;
    astrologyService
      .getAiTools()
      .then((res) => {
        if (!cancelled) setTools(res.data.tools || []);
      })
      .catch(() => {
        if (!cancelled) setError(t("aiTools.loadError"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    astrologyService
      .getAiSources()
      .then((res) => !cancelled && setSources(res.data))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Group tools by category, preserving the backend's order within each group.
  const groups = useMemo(() => {
    const out = [];
    (tools || []).forEach((tool) => {
      let g = out.find((x) => x.category === tool.category);
      if (!g) {
        g = { category: tool.category, items: [] };
        out.push(g);
      }
      g.items.push(tool);
    });
    return out;
  }, [tools]);

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Wrench size={24} />}
        title={t("aiTools.title")}
        subtitle={t("aiTools.subtitle")}
        accent="indigo"
      />

      <div className="dashboard-content">
        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("common.loading")} />
          </Card>
        ) : (
          <>
            <p className="ai-tools-intro">{t("aiTools.intro")}</p>
            {sources && (
              <p className={`ai-tools-sources ${sources.available ? "is-on" : "is-off"}`}>
                {sources.available
                  ? t("aiTools.citationsOn", { count: sources.passages })
                  : t("aiTools.citationsOff")}
              </p>
            )}
            {groups.map((g) => (
              <Card
                key={g.category}
                title={g.category}
                count={g.items.length}
                accent="indigo"
                className="ai-tools-group"
              >
                {g.items.map((tool) => (
                  <ToolCard key={tool.name} tool={tool} />
                ))}
              </Card>
            ))}
          </>
        )}
      </div>
    </div>
  );
};

export default AiToolsPage;
