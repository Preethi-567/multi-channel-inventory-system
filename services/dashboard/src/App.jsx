import { useState, useEffect, useCallback } from "react"
import axios from "axios"
import { AlertTriangle, Package, TrendingDown, RefreshCw, CheckCircle } from "lucide-react"
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts"
import "./App.css"

const API = "/api"
const REFRESH_MS = 30000

// ── Helpers ──────────────────────────────────────────────────────────────────

function daysUntil(dateStr) {
  if (!dateStr) return null
  const diff = new Date(dateStr) - new Date()
  return Math.ceil(diff / (1000 * 60 * 60 * 24))
}

function severityColor(severity) {
  if (severity === "critical") return "#ef4444"
  if (severity === "warning") return "#f59e0b"
  return "#6b7280"
}

function stockColor(qty, reorder) {
  if (qty === 0) return "#ef4444"
  if (qty <= reorder) return "#f59e0b"
  return "#22c55e"
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div className="stat-card">
      <Icon size={20} color={color} />
      <div>
        <div className="stat-value" style={{ color }}>{value}</div>
        <div className="stat-label">{label}</div>
      </div>
    </div>
  )
}

function InventoryTable({ data }) {
  const rows = []
  for (const item of data) {
    for (const ch of item.channels) {
      rows.push({
        sku: item.sku,
        name: item.name,
        channel: ch.channel,
        qty: ch.quantity_on_hand,
        reserved: ch.quantity_reserved,
        available: ch.quantity_available,
        reorder: item.reorder_point,
        low: item.low_stock,
      })
    }
  }

  return (
    <div className="card">
      <h2 className="card-title"><Package size={16} /> Inventory</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>SKU</th>
              <th>Channel</th>
              <th>On Hand</th>
              <th>Available</th>
              <th>Reorder At</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className={r.qty === 0 ? "row-critical" : r.low ? "row-warning" : ""}>
                <td><span className="sku">{r.sku}</span></td>
                <td>{r.channel}</td>
                <td style={{ color: stockColor(r.qty, r.reorder), fontWeight: 600 }}>{r.qty}</td>
                <td>{r.available}</td>
                <td>{r.reorder}</td>
                <td>
                  <span className={`badge ${r.qty === 0 ? "badge-critical" : r.low ? "badge-warning" : "badge-ok"}`}>
                    {r.qty === 0 ? "STOCKOUT" : r.low ? "LOW" : "OK"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ForecastPanel({ data }) {
  const sorted = [...data].sort((a, b) => {
    if (!a.stockout_date) return 1
    if (!b.stockout_date) return -1
    return new Date(a.stockout_date) - new Date(b.stockout_date)
  })

  const chartData = sorted.slice(0, 8).map(f => ({
    sku: f.sku.split("-")[0],
    days: daysUntil(f.stockout_date) ?? 99,
    reorder: f.reorder_flag,
  }))

  return (
    <div className="card">
      <h2 className="card-title"><TrendingDown size={16} /> Forecast — Days Until Stockout</h2>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
          <XAxis dataKey="sku" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v) => [`${v} days`, "Until stockout"]} />
          <Bar dataKey="days" radius={[4, 4, 0, 0]}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.reorder ? "#ef4444" : "#22c55e"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <div className="forecast-list">
        {sorted.map((f, i) => {
          const days = daysUntil(f.stockout_date)
          return (
            <div key={i} className={`forecast-row ${f.reorder_flag ? "forecast-urgent" : ""}`}>
              <div>
                <span className="sku">{f.sku}</span>
                <span className="mape"> MAPE {f.model_mape?.toFixed(0)}%</span>
              </div>
              <div className="forecast-right">
                {days !== null ? (
                  <span style={{ color: days <= 3 ? "#ef4444" : days <= 7 ? "#f59e0b" : "#22c55e" }}>
                    {days <= 0 ? "STOCKOUT" : `${days}d`}
                  </span>
                ) : <span className="ok">Safe</span>}
                {f.reorder_flag && <span className="reorder-badge">REORDER {f.reorder_qty}</span>}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function AlertsPanel({ data }) {
  const sorted = [...data].sort((a, b) => {
    const order = { critical: 0, warning: 1, info: 2 }
    return (order[a.severity] ?? 2) - (order[b.severity] ?? 2)
  })

  return (
    <div className="card">
      <h2 className="card-title"><AlertTriangle size={16} /> Active Alerts</h2>
      {sorted.length === 0 ? (
        <div className="no-alerts"><CheckCircle size={16} color="#22c55e" /> All clear</div>
      ) : (
        <div className="alerts-list">
          {sorted.map((a, i) => (
            <div key={i} className="alert-row" style={{ borderLeft: `3px solid ${severityColor(a.severity)}` }}>
              <div className="alert-header">
                <span className="sku">{a.sku}</span>
                <span className="alert-channel">{a.channel}</span>
                <span className={`badge badge-${a.severity === "critical" ? "critical" : "warning"}`}>
                  {a.severity.toUpperCase()}
                </span>
              </div>
              <div className="alert-msg">{a.message}</div>
              <div className="alert-time">{new Date(a.created_at).toLocaleString()}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main App ──────────────────────────────────────────────────────────────────

export default function App() {
  const [inventory, setInventory] = useState([])
  const [forecasts, setForecasts] = useState([])
  const [alerts, setAlerts] = useState([])
  const [lastRefresh, setLastRefresh] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchAll = useCallback(async () => {
    try {
      const [inv, fcast, alrt] = await Promise.all([
        axios.get(`${API}/inventory/summary`),
        axios.get(`${API}/inventory/forecasts`),
        axios.get(`${API}/inventory/alerts`),
      ])
      setInventory(inv.data.data || [])
      setForecasts(fcast.data.forecasts || [])
      setAlerts(alrt.data.alerts || [])
      setLastRefresh(new Date())
    } catch (e) {
      console.error("Fetch error:", e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
    const id = setInterval(fetchAll, REFRESH_MS)
    return () => clearInterval(id)
  }, [fetchAll])

  const criticalCount = alerts.filter(a => a.severity === "critical").length
  const lowStockCount = inventory.filter(i => i.low_stock).length
  const reorderCount = forecasts.filter(f => f.reorder_flag).length

  if (loading) return <div className="loading">Loading...</div>

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <h1>Inventory Brain</h1>
          <span className="subtitle">Multi-Channel Platform</span>
        </div>
        <div className="header-right">
          <div className="stat-row">
            <StatCard icon={AlertTriangle} label="Critical Alerts" value={criticalCount} color="#ef4444" />
            <StatCard icon={Package} label="Low Stock SKUs" value={lowStockCount} color="#f59e0b" />
            <StatCard icon={TrendingDown} label="Reorder Needed" value={reorderCount} color="#8b5cf6" />
          </div>
          <button className="refresh-btn" onClick={fetchAll}>
            <RefreshCw size={14} /> Refresh
          </button>
          {lastRefresh && <span className="last-refresh">Updated {lastRefresh.toLocaleTimeString()}</span>}
        </div>
      </header>

      <main className="main">
        <div className="left-col">
          <InventoryTable data={inventory} />
        </div>
        <div className="right-col">
          <ForecastPanel data={forecasts} />
          <AlertsPanel data={alerts} />
        </div>
      </main>
    </div>
  )
}