"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { useAuth } from "@/components/auth/AuthProvider";
import { type AgentTrace, type ConversationTrace, getTrace } from "@/lib/api";

export function TraceDashboard({ conversationId }: Readonly<{ conversationId: string }>) {
  const { token } = useAuth();
  const [trace, setTrace] = useState<ConversationTrace | null>(null);
  const [expandedAgentIds, setExpandedAgentIds] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const refreshTrace = useCallback(async () => {
    if (!token) {
      return;
    }
    setIsLoading(true);
    setError("");
    try {
      const loadedTrace = await getTrace(token, conversationId);
      setTrace(loadedTrace);
      setExpandedAgentIds((current) => {
        if (current.size > 0) {
          return current;
        }
        const firstAgent = loadedTrace.agent_traces[0];
        return firstAgent ? new Set([firstAgent.id]) : new Set();
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load trace.");
    } finally {
      setIsLoading(false);
    }
  }, [conversationId, token]);

  useEffect(() => {
    void refreshTrace();
  }, [refreshTrace]);

  const summary = useMemo(() => {
    if (!trace) {
      return null;
    }
    const durationMs =
      trace.completed_at !== null
        ? new Date(trace.completed_at).getTime() - new Date(trace.created_at).getTime()
        : null;
    return {
      agents: trace.agent_traces.length,
      duration: durationMs !== null && durationMs >= 0 ? formatDuration(durationMs) : "Running",
      created: formatDate(trace.created_at),
    };
  }, [trace]);

  function toggleAgent(agentId: string) {
    setExpandedAgentIds((current) => {
      const next = new Set(current);
      if (next.has(agentId)) {
        next.delete(agentId);
      } else {
        next.add(agentId);
      }
      return next;
    });
  }

  return (
    <main className="page-shell">
      <section className="page-header">
        <div>
          <h1>Agent Trace</h1>
          <p>Inspect the reasoning workflow, retrieved evidence, guardrails, and final synthesis.</p>
        </div>
        <div className="trace-header-actions">
          <Link className="button" href="/chat">
            Back to chat
          </Link>
          <button className="button" disabled={isLoading} onClick={refreshTrace} type="button">
            {isLoading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </section>

      {error ? <div className="form-error trace-alert">{error}</div> : null}
      {isLoading && !trace ? (
        <section className="panel">
          <p>Loading trace...</p>
        </section>
      ) : null}

      {trace && summary ? (
        <>
          <section className="stats-grid trace-stats" aria-label="Trace summary">
            <TraceStat label="Status" value={trace.status} />
            <TraceStat label="Workflow steps" value={summary.agents.toLocaleString()} />
            <TraceStat label="Duration" value={summary.duration} />
            <TraceStat label="Started" value={summary.created} />
          </section>

          <section className="trace-layout">
            <aside className="panel trace-timeline-panel">
              <h2>Timeline</h2>
              <div className="trace-question">
                <span>Question</span>
                <p>{trace.question}</p>
                {trace.equipment_name ? <strong>{trace.equipment_name}</strong> : null}
              </div>
              <ol className="trace-timeline">
                {trace.agent_traces.map((agent) => (
                  <li key={agent.id}>
                    <button
                      className={expandedAgentIds.has(agent.id) ? "active" : undefined}
                      onClick={() => toggleAgent(agent.id)}
                      type="button"
                    >
                      <span>{agent.sequence}</span>
                      <strong>{agent.agent_name}</strong>
                    </button>
                  </li>
                ))}
              </ol>
            </aside>

            <section className="trace-main">
              {trace.final_answer ? (
                <article className="panel trace-final-answer">
                  <h2>Final Answer</h2>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{trace.final_answer}</ReactMarkdown>
                </article>
              ) : null}

              <div className="trace-agent-list">
                {trace.agent_traces.map((agent) => (
                  <AgentTraceCard
                    agent={agent}
                    isExpanded={expandedAgentIds.has(agent.id)}
                    key={agent.id}
                    onToggle={() => toggleAgent(agent.id)}
                  />
                ))}
              </div>
            </section>
          </section>
        </>
      ) : null}
    </main>
  );
}

function TraceStat({ label, value }: Readonly<{ label: string; value: string }>) {
  return (
    <div className="stat trace-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function AgentTraceCard({
  agent,
  isExpanded,
  onToggle,
}: Readonly<{
  agent: AgentTrace;
  isExpanded: boolean;
  onToggle: () => void;
}>) {
  const duration = formatDuration(new Date(agent.completed_at).getTime() - new Date(agent.started_at).getTime());

  return (
    <article className="panel trace-agent-card">
      <button className="trace-agent-card-header" onClick={onToggle} type="button">
        <div>
          <span>Step {agent.sequence}</span>
          <h2>{agent.agent_name}</h2>
        </div>
        <div className="trace-agent-meta">
          <strong className={`status status-${agent.status}`}>{agent.status}</strong>
          <span>{duration}</span>
          <span>{isExpanded ? "Hide" : "Show"}</span>
        </div>
      </button>

      {isExpanded ? (
        <div className="trace-agent-detail">
          <JsonPanel title="Input" value={agent.input} />
          <JsonPanel title="Output" value={agent.output} />
        </div>
      ) : null}
    </article>
  );
}

function JsonPanel({ title, value }: Readonly<{ title: string; value: Record<string, unknown> }>) {
  return (
    <section className="json-panel">
      <h3>{title}</h3>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </section>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatDuration(milliseconds: number) {
  if (!Number.isFinite(milliseconds) || milliseconds < 0) {
    return "0 ms";
  }
  if (milliseconds < 1000) {
    return `${Math.round(milliseconds)} ms`;
  }
  return `${(milliseconds / 1000).toFixed(1)} s`;
}
