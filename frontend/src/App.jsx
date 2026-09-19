import { useState, useEffect, useRef } from "react";
import { createApiClient, API_BASE_URL } from "./api";
import Dashboard from "./Dashboard";

export default function App() {
  const [token, setToken] = useState(null);
  const [mode, setMode] = useState("login"); // "login" or "register"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const wsRef = useRef(null);
  const [lastEvent, setLastEvent] = useState(null);

  // Connect the WebSocket once we have a token, disconnect on logout
  useEffect(() => {
    if (!token) return;

    const wsUrl = API_BASE_URL.replace("http", "ws") + `/ws?token=${token}`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setLastEvent(data); // Dashboard watches this to know when to refresh
    };

    wsRef.current = ws;
    return () => ws.close();
  }, [token]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    const api = createApiClient(null);
    try {
      if (mode === "register") {
        await api.post("/auth/register", { email, password });
        setMode("login");
        setError("Registered! Now log in.");
        return;
      }
      const res = await api.post("/auth/login", { email, password });
      setToken(res.data.access_token);
    } catch (err) {
      setError(err.response?.data?.detail || "Something went wrong");
    }
  }

  function handleLogout() {
    setToken(null);
    setEmail("");
    setPassword("");
  }

  if (token) {
    return <Dashboard token={token} onLogout={handleLogout} lastEvent={lastEvent} />;
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <h1 style={styles.title}>Beacon</h1>
        <p style={styles.subtitle}>API Reliability & Incident Monitoring</p>

        <form onSubmit={handleSubmit} style={styles.form}>
          <input
            style={styles.input}
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <input
            style={styles.input}
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && <p style={styles.error}>{error}</p>}
          <button style={styles.button} type="submit">
            {mode === "login" ? "Log In" : "Register"}
          </button>
        </form>

        <p style={styles.switchText}>
          {mode === "login" ? "No account?" : "Already have an account?"}{" "}
          <span
            style={styles.switchLink}
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError("");
            }}
          >
            {mode === "login" ? "Register" : "Log In"}
          </span>
        </p>
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "#faf6f1",
    fontFamily: "system-ui, sans-serif",
  },
  card: {
    background: "#ffffff",
    padding: "2.5rem",
    borderRadius: "12px",
    width: "340px",
    boxShadow: "0 10px 30px rgba(0,0,0,0.08)",
    border: "1px solid #eee3d8",
  },
  title: { color: "#3a3129", margin: 0, fontSize: "1.8rem" },
  subtitle: { color: "#8a7c6d", marginTop: "0.25rem", marginBottom: "1.5rem", fontSize: "0.9rem" },
  form: { display: "flex", flexDirection: "column", gap: "0.75rem" },
  input: {
    padding: "0.7rem",
    borderRadius: "8px",
    border: "1px solid #e0d5c7",
    background: "#fffdfb",
    color: "#3a3129",
    fontSize: "0.95rem",
  },
  button: {
    padding: "0.7rem",
    borderRadius: "8px",
    border: "none",
    background: "#c17a4f",
    color: "white",
    fontWeight: 600,
    cursor: "pointer",
    marginTop: "0.5rem",
  },
  error: { color: "#c0392b", fontSize: "0.85rem", margin: 0 },
  switchText: { color: "#8a7c6d", fontSize: "0.85rem", marginTop: "1.2rem", textAlign: "center" },
  switchLink: { color: "#c17a4f", cursor: "pointer", fontWeight: 600 },
};