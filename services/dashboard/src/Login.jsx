import { useState } from "react"
import axios from "axios"

const API = "/api"

export default function Login({ onLogin }) {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError]       = useState("")
  const [loading, setLoading]   = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError("")

    try {
      const res = await axios.post(`${API}/auth/login`, { username, password })
      const { access_token, username: user } = res.data
      localStorage.setItem("token", access_token)
      localStorage.setItem("username", user)
      onLogin(user)
    } catch (err) {
      setError("Invalid username or password")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "center",
      minHeight: "100vh", background: "#0f172a",
    }}>
      <div style={{
        background: "#1e293b", border: "1px solid #334155",
        borderRadius: 12, padding: "40px 48px", width: 380,
        boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
      }}>
        {/* Logo area */}
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{ fontSize: 36, marginBottom: 8 }}>📦</div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: "#f8fafc", margin: 0 }}>
            Inventory Brain
          </h1>
          <p style={{ fontSize: 12, color: "#64748b", margin: "6px 0 0" }}>
            Multi-Channel Platform
          </p>
        </div>

        {/* Form */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label style={{ fontSize: 12, color: "#94a3b8", display: "block", marginBottom: 6 }}>
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="admin"
              style={{
                width: "100%", padding: "10px 14px",
                background: "#0f172a", border: "1px solid #334155",
                borderRadius: 8, color: "#e2e8f0", fontSize: 14,
                outline: "none", boxSizing: "border-box",
              }}
              onKeyDown={e => e.key === "Enter" && handleSubmit(e)}
            />
          </div>

          <div>
            <label style={{ fontSize: 12, color: "#94a3b8", display: "block", marginBottom: 6 }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              style={{
                width: "100%", padding: "10px 14px",
                background: "#0f172a", border: "1px solid #334155",
                borderRadius: 8, color: "#e2e8f0", fontSize: 14,
                outline: "none", boxSizing: "border-box",
              }}
              onKeyDown={e => e.key === "Enter" && handleSubmit(e)}
            />
          </div>

          {error && (
            <div style={{
              background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)",
              borderRadius: 6, padding: "8px 12px",
              fontSize: 12, color: "#ef4444",
            }}>
              {error}
            </div>
          )}

          <button
            onClick={handleSubmit}
            disabled={loading || !username || !password}
            style={{
              background: loading ? "#334155" : "#8b5cf6",
              border: "none", borderRadius: 8,
              color: "#fff", fontSize: 14, fontWeight: 600,
              padding: "11px 0", cursor: loading ? "not-allowed" : "pointer",
              marginTop: 4, transition: "background 0.15s",
            }}
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </div>

        {/* Hint */}
        <p style={{ fontSize: 11, color: "#475569", textAlign: "center", marginTop: 24, marginBottom: 0 }}>
          admin / inventory2026
        </p>
      </div>
    </div>
  )
}