import { useState } from "react"
import type { CSSProperties } from "react"
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, Cell, Legend
} from "recharts"

type AnalysisTab = "risk" | "tail" | "drawdown" | "trade_quality"

const TABS: { key: AnalysisTab; label: string }[] = [
  { key: "risk",     label: "Risk Profile" },
  { key: "tail",     label: "Tail Risk" },
  { key: "drawdown", label: "Drawdown" },
  { key: "trade_quality", label: "Trade Quality" }
]

const COLORS = ["#3fb950", "#1f6feb", "#d29922", "#f85149", "#a371f7", "#56d364"]

const TOOLTIPS: Record<string, string> = {
  // Risk Profile
  Volatility: "Annualized standard deviation of returns. Measures total variability — both up and down.",
  "Max Drawdown": "Largest peak-to-trough decline over the backtest. The worst-case loss an investor would have experienced.",
  Sharpe: "Annualized excess return divided by annualized volatility. The primary risk-adjusted performance measure — higher is better.",
  "Sharpe Ratio": "Annualized excess return divided by annualized volatility. The primary risk-adjusted performance measure — higher is better.",
  "Sortino Ratio": "Like Sharpe, but only penalizes downside volatility. Useful when return distributions are asymmetric — a higher Sortino than Sharpe suggests losses are less frequent than gains.",
  "Calmar Ratio": "Annualized return divided by maximum drawdown. Measures return per unit of worst-case risk — higher is better. Sensitive to the length of the backtest.",
  Turnover: "Average annual portfolio turnover. High turnover increases transaction costs and drag on returns.",
  // Tail Risk
  VaR: "Value at Risk (95%). The return threshold exceeded only 5% of the time — a typical bad day/week/period.",
  CVaR: "Conditional VaR (95%). The average return in the worst 5% of periods. Also called Expected Shortfall — a more complete picture of tail risk than VaR alone.",
  Skewness: "Asymmetry of the return distribution. Negative skew means occasional large losses dominate; positive skew means occasional large gains. Most equity strategies have negative skew.",
  Kurtosis: "Excess fat-tailedness relative to a normal distribution. Higher kurtosis means more extreme outlier events in both directions. A normal distribution has kurtosis = 0 (Fisher's definition).",
  // Drawdown
  "Max DD": "Largest peak-to-trough decline over the backtest. The single worst loss an investor would have experienced.",
  "Avg DD": "Mean of all below-peak drawdown values over the backtest. Measures typical pain experienced by the strategy, not just the worst-case event.",
  "Max DD Days": "Longest consecutive streak of periods spent below a previous peak. Measures recovery time — how long an investor would have waited to break even from the worst drawdown.",
}

function MetricTooltip({ label, children }: { label: string; children: React.ReactNode }) {
  const [visible, setVisible] = useState(false)
  const tip = TOOLTIPS[label]
  return (
    <div style={{ position: "relative", display: "inline-block" }}
      onMouseEnter={() => tip && setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      {children}
      {visible && tip && (
        <div style={tooltipBox}>
          <strong style={{ display: "block", marginBottom: 4, color: "#e6edf3" }}>{label}</strong>
          {tip}
        </div>
      )}
    </div>
  )
}

export default function AnalysisPanel({ runs, selectedRun }: any) {
  const [tab, setTab] = useState<AnalysisTab>("risk")

  if (!runs || runs.length === 0) return null

  return (
    <div style={panel}>
      {/* Tab strip */}
      <div style={tabStrip}>
        {TABS.map(t => (
          <button
            key={t.key}
            style={tab === t.key ? activeTab : inactiveTab}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div style={body}>
        {tab === "risk"     && <RiskProfile runs={runs} />}
        {tab === "tail"     && <TailRisk runs={runs} />}
        {tab === "drawdown" && <DrawdownView runs={runs} />}
        {tab === "trade_quality" && <TradeQualityView runs={runs} />}
      </div>
    </div>
  )
}

/* ── RISK PROFILE ── */
function RiskProfile({ runs }: any) {
  const metrics = [
    { key: "volatility",    label: "Volatility",    fmt: "pct" },
    { key: "max_drawdown",  label: "Max Drawdown",  fmt: "pct" },
    { key: "sharpe_ratio",  label: "Sharpe", fmt: "num" },
    { key: "tracking_error",  label: "Tracking Error", fmt: "pct" },
    { key: "sortino_ratio",  label: "Sortino Ratio", fmt: "num" },
    { key: "calmar_ratio",  label: "Calmar Ratio", fmt: "num" },
  ]

  return (
    <div style={tabBody}>
      <SectionTitle>Risk Metrics</SectionTitle>
      <table style={table}>
        <thead>
          <tr style={headerRow}>
            <th style={leftHeader}>Strategy</th>
            {metrics.map(m => (
              <th key={m.key} style={rightHeader}>
                <MetricTooltip label={m.label}>
                  <span style={tooltipLabel}>{m.label} <span style={dotStyle}>?</span></span>
                </MetricTooltip>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {runs.map((run: any, i: number) => {
            const s = run.result.summary
            return (
              <tr key={run.run_id} style={row}>
                <td style={leftCell}>
                  <span style={{ ...colorDot, backgroundColor: COLORS[i % COLORS.length] }} />
                  {formatName(run.strategy_name)}
                </td>
                <td style={rightCell}>{fmt(s.volatility, "pct")}</td>
                <td style={rightCellRed(s.max_drawdown)}>{fmt(s.max_drawdown, "pct")}</td>
                <td style={rightCell}>{fmt(s.sharpe_ratio, "num")}</td>
                <td style={rightCell}>{fmt(s.tracking_error, "pct")}</td>
                <td style={rightCell}>{fmt(s.sortino_ratio, "num")}</td>
                <td style={rightCell}>{fmt(s.calmar_ratio, "num")}</td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {/* Radar chart */}
      <SectionTitle style={{ marginTop: 28 }}>Risk Radar</SectionTitle>
      <p style={chartNote}>Normalized across strategies — further from center = more risk</p>
      <div style={{ height: 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={buildRadarData(runs)}>
            <PolarGrid stroke="#2a2f3a" />
            <PolarAngleAxis dataKey="metric" tick={{ fill: "#8b949e", fontSize: 11 }} />
            <Tooltip
              contentStyle={{ background: "#161b22", border: "1px solid #2a2f3a", fontSize: 12 }}
            />
            {runs.map((run: any, i: number) => (
              <Radar
                key={run.run_id}
                name={formatName(run.strategy_name)}
                dataKey={run.strategy_name}
                stroke={COLORS[i % COLORS.length]}
                fill={COLORS[i % COLORS.length]}
                fillOpacity={0.08}
              />
            ))}
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <div style={legend}>
        {runs.map((run: any, i: number) => (
          <div key={run.run_id} style={legendItem}>
            <span style={{ ...colorDot, backgroundColor: COLORS[i % COLORS.length] }} />
            <span style={{ fontSize: 11, color: "#8b949e" }}>{formatName(run.strategy_name)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ── TAIL RISK ── */
function TailRisk({ runs }: any) {
  const metrics = [
    { key: "var_95",      label: "VaR",      fmt: "pct" },
    { key: "cvar_95",     label: "CVaR",     fmt: "pct" },
    { key: "skewness",    label: "Skewness", fmt: "num" },
    { key: "kurtosis",    label: "Kurtosis", fmt: "num" },
  ]

  // Build bar chart data for VaR / CVaR
  const barData = runs.map((run: any, i: number) => ({
    name: formatName(run.strategy_name),
    VaR:  run.result.summary.var_95  != null ? Math.abs(run.result.summary.var_95 * 100)  : null,
    CVaR: run.result.summary.cvar_95 != null ? Math.abs(run.result.summary.cvar_95 * 100) : null,
    color: COLORS[i % COLORS.length]
  }))

  const hasBarData = barData.some((d: any) => d.VaR != null || d.CVaR != null)

  return (
    <div style={tabBody}>
      <SectionTitle>Tail Risk Metrics</SectionTitle>
      <table style={table}>
        <thead>
          <tr style={headerRow}>
            <th style={leftHeader}>Strategy</th>
            {metrics.map(m => (
              <th key={m.key} style={rightHeader}>
                <MetricTooltip label={m.label}>
                  <span style={tooltipLabel}>{m.label} <span style={dotStyle}>?</span></span>
                </MetricTooltip>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {runs.map((run: any, i: number) => {
            const s = run.result.summary
            return (
              <tr key={run.run_id} style={row}>
                <td style={leftCell}>
                  <span style={{ ...colorDot, backgroundColor: COLORS[i % COLORS.length] }} />
                  {formatName(run.strategy_name)}
                </td>
                <td style={rightCellRed(s.var_95)}>{fmt(s.var_95, "pct")}</td>
                <td style={rightCellRed(s.cvar_95)}>{fmt(s.cvar_95, "pct")}</td>
                <td style={rightCell}>{fmt(s.skewness, "num")}</td>
                <td style={rightCell}>{fmt(s.kurtosis, "num")}</td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {hasBarData && (
        <>
          <SectionTitle style={{ marginTop: 28 }}>VaR vs CVaR (95%, absolute %)</SectionTitle>
          <div style={{ height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData} barCategoryGap="30%">
                <XAxis dataKey="name" tick={{ fill: "#8b949e", fontSize: 10 }} />
                <YAxis tick={{ fill: "#8b949e", fontSize: 10 }} tickFormatter={v => v.toFixed(1) + "%"} />
                <Tooltip
                  contentStyle={{ background: "#161b22", border: "1px solid #2a2f3a", fontSize: 12 }}
                  formatter={(v: any) => v.toFixed(2) + "%"}
                />
                <Bar dataKey="VaR" fill="#d29922" radius={[3,3,0,0]} />
                <Bar dataKey="CVaR" fill="#f85149" radius={[3,3,0,0]} />
                <Legend wrapperStyle={{ fontSize: 11, color: "#8b949e" }} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      {!hasBarData && (
        <p style={chartNote}>VaR / CVaR not available in summary — add them to your backend response to enable this chart.</p>
      )}
    </div>
  )
}

/* ── DRAWDOWN ── */
function DrawdownView({ runs }: any) {
  const metrics = [
    { key: "max_drawdown",          label: "Max DD",        fmt: "pct" },
    { key: "avg_drawdown",          label: "Avg DD",        fmt: "pct" },
    { key: "max_drawdown_duration", label: "Max DD Days",   fmt: "num" },
  ]

  const barData = runs.map((run: any, i: number) => ({
    name: formatName(run.strategy_name),
    "Max DD": run.result.summary.max_drawdown != null
      ? Math.abs(run.result.summary.max_drawdown * 100) : null,
    color: COLORS[i % COLORS.length]
  }))

  return (
    <div style={tabBody}>
      <SectionTitle>Drawdown Analysis</SectionTitle>
      <table style={table}>
        <thead>
          <tr style={headerRow}>
            <th style={leftHeader}>Strategy</th>
            {metrics.map(m => (
              <th key={m.key} style={rightHeader}>{m.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {runs.map((run: any, i: number) => {
            const s = run.result.summary
            return (
              <tr key={run.run_id} style={row}>
                <td style={leftCell}>
                  <span style={{ ...colorDot, backgroundColor: COLORS[i % COLORS.length] }} />
                  {formatName(run.strategy_name)}
                </td>
                <td style={rightCellRed(-s.max_drawdown)}>{fmt(s.max_drawdown, "pct")}</td>
                <td style={rightCellRed(s.avg_drawdown)}>{fmt(s.avg_drawdown, "pct")}</td>
                <td style={rightCell}>{fmt(s.max_drawdown_duration, "num")}</td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <SectionTitle style={{ marginTop: 28 }}>Max Drawdown Comparison</SectionTitle>
      <div style={{ height: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={barData} barCategoryGap="35%">
            <XAxis dataKey="name" tick={{ fill: "#8b949e", fontSize: 10 }} />
            <YAxis tick={{ fill: "#8b949e", fontSize: 10 }} tickFormatter={v => v.toFixed(0) + "%"} />
            <Tooltip
              contentStyle={{ background: "#161b22", border: "1px solid #2a2f3a", fontSize: 12 }}
              formatter={(v: any) => v.toFixed(2) + "%"}
            />
            <Bar dataKey="Max DD" radius={[3,3,0,0]}>
              {barData.map((entry: any, i: number) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

/* ── Trade Quality ── */
function TradeQualityView({ runs }: any) {
  const metrics = [
    { key: "turnover",     label: "Turnover",     fmt: "pct" },
    { key: "win_rate",     label: "Win Rate",     fmt: "pct" },
    { key: "loss_rate",    label: "Loss Rate",    fmt: "pct" },
    { key: "average_win",  label: "Average Win",  fmt: "num" },
    { key: "average_loss", label: "Average Loss", fmt: "num" },
  ]

  const barData = runs.map((run: any, i: number) => ({
    name: formatName(run.strategy_name),
    "Max DD": run.result.summary.max_drawdown != null
      ? Math.abs(run.result.summary.max_drawdown * 100) : null,
    color: COLORS[i % COLORS.length]
  }))

  return (
    <div style={tabBody}>
      <SectionTitle>Trade Analysis</SectionTitle>
      <table style={table}>
        <thead>
          <tr style={headerRow}>
            <th style={leftHeader}>Strategy</th>
            {metrics.map(m => (
              <th key={m.key} style={rightHeader}>{m.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {runs.map((run: any, i: number) => {
            const s = run.result.summary
            return (
              <tr key={run.run_id} style={row}>
                <td style={leftCell}>
                  <span style={{ ...colorDot, backgroundColor: COLORS[i % COLORS.length] }} />
                  {formatName(run.strategy_name)}
                </td>
                <td style={rightCell}>{fmt(s.turnover, "pct")}</td>
                <td style={rightCellGreen(s.win_rate)}>{fmt(s.win_rate, "pct")}</td>
                <td style={rightCellRed(s.loss_rate)}>{fmt(s.loss_rate, "pct")}</td>
                <td style={rightCell}>{fmt(s.average_win, "num")}</td>
                <td style={rightCell}>{fmt(s.average_loss, "num")}</td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {/* <SectionTitle style={{ marginTop: 28 }}>Max Drawdown Comparison</SectionTitle>
      <div style={{ height: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={barData} barCategoryGap="35%">
            <XAxis dataKey="name" tick={{ fill: "#8b949e", fontSize: 10 }} />
            <YAxis tick={{ fill: "#8b949e", fontSize: 10 }} tickFormatter={v => v.toFixed(0) + "%"} />
            <Tooltip
              contentStyle={{ background: "#161b22", border: "1px solid #2a2f3a", fontSize: 12 }}
              formatter={(v: any) => v.toFixed(2) + "%"}
            />
            <Bar dataKey="Max DD" radius={[3,3,0,0]}>
              {barData.map((entry: any, i: number) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div> */}
    </div>
  )
}

/* ── Shared helpers ── */
function SectionTitle({ children, style }: any) {
  return <h4 style={{ ...sectionTitleStyle, ...style }}>{children}</h4>
}

function buildRadarData(runs: any[]) {
  const keys   = ["volatility", "max_drawdown", "sharpe_ratio", "sortino_ratio", "calmar_ratio"]
  const labels = ["Volatility", "Max DD",       "Sharpe",       "Sortino",       "Calmar"]
  // These axes are inverted: lower ratio = more risk = further from center
  const invertedKeys = new Set(["sharpe_ratio", "sortino_ratio", "calmar_ratio"])

  const mins: Record<string, number> = {}
  const maxs: Record<string, number> = {}
  keys.forEach(k => {
    const vals = runs.map(r => Math.abs(r.result.summary[k] ?? 0))
    mins[k] = Math.min(...vals)
    maxs[k] = Math.max(...vals)
  })

  return keys.map((k, idx) => {
    const row: any = { metric: labels[idx] }
    runs.forEach(run => {
      const raw = Math.abs(run.result.summary[k] ?? 0)
      const range = maxs[k] - mins[k]
      const normalized = range === 0 ? 0.5 : (raw - mins[k]) / range
      row[run.strategy_name] = invertedKeys.has(k) ? 1 - normalized : normalized
    })
    return row
  })
}

function fmt(v: number | null | undefined, type: "pct" | "num") {
  if (v == null) return "-"
  if (type === "pct") return (v * 100).toFixed(2) + "%"
  return v.toFixed(2)
}

function formatName(name: string) {
  return name.replace("_portfolio", "").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())
}

/* ── Styles ── */
const panel: CSSProperties = {
  background: "#161b22",
  border: "1px solid #2a2f3a",
  borderRadius: 8,
  overflow: "hidden",
  height: "100%"
}

const tabStrip: CSSProperties = {
  display: "flex",
  borderBottom: "1px solid #2a2f3a",
  background: "#0d1117"
}

const baseTab: CSSProperties = {
  flex: 1,
  padding: "10px 0",
  background: "none",
  border: "none",
  borderBottom: "2px solid transparent",
  cursor: "pointer",
  fontSize: 12,
  fontWeight: 600,
  letterSpacing: "0.3px",
  color: "#8b949e"
}

const activeTab: CSSProperties = {
  ...baseTab,
  color: "#e6edf3",
  borderBottom: "2px solid #238636"
}

const inactiveTab: CSSProperties = baseTab

const body: CSSProperties = { padding: 16 }
const tabBody: CSSProperties = { display: "flex", flexDirection: "column", gap: 0 }

const sectionTitleStyle: CSSProperties = {
  fontSize: 12, textTransform: "uppercase", letterSpacing: "0.6px",
  color: "#8b949e", margin: "0 0 10px 0", fontWeight: 600
}

const table: CSSProperties = { width: "100%", borderCollapse: "collapse" }
const headerRow: CSSProperties = { borderBottom: "1px solid #2a2f3a" }
const leftHeader: CSSProperties = { padding: "8px 10px", textAlign: "left", fontSize: 12, fontWeight: 600, color: "#8b949e" }
const rightHeader: CSSProperties = { padding: "8px 10px", textAlign: "right", fontSize: 12, fontWeight: 600, color: "#8b949e", cursor: "default" }
const row: CSSProperties = { borderBottom: "1px solid #21262d" }
const leftCell: CSSProperties = { padding: "8px 10px", textAlign: "left", fontSize: 12, display: "flex", alignItems: "center", gap: 6 }
const rightCell: CSSProperties = { padding: "8px 10px", textAlign: "right", fontSize: 12 }
const rightCellRed = (v: number | null | undefined): CSSProperties => ({
  ...rightCell, color: v != null && v < 0 ? "#f85149" : "#e6edf3"
})
const rightCellGreen = (val: number | null | undefined): CSSProperties => ({
  ...rightCell, color: val != null && val > 0 ? "#3fb950" : "#f85149"
})

const colorDot: CSSProperties = {
  display: "inline-block", width: 8, height: 8, borderRadius: "50%", flexShrink: 0
}

const legend: CSSProperties = {
  display: "flex", flexWrap: "wrap", gap: "6px 16px", marginTop: 8, justifyContent: "center"
}

const legendItem: CSSProperties = { display: "flex", alignItems: "center", gap: 5 }

const chartNote: CSSProperties = {
  fontSize: 11, color: "#8b949e", margin: "0 0 12px 0", fontStyle: "italic"
}

const tooltipLabel: CSSProperties = { cursor: "help" }

const dotStyle: CSSProperties = {
  display: "inline-flex", alignItems: "center", justifyContent: "center",
  width: 12, height: 12, borderRadius: "50%", background: "#30363d",
  color: "#8b949e", fontSize: 9, fontWeight: 700, marginLeft: 3, verticalAlign: "middle"
}

const tooltipBox: CSSProperties = {
  position: "absolute", bottom: "calc(100% + 8px)", right: 0,
  width: 230, background: "#161b22", border: "1px solid #30363d",
  borderRadius: 6, padding: "10px 12px", fontSize: 12,
  color: "#8b949e", lineHeight: 1.5, zIndex: 100,
  boxShadow: "0 4px 16px rgba(0,0,0,0.5)", pointerEvents: "none",
  textAlign: "left", fontWeight: 400
}
