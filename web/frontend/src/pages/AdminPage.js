import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  ShieldAlert,
  Users,
  Activity,
  ScrollText,
  Trash2,
  Ban,
  Eye,
  RefreshCw,
  Waves,
  SlidersHorizontal,
  Save,
  RotateCcw,
} from "lucide-react";
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
    return new Date(v).toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return String(v);
  }
};

const fmtDateTime = (v) => {
  if (!v) return "—";
  try {
    return new Date(v).toLocaleString();
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
      { key: "activity", label: "Activity", icon: <Waves size={15} /> },
      { key: "audit", label: "Audit log", icon: <ScrollText size={15} /> },
      { key: "settings", label: "Settings", icon: <SlidersHorizontal size={15} /> },
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
        {tab === "activity" && <ActivityTab />}
        {tab === "audit" && <AuditTab />}
        {tab === "settings" && <SettingsTab />}
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
            <strong>Content access is ON.</strong> You can open individual users' private readings,
            chats and journal entries. Every such view is recorded in the audit log.
          </>
        ) : (
          <>
            <strong>Content access is OFF.</strong> The console shows metadata and counts only. To
            inspect a user's actual content, set <code>ADMIN_CONTENT_ACCESS=true</code> and redeploy
            — a deliberate "break glass" step.
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
                      {u.suspended && (
                        <span className="admin-badge admin-badge--suspended">suspended</span>
                      )}
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
                          <Ban size={13} style={{ verticalAlign: "-2px" }} />{" "}
                          {u.suspended ? "Unsuspend" : "Suspend"}
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
                    <td
                      colSpan={7}
                      style={{
                        color: "var(--text-muted)",
                        textAlign: "center",
                        padding: "var(--space-lg)",
                      }}
                    >
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
              <dt>Email</dt>
              <dd>{detail.email || "—"}</dd>
              <dt>Name</dt>
              <dd>{detail.name || "—"}</dd>
              <dt>Joined</dt>
              <dd>{fmtDate(detail.created_at)}</dd>
              <dt>Sign-in</dt>
              <dd>
                {detail.auth_provider}
                {detail.has_password ? " · has password" : ""}
              </dd>
              <dt>Status</dt>
              <dd>
                {detail.is_admin ? "admin " : ""}
                {detail.suspended ? "suspended" : "active"}
              </dd>
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
                <h4 style={{ color: "var(--text-secondary)" }}>
                  {content.kind.replace(/_/g, " ")} · {content.items.length}
                </h4>
                <pre className="admin-content-pre">{JSON.stringify(content.items, null, 2)}</pre>
              </>
            )}
          </>
        )}
        <div style={{ marginTop: "var(--space-lg)", textAlign: "right" }}>
          <button className="admin-btn" onClick={onClose}>
            Close
          </button>
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
          This permanently deletes the account and <strong>every</strong> record it owns — profiles,
          readings, chats, journal, settings and tokens. This cannot be undone.
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
        <div
          style={{
            marginTop: "var(--space-md)",
            textAlign: "right",
            display: "flex",
            gap: "var(--space-sm)",
            justifyContent: "flex-end",
          }}
        >
          <button className="admin-btn" onClick={onCancel}>
            Cancel
          </button>
          <button
            className="admin-btn admin-btn--danger"
            disabled={typed !== username}
            onClick={onConfirm}
          >
            <Trash2 size={13} style={{ verticalAlign: "-2px" }} /> Delete permanently
          </button>
        </div>
      </div>
    </div>
  );
}

// How each activity kind is labelled and coloured. The feed is derived from the
// collections themselves, so this list mirrors admin.py's _ACTIVITY_SOURCES.
const ACTIVITY_KINDS = [
  { key: "signup", label: "Signups" },
  { key: "ai", label: "AI readings & chats" },
  { key: "digest", label: "Digests" },
  { key: "journal", label: "Journal" },
  { key: "quiz", label: "Quiz" },
  { key: "share", label: "Shares" },
  { key: "profile", label: "Profiles" },
  { key: "audit", label: "Audit events" },
];

/**
 * What the deployment has actually been doing. Distinct from the audit log: this
 * is derived on read from the data itself, so it shows every signup and every
 * reading ever made — including the long stretch before event logging existed.
 */
function ActivityTab() {
  const [entries, setEntries] = useState([]);
  const [kinds, setKinds] = useState([]);
  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    adminService
      .activity({ kinds: kinds.join(","), username })
      .then((r) => setEntries(r.data.entries || []))
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, [kinds, username]);

  useEffect(() => {
    load();
  }, [load]);

  const toggleKind = (key) =>
    setKinds((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));

  return (
    <>
      <ErrorBanner message={error} />
      <div className="admin-filters">
        <input
          className="admin-input"
          placeholder="Filter by username…"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <button className="admin-btn" onClick={load}>
          <RefreshCw size={13} style={{ verticalAlign: "-2px" }} /> Refresh
        </button>
      </div>
      <div className="admin-chips">
        {ACTIVITY_KINDS.map((k) => (
          <button
            key={k.key}
            className={`admin-chip${kinds.includes(k.key) ? " is-active" : ""}`}
            onClick={() => toggleKind(k.key)}
          >
            {k.label}
          </button>
        ))}
        {kinds.length > 0 && (
          <button className="admin-chip" onClick={() => setKinds([])}>
            Clear
          </button>
        )}
      </div>

      {loading ? (
        <LoadingState />
      ) : (
        <Card accent="indigo">
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Kind</th>
                  <th>User</th>
                  <th>What</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e, i) => (
                  <tr key={`${e.at}-${i}`}>
                    <td>{fmtDateTime(e.at)}</td>
                    <td>
                      <span className="admin-badge">{e.kind}</span>
                    </td>
                    <td>{e.user || "—"}</td>
                    <td className="admin-cell-wrap">{e.summary || "—"}</td>
                  </tr>
                ))}
                {entries.length === 0 && (
                  <tr>
                    <td colSpan={4} className="admin-empty">
                      Nothing recorded for this filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  );
}

/**
 * The audit log — moderation actions and security events. Deliberately NOT an
 * activity feed: a quiet log here means nobody suspended anyone and nobody failed
 * a login, which is the good outcome. The empty state says so, because a blank
 * table reads as a broken feature.
 */
function AuditTab() {
  const [entries, setEntries] = useState([]);
  const [summary, setSummary] = useState(null);
  const [actions, setActions] = useState([]);
  const [filters, setFilters] = useState({ category: "", action: "", actor: "", target: "" });
  const [sinceDays, setSinceDays] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    adminService
      .audit({ ...filters, since_days: sinceDays })
      .then((r) => {
        setEntries(r.data.entries || []);
        setSummary(r.data.summary || null);
        setActions(r.data.actions || []);
      })
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, [filters, sinceDays]);

  useEffect(() => {
    load();
  }, [load]);

  const set = (key) => (e) => setFilters((f) => ({ ...f, [key]: e.target.value }));
  const filtered = Object.values(filters).some(Boolean) || sinceDays > 0;

  return (
    <>
      <ErrorBanner message={error} />

      <div className="admin-content-note">
        This log records <strong>events</strong>: moderation actions taken in this console, and
        security events (sign-ins, failed sign-ins, password resets, API tokens). It is not a
        record of ordinary use — for signups, readings and digests see the{" "}
        <strong>Activity</strong> tab, which is derived from the data itself and covers everything
        that ever happened.
        {summary ? (
          <>
            {" "}
            Holding <strong>{summary.total}</strong> rows ({summary.security} security,{" "}
            {summary.moderation} moderation); kept for {summary.retention_days} days
            {summary.newest_at ? `, newest ${fmtDateTime(summary.newest_at)}` : ""}.
          </>
        ) : null}
      </div>

      <div className="admin-filters">
        <select className="admin-input" value={filters.category} onChange={set("category")}>
          <option value="">All categories</option>
          <option value="security">Security</option>
          <option value="moderation">Moderation</option>
        </select>
        <select className="admin-input" value={filters.action} onChange={set("action")}>
          <option value="">All actions</option>
          {[
            ...actions,
            "view_content",
            "suspend",
            "unsuspend",
            "delete_user",
            "update_config",
          ].map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        <input
          className="admin-input"
          placeholder="Actor…"
          value={filters.actor}
          onChange={set("actor")}
        />
        <input
          className="admin-input"
          placeholder="Target…"
          value={filters.target}
          onChange={set("target")}
        />
        <select
          className="admin-input"
          value={sinceDays}
          onChange={(e) => setSinceDays(Number(e.target.value))}
        >
          <option value={0}>Any time</option>
          <option value={1}>Last 24 hours</option>
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
        </select>
        <button className="admin-btn" onClick={load}>
          <RefreshCw size={13} style={{ verticalAlign: "-2px" }} /> Refresh
        </button>
      </div>

      {loading ? (
        <LoadingState />
      ) : (
        <Card accent="indigo">
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Category</th>
                  <th>Actor</th>
                  <th>Action</th>
                  <th>Target</th>
                  <th>Detail</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => (
                  <tr key={e._id}>
                    <td>{fmtDateTime(e.at)}</td>
                    <td>
                      <span
                        className={`admin-badge${
                          e.category === "security" ? " admin-badge--security" : ""
                        }`}
                      >
                        {e.category || "moderation"}
                      </span>
                    </td>
                    <td>{e.admin || "—"}</td>
                    <td>{e.action}</td>
                    <td>{e.target || "—"}</td>
                    <td className="admin-cell-clip">{e.detail || "—"}</td>
                    <td>{e.ip || "—"}</td>
                  </tr>
                ))}
                {entries.length === 0 && (
                  <tr>
                    <td colSpan={7} className="admin-empty">
                      {filtered
                        ? "No events match these filters."
                        : "No events recorded yet — nothing has been moderated and no sign-in events have been logged since this deployment started recording them."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  );
}

// The runtime knobs, in the units an operator actually thinks in. Each carries
// the "why you'd change this" so the console explains itself.
const CONFIG_FIELDS = [
  {
    key: "digest_scheduler_enabled",
    label: "Digest scheduler",
    type: "bool",
    help: "When off, no scheduled digest is delivered — the manual 'send now' still works.",
  },
  {
    key: "digest_scheduler_interval_minutes",
    label: "Check every (minutes)",
    type: "int",
    min: 1,
    max: 59,
    help: "How often the scheduler wakes and looks for due digests. Must stay under 60 so every target hour is caught. A digest set for 07:00 can therefore arrive up to this many minutes late.",
  },
  {
    key: "digest_ai_max_delay_minutes",
    label: "Wait up to (minutes) for the AI",
    type: "int",
    min: 0,
    max: 720,
    help: "How late a digest may be while the model is busy with another workload. Past this, it goes out with its rule-based highlights and no narrative — late beats never. 0 sends immediately without waiting.",
  },
];

/**
 * Runtime settings. These are stored in Mongo and re-read by the scheduler each
 * tick, so a change takes effect within one cycle — no redeploy, no pod shell.
 * Env vars remain the defaults, and "Reset" genuinely returns a field to its
 * deployed value rather than writing the default back as an override.
 */
function SettingsTab() {
  const [cfg, setCfg] = useState(null);
  const [draft, setDraft] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  const apply = useCallback((data) => {
    setCfg(data);
    setDraft(data.values || {});
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    adminService
      .getConfig()
      .then((r) => apply(r.data))
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, [apply]);

  useEffect(() => {
    load();
  }, [load]);

  const save = async (updates) => {
    setSaving(true);
    setError("");
    setSaved("");
    try {
      const { data } = await adminService.setConfig(updates);
      apply(data);
      setSaved("Saved — the scheduler picks this up on its next tick.");
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingState />;
  if (!cfg) return <ErrorBanner message={error} />;

  const dirty = CONFIG_FIELDS.some((f) => draft[f.key] !== cfg.values[f.key]);

  return (
    <>
      <ErrorBanner message={error} />
      {saved && <div className="admin-content-note admin-note--ok">{saved}</div>}

      <div className="admin-content-note">
        Stored in the database and re-read by the scheduler every tick, so changes take effect
        without a redeploy. The environment variables remain the defaults — <strong>Reset</strong>{" "}
        clears an override and returns a setting to its deployed value.
      </div>

      <Card title="Digest delivery" accent="indigo">
        {CONFIG_FIELDS.map((f) => {
          const overridden = (cfg.overridden || []).includes(f.key);
          return (
            <div key={f.key} className="admin-setting">
              <div className="admin-setting__main">
                <label className="admin-setting__label" htmlFor={`cfg-${f.key}`}>
                  {f.label}
                  {overridden && <span className="admin-badge">overridden</span>}
                </label>
                <p className="admin-setting__help">{f.help}</p>
                <p className="admin-setting__help">
                  Deployed default: <code>{String(cfg.defaults[f.key])}</code>
                </p>
              </div>
              <div className="admin-setting__control">
                {f.type === "bool" ? (
                  <input
                    id={`cfg-${f.key}`}
                    type="checkbox"
                    checked={!!draft[f.key]}
                    onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.checked }))}
                  />
                ) : (
                  <input
                    id={`cfg-${f.key}`}
                    className="admin-input admin-input--num"
                    type="number"
                    min={f.min}
                    max={f.max}
                    value={draft[f.key] ?? ""}
                    onChange={(e) => setDraft((d) => ({ ...d, [f.key]: Number(e.target.value) }))}
                  />
                )}
                {overridden && (
                  <button
                    className="admin-btn"
                    disabled={saving}
                    onClick={() => save({ clear: [f.key] })}
                    title="Clear the override and use the deployed default"
                  >
                    <RotateCcw size={13} style={{ verticalAlign: "-2px" }} /> Reset
                  </button>
                )}
              </div>
            </div>
          );
        })}

        <div className="admin-setting__footer">
          <span className="admin-setting__help">
            At the current interval, waiting {draft.digest_ai_max_delay_minutes ?? 0} minutes means
            up to <strong>{cfg.max_deferrals}</strong> retries before a digest is sent without its
            narrative.
          </span>
          <button
            className="admin-btn admin-btn--primary"
            disabled={saving || !dirty}
            onClick={() => save(draft)}
          >
            <Save size={13} style={{ verticalAlign: "-2px" }} /> Save changes
          </button>
        </div>
      </Card>
    </>
  );
}

export default AdminPage;
