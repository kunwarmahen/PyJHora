import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldAlert, Users, Activity, ScrollText, Trash2, Ban, Eye, RefreshCw } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { adminService } from "../services/api";
import { PageHeader } from "../components/PageHeader";
import { Card } from "../components/Card";
import { LoadingState } from "../components/LoadingState";
import { ErrorBanner } from "../components/ErrorBanner";
import "../styles/Shared.css";
import { Tabs, useTabs } from "../components/Tabs";
import "../styles/Admin.css";

const errMsg = (e) => e?.response?.data?.detail || e?.message || "Something went wrong";

const fmtDate = (v) => {
  if (!v) return "—";
  try {
    return new Date(v).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  } catch {
    return String(v);
  }
};

const StatCard = ({ label, value }) => (
  <div className="admin-stat">
    <div className="admin-stat-label">{label}</div>
    <div className="admin-stat-value">{value}</div>
  </div>
);

/**
 * Admin console (§44). Deployer-only. The route guard below redirects non-admins,
 * but every endpoint this page calls is also enforced server-side — the UI gate
 * is convenience, not security.
 */
export const AdminPage = () => {
  const navigate = useNavigate();
  const { user, isLoading: authLoading } = useAuth();
  // Console sections. Deployer-only screen, so labels stay untranslated like the
  // rest of this page.
  const ADMIN_TABS = useMemo(
    () => [
      { key: "overview", label: "Overview", icon: <Activity size={15} /> },
      { key: "users", label: "Users", icon: <Users size={15} /> },
      { key: "audit", label: "Audit log", icon: <ScrollText size={15} /> },
    ],
    []
  );
  const { tabs, active: tab, setActive: setTab } = useTabs(ADMIN_TABS);

  // Redirect anyone who isn't an admin once auth has resolved.
  useEffect(() => {
    if (!authLoading && user && !user.is_admin) navigate("/dashboard", { replace: true });
  }, [authLoading, user, navigate]);

  if (authLoading || !user) return <LoadingState />;
  if (!user.is_admin) return null;

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<ShieldAlert size={22} />}
        title="Admin console"
        subtitle="Deployment operations — all actions are audit-logged"
        accent="indigo"
      />
      <div className="dashboard-content">
        <Tabs tabs={tabs} active={tab} onChange={setTab} ariaLabel="Admin console" />

        {tab === "overview" && <OverviewTab />}
        {tab === "users" && <UsersTab />}
        {tab === "audit" && <AuditTab />}
      </div>
    </div>
  );
};

function OverviewTab() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminService
      .stats()
      .then((r) => setStats(r.data))
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingState />;
  if (error) return <ErrorBanner message={error} />;
  if (!stats) return null;

  return (
    <>
      <div className="admin-stat-grid">
        <StatCard label="Total users" value={stats.total_users} />
        <StatCard label="New · 7 days" value={stats.new_users_7d} />
        <StatCard label="New · 30 days" value={stats.new_users_30d} />
        <StatCard label="Suspended" value={stats.suspended} />
        <StatCard label="Admins" value={stats.admins} />
        <StatCard label="Google accounts" value={stats.google_accounts} />
      </div>

      <Card title="Stored records" accent="indigo">
        <div className="admin-stat-grid" style={{ marginBottom: 0 }}>
          {Object.entries(stats.collections).map(([k, v]) => (
            <StatCard key={k} label={k.replace(/_/g, " ")} value={v} />
          ))}
        </div>
      </Card>

      <div className="admin-content-note" style={{ marginTop: "var(--space-lg)" }}>
        {stats.content_access_enabled ? (
          <>
            <strong>Content access is ON.</strong> You can open individual users' private
            readings, chats and journal entries. Every such view is recorded in the audit log.
          </>
        ) : (
          <>
            <strong>Content access is OFF.</strong> The console shows metadata and counts
            only. To inspect a user's actual content, set <code>ADMIN_CONTENT_ACCESS=true</code> and
            redeploy — a deliberate "break glass" step.
          </>
        )}
      </div>
    </>
  );
}

function UsersTab() {
  const [users, setUsers] = useState([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null); // username of user in detail modal
  const [confirmDelete, setConfirmDelete] = useState(null);

  const load = useCallback((query = "") => {
    setLoading(true);
    adminService
      .listUsers(query)
      .then((r) => setUsers(r.data.users || []))
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Debounce the search.
  useEffect(() => {
    const id = setTimeout(() => load(q), 300);
    return () => clearTimeout(id);
  }, [q, load]);

  const toggleSuspend = async (u) => {
    try {
      await adminService.suspend(u.username, !u.suspended);
      load(q);
    } catch (e) {
      setError(errMsg(e));
    }
  };

  const doDelete = async (username) => {
    try {
      await adminService.deleteUser(username);
      setConfirmDelete(null);
      load(q);
    } catch (e) {
      setError(errMsg(e));
    }
  };

  return (
    <>
      <ErrorBanner message={error} />
      <input
        className="admin-search"
        placeholder="Search username, email or name…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      {loading ? (
        <LoadingState />
      ) : (
        <Card accent="indigo">
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Joined</th>
                  <th>Sign-in</th>
                  <th>Profiles</th>
                  <th>Readings</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.username}>
                    <td>
                      <div className="admin-user-cell">
                        <span>{u.name || u.username}</span>
                        <small>{u.email}</small>
                      </div>
                    </td>
                    <td>{fmtDate(u.created_at)}</td>
                    <td>{u.auth_provider}</td>
                    <td>{u.counts.saved_profiles}</td>
                    <td>{u.counts.ai_conversations}</td>
                    <td>
                      {u.is_admin && <span className="admin-badge admin-badge--admin">admin</span>}{" "}
                      {u.suspended && <span className="admin-badge admin-badge--suspended">suspended</span>}
                      {!u.is_admin && !u.suspended && <span className="admin-badge">active</span>}
                    </td>
                    <td>
                      <div className="admin-actions">
                        <button className="admin-btn" onClick={() => setSelected(u.username)}>
                          <Eye size={13} style={{ verticalAlign: "-2px" }} /> View
                        </button>
                        <button
                          className="admin-btn"
                          disabled={u.is_admin}
                          onClick={() => toggleSuspend(u)}
                        >
                          <Ban size={13} style={{ verticalAlign: "-2px" }} /> {u.suspended ? "Unsuspend" : "Suspend"}
                        </button>
                        <button
                          className="admin-btn admin-btn--danger"
                          disabled={u.is_admin}
                          onClick={() => setConfirmDelete(u.username)}
                        >
                          <Trash2 size={13} style={{ verticalAlign: "-2px" }} /> Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan={7} style={{ color: "var(--text-muted)", textAlign: "center", padding: "var(--space-lg)" }}>
                      No users found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {selected && <UserDetailModal username={selected} onClose={() => setSelected(null)} />}
      {confirmDelete && (
        <DeleteConfirmModal
          username={confirmDelete}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={() => doDelete(confirmDelete)}
        />
      )}
    </>
  );
}

function UserDetailModal({ username, onClose }) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");
  const [content, setContent] = useState(null); // { kind, items }
  const [contentErr, setContentErr] = useState("");

  useEffect(() => {
    adminService
      .userDetail(username)
      .then((r) => setDetail(r.data))
      .catch((e) => setError(errMsg(e)));
  }, [username]);

  const openContent = async (kind) => {
    setContentErr("");
    try {
      const r = await adminService.userContent(username, kind);
      setContent({ kind, items: r.data.items || [] });
    } catch (e) {
      setContentErr(errMsg(e));
    }
  };

  return (
    <div className="admin-modal-backdrop" onClick={onClose}>
      <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
        <h3>{username}</h3>
        <ErrorBanner message={error} />
        {detail && (
          <>
            <dl className="admin-kv">
              <dt>Email</dt><dd>{detail.email || "—"}</dd>
              <dt>Name</dt><dd>{detail.name || "—"}</dd>
              <dt>Joined</dt><dd>{fmtDate(detail.created_at)}</dd>
              <dt>Sign-in</dt><dd>{detail.auth_provider}{detail.has_password ? " · has password" : ""}</dd>
              <dt>Status</dt><dd>{detail.is_admin ? "admin " : ""}{detail.suspended ? "suspended" : "active"}</dd>
            </dl>

            <h4 style={{ color: "var(--text-secondary)" }}>Records</h4>
            <div className="admin-actions">
              {Object.entries(detail.counts).map(([k, v]) => (
                <button key={k} className="admin-btn" onClick={() => openContent(k)}>
                  {k.replace(/_/g, " ")} ({v})
                </button>
              ))}
            </div>
            <div className="admin-content-note">
              Clicking a record type opens the user's actual content. This works only when
              <code> ADMIN_CONTENT_ACCESS</code> is enabled, and each view is audit-logged.
            </div>
            <ErrorBanner message={contentErr} />
            {content && (
              <>
                <h4 style={{ color: "var(--text-secondary)" }}>{content.kind.replace(/_/g, " ")} · {content.items.length}</h4>
                <pre className="admin-content-pre">{JSON.stringify(content.items, null, 2)}</pre>
              </>
            )}
          </>
        )}
        <div style={{ marginTop: "var(--space-lg)", textAlign: "right" }}>
          <button className="admin-btn" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

function DeleteConfirmModal({ username, onCancel, onConfirm }) {
  const [typed, setTyped] = useState("");
  return (
    <div className="admin-modal-backdrop" onClick={onCancel}>
      <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
        <h3>Delete {username}?</h3>
        <p style={{ color: "var(--text-secondary)" }}>
          This permanently deletes the account and <strong>every</strong> record it owns —
          profiles, readings, chats, journal, settings and tokens. This cannot be undone.
        </p>
        <p style={{ color: "var(--text-secondary)" }}>
          Type the username <strong>{username}</strong> to confirm:
        </p>
        <input
          className="admin-search"
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          placeholder={username}
        />
        <div style={{ marginTop: "var(--space-md)", textAlign: "right", display: "flex", gap: "var(--space-sm)", justifyContent: "flex-end" }}>
          <button className="admin-btn" onClick={onCancel}>Cancel</button>
          <button className="admin-btn admin-btn--danger" disabled={typed !== username} onClick={onConfirm}>
            <Trash2 size={13} style={{ verticalAlign: "-2px" }} /> Delete permanently
          </button>
        </div>
      </div>
    </div>
  );
}

function AuditTab() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    adminService
      .audit()
      .then((r) => setEntries(r.data.entries || []))
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <LoadingState />;
  return (
    <>
      <ErrorBanner message={error} />
      <button className="admin-btn" onClick={load} style={{ marginBottom: "var(--space-md)" }}>
        <RefreshCw size={13} style={{ verticalAlign: "-2px" }} /> Refresh
      </button>
      <Card accent="indigo">
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Admin</th>
                <th>Action</th>
                <th>Target</th>
                <th>Detail</th>
                <th>IP</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e._id}>
                  <td>{new Date(e.at).toLocaleString()}</td>
                  <td>{e.admin}</td>
                  <td><span className="admin-badge">{e.action}</span></td>
                  <td>{e.target || "—"}</td>
                  <td style={{ maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{e.detail || "—"}</td>
                  <td>{e.ip || "—"}</td>
                </tr>
              ))}
              {entries.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ color: "var(--text-muted)", textAlign: "center", padding: "var(--space-lg)" }}>
                    No admin activity recorded yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}

export default AdminPage;
