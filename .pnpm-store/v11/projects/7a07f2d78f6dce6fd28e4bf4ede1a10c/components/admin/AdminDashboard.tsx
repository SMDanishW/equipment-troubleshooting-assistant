"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import {
  type AdminConversation,
  type AdminUserOverview,
  type EquipmentDocument,
  getDockerLogs,
  listAdminUserOverview,
  listDockerLogServices,
} from "@/lib/api";

export function AdminDashboard() {
  const { token, user } = useAuth();
  const [services, setServices] = useState<string[]>([]);
  const [selectedService, setSelectedService] = useState("backend");
  const [tail, setTail] = useState(200);
  const [logs, setLogs] = useState("");
  const [userOverview, setUserOverview] = useState<AdminUserOverview[]>([]);
  const [expandedUserIds, setExpandedUserIds] = useState<Set<string>>(new Set());
  const [isLogsLoading, setIsLogsLoading] = useState(false);
  const [isUsersLoading, setIsUsersLoading] = useState(false);
  const [error, setError] = useState("");

  const totals = useMemo(
    () => ({
      users: userOverview.length,
      documents: userOverview.reduce((sum, item) => sum + item.documents_count, 0),
      chats: userOverview.reduce((sum, item) => sum + item.conversations_count, 0),
      admins: userOverview.filter((item) => item.role === "admin").length,
    }),
    [userOverview],
  );

  const refreshLogs = useCallback(async () => {
    if (!token || user?.role !== "admin") {
      return;
    }
    setIsLogsLoading(true);
    setError("");
    try {
      const response = await getDockerLogs(token, selectedService, tail);
      setLogs(response.logs);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load Docker logs.");
    } finally {
      setIsLogsLoading(false);
    }
  }, [selectedService, tail, token, user?.role]);

  const refreshUserOverview = useCallback(async () => {
    if (!token || user?.role !== "admin") {
      return;
    }
    setIsUsersLoading(true);
    setError("");
    try {
      const overview = await listAdminUserOverview(token);
      setUserOverview(overview);
      setExpandedUserIds((current) => {
        if (current.size > 0) {
          return current;
        }
        const firstUser = overview[0];
        return firstUser ? new Set([firstUser.id]) : new Set();
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load user overview.");
    } finally {
      setIsUsersLoading(false);
    }
  }, [token, user?.role]);

  useEffect(() => {
    async function loadServices() {
      if (!token || user?.role !== "admin") {
        return;
      }
      setError("");
      try {
        const loadedServices = await listDockerLogServices(token);
        setServices(loadedServices);
        setSelectedService((current) => (loadedServices.includes(current) ? current : (loadedServices[0] ?? "backend")));
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Unable to load Docker services.");
      }
    }

    void loadServices();
  }, [token, user?.role]);

  useEffect(() => {
    void refreshLogs();
  }, [refreshLogs]);

  useEffect(() => {
    void refreshUserOverview();
  }, [refreshUserOverview]);

  function toggleUser(userId: string) {
    setExpandedUserIds((current) => {
      const next = new Set(current);
      if (next.has(userId)) {
        next.delete(userId);
      } else {
        next.add(userId);
      }
      return next;
    });
  }

  if (user?.role !== "admin") {
    return (
      <main className="page-shell">
        <section className="panel">
          <h1>Admin</h1>
          <p>Admin role required.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="page-shell">
      <section className="page-header">
        <div>
          <h1>Admin</h1>
          <p>Inspect local demo services, users, documents, and chat traces.</p>
        </div>
        <div className="trace-header-actions">
          <button className="button" disabled={isUsersLoading} onClick={refreshUserOverview} type="button">
            {isUsersLoading ? "Refreshing..." : "Refresh users"}
          </button>
          <button className="button" disabled={isLogsLoading} onClick={refreshLogs} type="button">
            {isLogsLoading ? "Refreshing..." : "Refresh logs"}
          </button>
        </div>
      </section>

      {error ? <div className="form-error trace-alert">{error}</div> : null}

      <section className="stats-grid admin-stats" aria-label="Admin totals">
        <AdminStat label="Users" value={totals.users} />
        <AdminStat label="Documents" value={totals.documents} />
        <AdminStat label="Chats" value={totals.chats} />
        <AdminStat label="Admins" value={totals.admins} />
      </section>

      <section className="admin-users-section" aria-label="User visibility">
        <div className="admin-section-heading">
          <h2>User Activity</h2>
          <span>{isUsersLoading ? "Loading" : `${userOverview.length} users`}</span>
        </div>
        {userOverview.length === 0 && !isUsersLoading ? <p className="empty-state">No users found.</p> : null}
        <div className="admin-user-list">
          {userOverview.map((item) => (
            <UserOverviewCard
              isExpanded={expandedUserIds.has(item.id)}
              key={item.id}
              onToggle={() => toggleUser(item.id)}
              user={item}
            />
          ))}
        </div>
      </section>

      <section className="admin-layout">
        <form className="panel form admin-controls" onSubmit={(event) => event.preventDefault()}>
          <div>
            <h2>Docker Logs</h2>
            <p>Reads logs from the local Docker Compose containers when the backend can access Docker.</p>
          </div>
          <label>
            <span>Service</span>
            <select onChange={(event) => setSelectedService(event.target.value)} value={selectedService}>
              {services.length === 0 ? <option value="backend">backend</option> : null}
              {services.map((service) => (
                <option key={service} value={service}>
                  {service}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Tail lines</span>
            <input
              max={1000}
              min={20}
              onChange={(event) => setTail(Number(event.target.value))}
              step={20}
              type="number"
              value={tail}
            />
          </label>
        </form>

        <section className="panel admin-log-panel">
          <div className="panel-heading">
            <h2>{selectedService} logs</h2>
            <span>{tail} lines</span>
          </div>
          <pre className="log-output">{logs || "No logs loaded yet."}</pre>
        </section>
      </section>
    </main>
  );
}

function AdminStat({ label, value }: Readonly<{ label: string; value: number }>) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong>{value.toLocaleString()}</strong>
    </div>
  );
}

function UserOverviewCard({
  isExpanded,
  onToggle,
  user,
}: Readonly<{
  isExpanded: boolean;
  onToggle: () => void;
  user: AdminUserOverview;
}>) {
  return (
    <article className="admin-user-card">
      <button className="admin-user-card-header" onClick={onToggle} type="button">
        <div>
          <h3>{user.username}</h3>
          <p>{user.email}</p>
        </div>
        <div className="admin-user-meta">
          <span className={`status role-${user.role}`}>{user.role}</span>
          <span>{user.documents_count.toLocaleString()} docs</span>
          <span>{user.conversations_count.toLocaleString()} chats</span>
          <span>{isExpanded ? "Hide" : "Show"}</span>
        </div>
      </button>

      {isExpanded ? (
        <div className="admin-user-detail">
          <section>
            <h4>Uploaded Documents</h4>
            <div className="admin-row-list">
              {user.documents.length === 0 ? <p className="empty-state">No documents uploaded.</p> : null}
              {user.documents.map((document) => (
                <DocumentRow document={document} key={document.id} />
              ))}
            </div>
          </section>
          <section>
            <h4>Chat History</h4>
            <div className="admin-row-list">
              {user.conversations.length === 0 ? <p className="empty-state">No chats yet.</p> : null}
              {user.conversations.map((conversation) => (
                <ConversationRow conversation={conversation} key={conversation.id} />
              ))}
            </div>
          </section>
        </div>
      ) : null}
    </article>
  );
}

function DocumentRow({ document }: Readonly<{ document: EquipmentDocument }>) {
  return (
    <div className="admin-data-row">
      <div>
        <strong>{document.filename}</strong>
        <span>
          {document.equipment_name} - {formatDocumentType(document.document_type)}
        </span>
      </div>
      <div className="admin-row-metrics">
        <span className={`status status-${document.status}`}>{document.status}</span>
        <span>{document.page_count.toLocaleString()} pages</span>
        <span>{document.images_extracted_count.toLocaleString()} images</span>
      </div>
    </div>
  );
}

function ConversationRow({ conversation }: Readonly<{ conversation: AdminConversation }>) {
  return (
    <div className="admin-data-row">
      <div>
        <strong>{conversation.question}</strong>
        <span>
          {conversation.equipment_name ?? "No equipment"} - {formatDate(conversation.created_at)}
        </span>
      </div>
      <div className="admin-row-metrics">
        <span className={`status status-${conversation.status}`}>{conversation.status}</span>
        <Link className="button compact" href={`/traces/${conversation.id}`}>
          Trace
        </Link>
      </div>
    </div>
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

function formatDocumentType(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
