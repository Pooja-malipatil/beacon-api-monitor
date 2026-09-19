import { useState, useEffect, useCallback } from "react";
import { createApiClient } from "./api";

export default function Dashboard({ token, onLogout, lastEvent }) {
  const api = createApiClient(token);

  const [summary, setSummary] = useState(null);
  const [services, setServices] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [editingService, setEditingService] = useState(null);
  const [formError, setFormError] = useState("");

  const loadAll = useCallback(async () => {
    try {
      const [dashRes, servicesRes, incidentsRes, alertsRes] = await Promise.all([
        api.get("/dashboard"),
        api.get("/services"),
        api.get("/incidents"),
        api.get("/alerts"),
      ]);
      setSummary(dashRes.data);
      setServices(servicesRes.data);
      setIncidents(incidentsRes.data.slice(0, 5));
      setAlerts(alertsRes.data);
    } catch (err) {
      console.error("Failed to load dashboard data", err);
    }
  }, [token]);

  // Initial load
  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Re-load the moment the WebSocket tells us something changed
  useEffect(() => {
    if (lastEvent) loadAll();
  }, [lastEvent, loadAll]);

  async function handleDelete(id) {
    if (!confirm("Delete this service?")) return;
    await api.delete(`/services/${id}`);
    loadAll();
  }

  async function handleToggleActive(service) {
    await api.put(`/services/${service.id}`, { is_active: !service.is_active });
    loadAll();
  }

  function openEditForm(service) {
    setEditingService(service);
    setShowForm(true);
  }

  function openAddForm() {
    setEditingService(null);
    setShowForm(true);
  }

  return (
    <div style={styles.page}>
      <header style={styles.header}>
        <h1 style={styles.logo}>Beacon</h1>
        <button style={styles.logoutBtn} onClick={onLogout}>Log Out</button>
      </header>

      {summary && (
        <div style={styles.summaryGrid}>
          <SummaryCard label="Total Services" value={summary.total_services} color="#c17a4f" />
          <SummaryCard label="Healthy" value={summary.healthy} color="#22c55e" />
          <SummaryCard label="Degraded" value={summary.degraded} color="#f59e0b" />
          <SummaryCard label="Down" value={summary.down} color="#ef4444" />
          <SummaryCard label="Active Incidents" value={summary.active_incidents} color="#ef4444" />
          <SummaryCard
            label="Avg Response"
            value={summary.avg_response_time_ms ? `${Math.round(summary.avg_response_time_ms)}ms` : "—"}
          />
          <SummaryCard
            label="Uptime (24h)"
            value={summary.overall_uptime_24h != null ? `${summary.overall_uptime_24h}%` : "—"}
          />
        </div>
      )}

      {alerts.length > 0 && (
        <div style={styles.alertBanner}>
          {alerts.map((a, i) => (
            <div key={i} style={styles.alertItem}>⚠ {a.message}</div>
          ))}
        </div>
      )}

      <div style={styles.sectionHeader}>
        <h2 style={styles.sectionTitle}>Services</h2>
        <button style={styles.addBtn} onClick={openAddForm}>+ Add Service</button>
      </div>

      <div style={styles.serviceList}>
        {services.map((s) => (
          <ServiceRow
            key={s.id}
            service={s}
            onEdit={() => openEditForm(s)}
            onDelete={() => handleDelete(s.id)}
            onToggle={() => handleToggleActive(s)}
          />
        ))}
        {services.length === 0 && <p style={styles.emptyText}>No services yet — add one to get started.</p>}
      </div>

      <h2 style={styles.sectionTitle}>Recent Incidents</h2>
      <div style={styles.incidentList}>
        {incidents.map((inc) => (
          <div key={inc.id} style={styles.incidentRow}>
            <span style={{
              ...styles.badge,
              background: inc.status === "open" ? "#ef4444" : "#22c55e",
            }}>
              {inc.status}
            </span>
            <span style={styles.incidentReason}>{inc.reason}</span>
            <span style={styles.incidentTime}>
              {new Date(inc.started_at).toLocaleString()}
            </span>
          </div>
        ))}
        {incidents.length === 0 && <p style={styles.emptyText}>No incidents recorded.</p>}
      </div>

      {showForm && (
        <ServiceFormModal
          api={api}
          existing={editingService}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); loadAll(); }}
          error={formError}
          setError={setFormError}
        />
      )}
    </div>
  );
}

function SummaryCard({ label, value, color }) {
  return (
    <div style={styles.summaryCard}>
      <div style={{ ...styles.summaryValue, color: color || "#3a3129" }}>{value}</div>
      <div style={styles.summaryLabel}>{label}</div>
    </div>
  );
}
function ServiceRow({ service, onEdit, onDelete, onToggle }) {
  const statusColors = { healthy: "#22c55e", degraded: "#f59e0b", down: "#ef4444", pending: "#a89a89" };
  return (
    <div style={styles.serviceRow}>
      <span style={{ ...styles.statusDot, background: statusColors[service.status] || "#a89a89" }} />
      <div style={styles.serviceInfo}>
        <div style={styles.serviceName}>{service.name}</div>
        <div style={styles.serviceUrl}>{service.url}</div>
      </div>
      <div style={styles.serviceMeta}>
        <span style={styles.serviceStatus}>{service.status}</span>
        <span style={styles.serviceMetaText}>every {service.interval_seconds}s</span>
      </div>
      <div style={styles.serviceActions}>
        <button style={styles.smallBtn} onClick={onToggle}>{service.is_active ? "Pause" : "Resume"}</button>
        <button style={styles.smallBtn} onClick={onEdit}>Edit</button>
        <button style={{ ...styles.smallBtn, color: "#c0392b" }} onClick={onDelete}>Delete</button>
      </div>
    </div>
  );
}

function ServiceFormModal({ api, existing, onClose, onSaved, error, setError }) {
  const [form, setForm] = useState({
    name: existing?.name || "",
    url: existing?.url || "",
    method: existing?.method || "GET",
    expected_status: existing?.expected_status ?? 200,
    interval_seconds: existing?.interval_seconds ?? 60,
    timeout_seconds: existing?.timeout_seconds ?? 5,
  });

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      if (existing) {
        await api.put(`/services/${existing.id}`, form);
      } else {
        await api.post("/services", form);
      }
      onSaved();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to save service");
    }
  }

  return (
    <div style={styles.modalOverlay}>
      <div style={styles.modal}>
        <h3 style={{ color: "#3a3129", marginTop: 0 }}>{existing ? "Edit Service" : "Add Service"}</h3>
        <form onSubmit={handleSubmit} style={styles.form}>

          <input
            style={styles.input}
            placeholder="e.g. Payment API"
            value={form.name}
            onChange={(e) => update("name", e.target.value)}
            required
          />
          <p style={styles.fieldHint}>A friendly name so you recognize this service later.</p>

          <input
            style={styles.input}
            placeholder="e.g. https://api.example.com/health"
            value={form.url}
            onChange={(e) => update("url", e.target.value)}
            required
          />
          <p style={styles.fieldHint}>The exact web address Beacon should check.</p>

          <select style={styles.input} value={form.method} onChange={(e) => update("method", e.target.value)}>
            <option value="GET">GET</option>
            <option value="POST">POST</option>
            <option value="HEAD">HEAD</option>
          </select>
          <p style={styles.fieldHint}>The type of request to send — GET is correct for almost all cases.</p>

          <input
            style={styles.input}
            type="number"
            placeholder="e.g. 200"
            value={form.expected_status}
            onChange={(e) => update("expected_status", parseInt(e.target.value))}
          />
          <p style={styles.fieldHint}>
            The status code that means "working." 200 is the standard success code for most APIs.
          </p>

          <input
            style={styles.input}
            type="number"
            placeholder="e.g. 60"
            value={form.interval_seconds}
            onChange={(e) => update("interval_seconds", parseInt(e.target.value))}
          />
          <p style={styles.fieldHint}>
            How often (in seconds) Beacon checks this service. 60 means once every minute.
          </p>

          <input
            style={styles.input}
            type="number"
            placeholder="e.g. 5"
            value={form.timeout_seconds}
            onChange={(e) => update("timeout_seconds", parseInt(e.target.value))}
          />
          <p style={styles.fieldHint}>
            How long (in seconds) to wait for a response before treating it as a failure.
          </p>

          {error && <p style={styles.error}>{error}</p>}
          <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
            <button style={styles.button} type="submit">Save</button>
            <button style={{ ...styles.button, background: "#e0d5c7", color: "#3a3129" }} type="button" onClick={onClose}>Cancel</button>
          </div>
        </form>
      </div>
    </div>
  );
}

const styles = {
  page: { minHeight: "100vh", background: "#faf6f1", fontFamily: "system-ui, sans-serif", padding: "2rem" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" },
  logo: { color: "#3a3129", margin: 0 },
  logoutBtn: { background: "#ffffff", color: "#3a3129", border: "1px solid #e0d5c7", padding: "0.5rem 1rem", borderRadius: "8px", cursor: "pointer" },
  summaryGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "1rem", marginBottom: "1.5rem" },
  summaryCard: { background: "#ffffff", borderRadius: "10px", padding: "1rem", textAlign: "center", border: "1px solid #eee3d8" },
  summaryValue: { fontSize: "1.8rem", fontWeight: 700 },
  summaryLabel: { color: "#8a7c6d", fontSize: "0.8rem", marginTop: "0.25rem" },
  alertBanner: { background: "#fdecea", border: "1px solid #f5c6bd", borderRadius: "8px", padding: "0.75rem 1rem", marginBottom: "1.5rem" },
  alertItem: { color: "#a13d2b", fontSize: "0.9rem", padding: "0.2rem 0" },
  sectionHeader: { display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "1.5rem" },
  sectionTitle: { color: "#3a3129", fontSize: "1.1rem" },
  addBtn: { background: "#c17a4f", color: "white", border: "none", padding: "0.5rem 1rem", borderRadius: "8px", cursor: "pointer", fontWeight: 600 },
  serviceList: { display: "flex", flexDirection: "column", gap: "0.5rem", marginTop: "0.75rem" },
  serviceRow: { display: "flex", alignItems: "center", gap: "1rem", background: "#ffffff", borderRadius: "10px", padding: "0.9rem 1.2rem", border: "1px solid #eee3d8" },
  statusDot: { width: "10px", height: "10px", borderRadius: "50%", flexShrink: 0 },
  serviceInfo: { flex: 1 },
  serviceName: { color: "#3a3129", fontWeight: 600 },
  serviceUrl: { color: "#8a7c6d", fontSize: "0.8rem" },
  serviceMeta: { display: "flex", flexDirection: "column", alignItems: "flex-end", marginRight: "1rem" },
  serviceStatus: { color: "#3a3129", fontSize: "0.85rem", textTransform: "capitalize" },
  serviceMetaText: { color: "#a89a89", fontSize: "0.75rem" },
  serviceActions: { display: "flex", gap: "0.5rem" },
  smallBtn: { background: "#f3ece3", color: "#3a3129", border: "none", padding: "0.4rem 0.7rem", borderRadius: "6px", cursor: "pointer", fontSize: "0.8rem" },
  incidentList: { display: "flex", flexDirection: "column", gap: "0.5rem", marginTop: "0.75rem", marginBottom: "2rem" },
  incidentRow: { display: "flex", alignItems: "center", gap: "0.75rem", background: "#ffffff", borderRadius: "8px", padding: "0.6rem 1rem", border: "1px solid #eee3d8" },
  badge: { color: "white", fontSize: "0.7rem", padding: "0.2rem 0.5rem", borderRadius: "4px", textTransform: "uppercase", fontWeight: 700 },
  incidentReason: { color: "#5c5142", fontSize: "0.85rem", flex: 1 },
  incidentTime: { color: "#a89a89", fontSize: "0.75rem" },
  emptyText: { color: "#a89a89", fontSize: "0.85rem" },
  modalOverlay: { position: "fixed", inset: 0, background: "rgba(58,49,41,0.4)", display: "flex", alignItems: "center", justifyContent: "center" },
  modal: { background: "#ffffff", padding: "2rem", borderRadius: "12px", width: "380px", border: "1px solid #eee3d8" },
  form: { display: "flex", flexDirection: "column", gap: "0.6rem" },
  input: { padding: "0.6rem", borderRadius: "8px", border: "1px solid #e0d5c7", background: "#fffdfb", color: "#3a3129" },
  button: { padding: "0.6rem", borderRadius: "8px", border: "none", background: "#c17a4f", color: "white", fontWeight: 600, cursor: "pointer", flex: 1 },
  error: { color: "#c0392b", fontSize: "0.85rem", margin: 0 },
  fieldHint: { color: "#a89a89", fontSize: "0.75rem", margin: "-0.3rem 0 0.2rem 0.1rem" },
};