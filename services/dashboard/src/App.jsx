import { useState, useEffect, useCallback } from "react"
import axios from "axios"
import {
  AlertTriangle, Package, TrendingDown, RefreshCw,
  CheckCircle, BarChart2, TrendingUp
} from "lucide-react"
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell
} from "recharts"
import "./App.css"

const API = "/api"
const REFRESH_MS = 30000

// ── Helpers ───────────────────────────────────────────────────────────────────

function daysUntil(dateStr) {
  if (!dateStr) return null
  const diff = new Date(dateStr) - new Date()
  return Math.ceil(diff / (1000 * 60 * 60 * 24))
}

function severityColor(s) {
  if (s === "critical") return "#ef4444"
  if (s === "warning")  return "#f59e0b"
  return "#6b7280"
}

function stockColor(qty, reorder) {
  if (qty === 0)        return "#ef4444"
  if (qty <= reorder)   return "#f59e0b"
  return "#22c55e"
}

function abcClass(index, total) {
  if (index < total * 0.3)  return "A"
  if (index < total * 0.7)  return "B"
  return "C"
}

function abcColor(cls) {
  if (cls === "A") return "#ef4444"
  if (cls === "B") return "#f59e0b"
  return "#22c55e"
}

function fmt(n) {
  return "₹" + Number(n).toLocaleString("en-IN")
}

// ── Shared sub-components ─────────────────────────────────────────────────────

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

// ── Dashboard page components ─────────────────────────────────────────────────

function InventoryTable({ data }) {
  const rows = []
  for (const item of data) {
    for (const ch of item.channels) {
      rows.push({
        sku: item.sku, name: item.name, channel: ch.channel,
        qty: ch.quantity_on_hand, reserved: ch.quantity_reserved,
        available: ch.quantity_available, reorder: item.reorder_point,
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
              <th>SKU</th><th>Channel</th><th>On Hand</th>
              <th>Available</th><th>Reorder At</th><th>Status</th>
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
    sku: f.sku,
    days: daysUntil(f.stockout_date) ?? 99,
    reorder: f.reorder_flag,
  }))
  return (
    <div className="card">
      <h2 className="card-title"><TrendingDown size={16} /> Forecast — Days Until Stockout</h2>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData} margin={{ top: 4, right: 8, left: -10, bottom: 60 }}>
          <XAxis dataKey="sku" tick={{ fontSize: 10 }} angle={-40} textAnchor="end" interval={0} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v) => [`${v} days`, "Until stockout"]} />
          <Bar dataKey="days" radius={[4, 4, 0, 0]}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={
              entry.days <= -7 ? "#7f1d1d" :
              entry.days <= 0  ? "#ef4444" :
              entry.days <= 7  ? "#f59e0b" :
              entry.days <= 30 ? "#eab308" :
              "#22c55e"
            } />
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

function AlertsPanel({ data, onMarkRead }) {
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
                <button
                  className="mark-read-btn"
                  onClick={() => onMarkRead(a.id)}
                  title="Mark as read"
                >
                  ✓
                </button>
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

// ── Analytics page ────────────────────────────────────────────────────────────

function AnalyticsPage({ data }) {
  const [categoryTab, setCategoryTab] = useState("All")

  if (!data || data.length === 0) {
    return <div className="loading">Loading analytics...</div>
  }

  // Get unique categories from data
  const categories = ["All", ...Array.from(new Set(data.map(p => p.category))).sort()]

  // Filter data based on selected category
  const filtered = categoryTab === "All" ? data : data.filter(p => p.category === categoryTab)

  // Chart 1 — sorted by priority score (already sorted from API)
  const priorityChart = filtered.map(p => ({
    sku: p.sku,
    score: p.priority_score,
    margin: p.margin_percent,
  }))

  // Chart 2 — sorted by profit per unit
  const profitChart = [...filtered]
    .sort((a, b) => b.profit_per_unit - a.profit_per_unit)
    .map(p => ({
      sku: p.sku,
      profit: p.profit_per_unit,
    }))

  // Table — sorted by profit per unit for ABC classification
  const byProfitUnit = [...filtered].sort((a, b) => b.profit_per_unit - a.profit_per_unit)

  // Summary stats for filtered data
  const totalRevenue  = filtered.reduce((s, p) => s + p.revenue_30d, 0)
  const totalProfit   = filtered.reduce((s, p) => s + p.total_profit_30d, 0)
  const totalUnits    = filtered.reduce((s, p) => s + p.units_sold_30d, 0)
  const avgMargin     = filtered.length > 0
    ? (filtered.reduce((s, p) => s + p.margin_percent, 0) / filtered.length).toFixed(1)
    : 0

  return (
    <div className="analytics-page">

      {/* Category filter tabs */}
      <div className="category-tabs">
        {categories.map(cat => (
          <button
            key={cat}
            className={`category-tab ${categoryTab === cat ? "category-tab-active" : ""}`}
            onClick={() => setCategoryTab(cat)}
          >
            {cat}
            <span className="category-count">
              {cat === "All" ? data.length : data.filter(p => p.category === cat).length}
            </span>
          </button>
        ))}
      </div>

      {/* Summary stat row */}
      <div className="analytics-stats">
        <div className="analytics-stat-card">
          <div className="analytics-stat-label">Total Revenue (30d)</div>
          <div className="analytics-stat-value">{fmt(totalRevenue)}</div>
        </div>
        <div className="analytics-stat-card">
          <div className="analytics-stat-label">Total Profit (30d)</div>
          <div className="analytics-stat-value" style={{ color: "#22c55e" }}>{fmt(totalProfit)}</div>
        </div>
        <div className="analytics-stat-card">
          <div className="analytics-stat-label">Units Sold (30d)</div>
          <div className="analytics-stat-value">{totalUnits.toLocaleString()}</div>
        </div>
        <div className="analytics-stat-card">
          <div className="analytics-stat-label">Avg Margin</div>
          <div className="analytics-stat-value" style={{ color: "#8b5cf6" }}>{avgMargin}%</div>
        </div>
      </div>

      {/* Two charts side by side */}
      <div className="analytics-charts">
        <div className="card">
          <h2 className="card-title"><BarChart2 size={16} /> Restock Priority Score</h2>
          <p className="chart-subtitle">Margin % × Units Sold — higher = restock first</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={priorityChart} margin={{ top: 4, right: 8, left: 10, bottom: 40 }}>
              <XAxis dataKey="sku" tick={{ fontSize: 10 }} angle={-35} textAnchor="end" />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => [v.toLocaleString(), "Priority Score"]} />
              <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                {priorityChart.map((_, i) => (
                  <Cell key={i} fill={i === 0 ? "#22c55e" : i < 3 ? "#f59e0b" : "#6b7280"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h2 className="card-title"><TrendingUp size={16} /> Profit Per Unit — High Value Items</h2>
          <p className="chart-subtitle">Each unit lost = this much profit missed. Never let these stock out.</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={profitChart} margin={{ top: 4, right: 8, left: 10, bottom: 40 }}>
              <XAxis dataKey="sku" tick={{ fontSize: 10 }} angle={-35} textAnchor="end" />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => [fmt(v), "Profit / unit"]} />
              <Bar dataKey="profit" radius={[4, 4, 0, 0]}>
                {profitChart.map((_, i) => (
                  <Cell key={i} fill={i < 3 ? "#ef4444" : i < 6 ? "#f59e0b" : "#6b7280"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Profitability table with ABC classification */}
      <div className="card">
        <h2 className="card-title"><Package size={16} /> Product Profitability — ABC Analysis</h2>
        <p className="chart-subtitle">
          🔴 A-items: protect at all costs &nbsp;|&nbsp;
          🟡 B-items: restock by margin &nbsp;|&nbsp;
          🟢 C-items: restock by velocity
        </p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Class</th>
                <th>SKU</th>
                <th>Category</th>
                <th>Sell Price</th>
                <th>Unit Cost</th>
                <th>Profit/Unit</th>
                <th>Margin %</th>
                <th>Units Sold</th>
                <th>Total Profit</th>
                <th>Restock Cost</th>
                <th>Priority</th>
              </tr>
            </thead>
            <tbody>
              {byProfitUnit.map((p, i) => {
                const cls = abcClass(i, byProfitUnit.length)
                return (
                  <tr key={i}>
                    <td>
                      <span style={{
                        background: abcColor(cls),
                        color: "#fff",
                        borderRadius: 4,
                        padding: "2px 8px",
                        fontWeight: 700,
                        fontSize: 12,
                      }}>{cls}</span>
                    </td>
                    <td><span className="sku">{p.sku}</span></td>
                    <td>
                      <span style={{
                        fontSize: 11,
                        color: "#94a3b8",
                        background: "#0f172a",
                        padding: "2px 8px",
                        borderRadius: 4,
                      }}>{p.category}</span>
                    </td>
                    <td>{fmt(p.selling_price)}</td>
                    <td>{fmt(p.unit_cost)}</td>
                    <td style={{ color: "#22c55e", fontWeight: 600 }}>{fmt(p.profit_per_unit)}</td>
                    <td style={{ color: "#8b5cf6" }}>{p.margin_percent}%</td>
                    <td>{p.units_sold_30d.toLocaleString()}</td>
                    <td style={{ color: "#22c55e", fontWeight: 600 }}>{fmt(p.total_profit_30d)}</td>
                    <td style={{ color: "#f59e0b" }}>{fmt(p.restock_cost)}</td>
                    <td>{p.priority_score.toLocaleString()}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  )
}

// ── Main App ──────────────────────────────────────────────────────────────────

export default function App() {
  const [tab, setTab]           = useState("dashboard")
  const [inventory, setInventory] = useState([])
  const [forecasts, setForecasts] = useState([])
  const [alerts, setAlerts]     = useState([])
  const [analytics, setAnalytics] = useState([])
  const [lastRefresh, setLastRefresh] = useState(null)
  const [loading, setLoading]   = useState(true)

  const fetchAll = useCallback(async () => {
    try {
      const [inv, fcast, alrt, anal] = await Promise.all([
        axios.get(`${API}/inventory/summary`),
        axios.get(`${API}/inventory/forecasts`),
        axios.get(`${API}/inventory/alerts`),
        axios.get(`${API}/analytics/profitability`),
      ])
      setInventory(inv.data.data || [])
      setForecasts(fcast.data.forecasts || [])
      setAlerts(alrt.data.alerts || [])
      setAnalytics(anal.data.products || [])
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

  const markAlertRead = useCallback(async (alertId) => {
    try {
      await axios.patch(`${API}/inventory/alerts/${alertId}/read`)
      // Optimistic update — remove from local state immediately
      setAlerts(prev => prev.filter(a => a.id !== alertId))
    } catch (e) {
      console.error("Failed to mark alert read:", e)
    }
  }, [])

  const criticalCount = alerts.filter(a => a.severity === "critical").length
  const lowStockCount = inventory.filter(i => i.low_stock).length
  const reorderCount  = forecasts.filter(f => f.reorder_flag).length

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
            <StatCard icon={Package}       label="Low Stock SKUs"  value={lowStockCount} color="#f59e0b" />
            <StatCard icon={TrendingDown}  label="Reorder Needed"  value={reorderCount}  color="#8b5cf6" />
          </div>
          <button className="refresh-btn" onClick={fetchAll}>
            <RefreshCw size={14} /> Refresh
          </button>
          {lastRefresh && <span className="last-refresh">Updated {lastRefresh.toLocaleTimeString()}</span>}
        </div>
      </header>

      {/* Tab navigation */}
      <nav className="tab-nav">
        <button
          className={`tab-btn ${tab === "dashboard" ? "tab-active" : ""}`}
          onClick={() => setTab("dashboard")}
        >
          Dashboard
        </button>
        <button
          className={`tab-btn ${tab === "analytics" ? "tab-active" : ""}`}
          onClick={() => setTab("analytics")}
        >
          Analytics
        </button>
      </nav>

      <main className="main">
        {tab === "dashboard" ? (
          <div className="dashboard-grid">
            <InventoryTable data={inventory} />
            <div className="bottom-row">
              <ForecastPanel data={forecasts} />
              <AlertsPanel data={alerts} onMarkRead={markAlertRead} />
            </div>
          </div>
        ) : (
          <div style={{ width: "100%" }}>
            <AnalyticsPage data={analytics} />
          </div>
        )}
      </main>
    </div>
  )
}