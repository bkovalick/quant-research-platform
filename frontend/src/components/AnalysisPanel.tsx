import { useState, useMemo } from "react"
import type { CSSProperties } from "react"
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, Cell, Legend
} from "recharts"
import { getEffectiveSummary } from "../utils/metricsUtils"
import type { DateWindow } from "../utils/metricsUtils"

type AnalysisTab = "risk" | "tail" | "drawdown" | "trade_quality"

const TABS: { key: AnalysisTab; label: string }[] = [
  { key: "risk",          label: "Risk Profile" },
  { key: "tail",          label: "Tail Risk" },
  { key: "drawdown",      label: "Drawdown" },
  { key: "trade_quality", label: "Trade Quality" }
]

const COLORS = ["#3fb950", "#1f6feb", "#d29922", "#f85149", "#a371f7", "#56d364"]

const TOOLTIPS: Record<string, string> = {
  Volatility: "Annualized standard deviation of returns. Measures total variability — both up and down.",
  "Max Drawdown": "Largest peak-to-trough decline over the backtest. The worst-case loss an investor would have experienced.",
  Sharpe: "Annualized excess return divided by annualized volatility. Higher is better.",
  "Sharpe Ratio": "Annualized excess return divided by annualized volatility. Higher is better.",
  "Sortino Ratio": "Like Sharpe, but only penalizes downside volatility.",
  "Calmar Ratio": "Annualized return divided by maximum drawdown.",
  "Tracking Error": "Annualized standard deviation of returns relative to the benchmark.",
  "Info Ratio": "Annualized active return divided by tracking error. Measures how consistently the strategy generates returns above the benchmark per unit of active risk.",
  VaR: "Value at Risk (95%). The return threshold exceeded only 5% of the time.",
  CVaR: "Conditional VaR (95%). The average return in the worst 5% of periods.",
  Skewness: "Asymmetry of the return distribution.",
  Kurtosis: "Fat-tailedness relative to a normal distribution.",
  "Max DD": "Largest peak-to-trough decline.",
  "Avg DD": "Mean of all below-peak drawdown values.",
  "Max DD Days": "Longest consecutive streak of periods below a previous peak.",
  Turnover: "Average annual portfolio turnover.",
  "Win Rate": "Fraction of periods with a positive return.",
  "Loss Rate": "Fraction of periods with a negative return.",
  "Average Win": "Mean return across all winning periods.",
  "Average Loss": "Mean return across all losing periods.",
}

function MetricTooltip({ label, children }: { label: string; children: React.ReactNode }) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null)
  const tip = TOOLTIPS[label]
  return (
    <div style={{ position: "relative", display: "inline-block" }}
      onMouseEnter={(e) => tip && setPos({ x: e.clientX, y: e.clientY })}
      onMouseMove={(e) => tip && setPos({ x: e.clientX, y: e.clientY })}
      onMouseLeave={() => setPos(null)}
    >
      {children}
      {pos && tip && (
        <div style={{ ...tooltipBox, top: pos.y + 12, left: Math.min(pos.x + 8, window.innerWidth - 250) }}>
          <strong style={{ display: "block", marginBottom: 4, color: "#e6edf3" }}>{label}</strong>
          {tip}
        </div>
      )}
    </div>
  )
}

interface Props {
  runs: any[]
  selectedRun: any
  dateWindow: DateWindow | null
}

export default function AnalysisPanel({ runs, selectedRun, dateWindow }: Props) {
  const [tab, setTab] = useState<AnalysisTab>("risk")

  if (!runs || runs.length === 0) return null

  // Precompute effective summaries for all runs
  const effectiveSummaries = useMemo(() => {
    const map: Record<string, any> = {}
    runs.forEach(run => {
      map[run.run_id] = getEffectiveSummary(run, dateWindow)
    })
    return map
  }, [runs, dateWindow])

  // Inject effective summaries back into run objects for sub-components
  const enrichedRuns = runs.map(run => ({
    ...run,
    effectiveSummary: effectiveSummaries[run.run_id]
  }))

  return (
    <div style={panel}>
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
      {dateWindow && (
        <div style={windowBar}>
          Showing windowed metrics · {formatDate(dateWindow.start)} – {formatDate(dateWindow.end)}
          {" "}· <em style={{ color: "#8b949e" }}>Alpha &amp; Tracking Error unavailable in window mode</em>
        </div>
      )}
      <div style={body}>
        {tab === "risk"          && <RiskProfile runs={enrichedRuns} />}
        {tab === "tail"          && <TailRisk runs={enrichedRuns} />}
        {tab === "drawdown"      && <DrawdownView runs={enrichedRuns} />}
        {tab === "trade_quality" && <TradeQualityView runs={enrichedRuns} />}
      </div>
    </div>
  )
}

/* ── RISK PROFILE ── */
function RiskProfile({ runs }: any) {
  const metrics = [
    { key: "volatility",     label: "Volatility",     fmt: "pct" },
    { key: "max_drawdown",   label: "Max Drawdown",   fmt: "pct" },
    { key: "sharpe_ratio",   label: "Sharpe",         fmt: "num" },
    { key: "tracking_error",    label: "Tracking Error", fmt: "pct" },
    { key: "information_ratio", label: "Info Ratio",      fmt: "num" },
    { key: "sortino_ratio",  label: "Sortino Ratio",  fmt: "num" },
    { key: "calmar_ratio",   label: "Calmar Ratio",   fmt: "num" },
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
            const s = run.effectiveSummary
            return (
              <tr key={run.run_id} style={row}>
                <td style={leftCell}>
                  <span style={{ ...colorDot, backgroundColor: COLORS[i % COLORS.length] }} />
                  {formatName(run.strategy_name)}
                </td>
                <td style={rightCell}>{fmt(s.volatility, "pct")}</td>
                <td style={rightCellRed(s.max_drawdown)}>{fmt(s.max_drawdown, "pct")}</td>
                <td style={rightCell}>{fmt(s.sharpe_ratio, "num")}</td>
                <td style={rightCell}>{s.tracking_error != null ? fmt(s.tracking_error, "pct") : "-"}</td>
                <td style={rightCell}>{s.information_ratio != null ? fmt(s.information_ratio, "num") : "-"}</td>
                <td style={rightCell}>{fmt(s.sortino_ratio, "num")}</td>
                <td style={rightCell}>{fmt(s.calmar_ratio, "num")}</td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <SectionTitle style={{ marginTop: 28 }}>Risk Radar</SectionTitle>
      <p style={chartNote}>Normalized across strategies — further from center = more risk</p>
      <div style={{ height: 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={buildRadarData(runs)}>
            <PolarGrid stroke="#2a2f3a" />
            <PolarAngleAxis dataKey="metric" tick={{ fill: "#8b949e", fontSize: 11 }} />
            <Tooltip contentStyle={{ background: "#161b22", border: "1px solid #2a2f3a", fontSize: 12 }} />
            {runs.map((run: any, i: number) => (
              <Radar
                key={run.run_id}
                name={formatName(run.strategy_name)}
                dataKey={run.run_id}
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
  const barData = runs.map((run: any, i: number) => ({
    name: formatName(run.strategy_name),
    VaR:  run.effectiveSummary.var_95  != null ? Math.abs(run.effectiveSummary.var_95 * 100)  : null,
    CVaR: run.effectiveSummary.cvar_95 != null ? Math.abs(run.effectiveSummary.cvar_95 * 100) : null,
    color: COLORS[i % COLORS.length]
  }))
  const hasBarData = barData.some((d: any) => d.VaR != null)

  return (
    <div style={tabBody}>
      <SectionTitle>Tail Risk Metrics</SectionTitle>
      <table style={table}>
        <thead>
          <tr style={headerRow}>
            <th style={leftHeader}>Strategy</th>
            {["VaR", "CVaR", "Skewness", "Kurtosis"].map(label => (
              <th key={label} style={rightHeader}>
                <MetricTooltip label={label}>
                  <span style={tooltipLabel}>{label} <span style={dotStyle}>?</span></span>
                </MetricTooltip>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {runs.map((run: any, i: number) => {
            const s = run.effectiveSummary
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
                <Bar dataKey="VaR"  fill="#d29922" radius={[3,3,0,0]} />
                <Bar dataKey="CVaR" fill="#f85149" radius={[3,3,0,0]} />
                <Legend wrapperStyle={{ fontSize: 11, color: "#8b949e" }} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  )
}

/* ── DRAWDOWN ── */
function DrawdownView({ runs }: any) {
  const barData = runs.map((run: any, i: number) => ({
    name: formatName(run.strategy_name),
    "Max DD": run.effectiveSummary.max_drawdown != null
      ? Math.abs(run.effectiveSummary.max_drawdown * 100) : null,
    color: COLORS[i % COLORS.length]
  }))

  return (
    <div style={tabBody}>
      <SectionTitle>Drawdown Analysis</SectionTitle>
      <table style={table}>
        <thead>
          <tr style={headerRow}>
            <th style={leftHeader}>Strategy</th>
            {["Max DD", "Avg DD", "Max DD Days"].map(label => (
              <th key={label} style={rightHeader}>
                <MetricTooltip label={label}>
                  <span style={tooltipLabel}>{label} <span style={dotStyle}>?</span></span>
                </MetricTooltip>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {runs.map((run: any, i: number) => {
            const s = run.effectiveSummary
            return (
              <tr key={run.run_id} style={row}>
                <td style={leftCell}>
                  <span style={{ ...colorDot, backgroundColor: COLORS[i % COLORS.length] }} />
                  {formatName(run.strategy_name)}
                </td>
                <td style={rightCellRed(s.max_drawdown)}>{fmt(s.max_drawdown, "pct")}</td>
                <td style={rightCellRed(s.avg_drawdown)}>{fmt(s.avg_drawdown, "pct")}</td>
                <td style={rightCell}>{s.max_drawdown_duration != null ? Math.round(s.max_drawdown_duration) : "-"}</td>
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

/* ── TRADE QUALITY ── */
function TradeQualityView({ runs }: any) {
  const winLossData = runs.map((run: any, i: number) => ({
    name: formatName(run.strategy_name),
    "Win Rate":  run.effectiveSummary.win_rate  != null ? +(run.effectiveSummary.win_rate  * 100).toFixed(2) : null,
    "Loss Rate": run.effectiveSummary.loss_rate != null ? +(run.effectiveSummary.loss_rate * 100).toFixed(2) : null,
    color: COLORS[i % COLORS.length]
  }))

  const avgWinLossData = runs.map((run: any, i: number) => ({
    name: formatName(run.strategy_name),
    "Avg Win":  run.effectiveSummary.average_win  != null ? +(run.effectiveSummary.average_win  * 100).toFixed(2) : null,
    "Avg Loss": run.effectiveSummary.average_loss != null ? Math.abs(+(run.effectiveSummary.average_loss * 100).toFixed(2)) : null,
    color: COLORS[i % COLORS.length]
  }))

  const hasData = winLossData.some((d: any) => d["Win Rate"] != null)

  return (
    <div style={tabBody}>
      <SectionTitle>Trade Analysis</SectionTitle>
      <table style={table}>
        <thead>
          <tr style={headerRow}>
            <th style={leftHeader}>Strategy</th>
            {["Turnover", "Win Rate", "Loss Rate", "Average Win", "Average Loss"].map(label => (
              <th key={label} style={rightHeader}>
                <MetricTooltip label={label}>
                  <span style={tooltipLabel}>{label} <span style={dotStyle}>?</span></span>
                </MetricTooltip>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {runs.map((run: any, i: number) => {
            const s = run.effectiveSummary
            return (
              <tr key={run.run_id} style={row}>
                <td style={leftCell}>
                  <span style={{ ...colorDot, backgroundColor: COLORS[i % COLORS.length] }} />
                  {formatName(run.strategy_name)}
                </td>
                <td style={rightCell}>{fmt(s.turnover, "num")}</td>
                <td style={{ ...rightCell, color: "#3fb950" }}>{fmt(s.win_rate, "pct")}</td>
                <td style={{ ...rightCell, color: "#f85149" }}>{fmt(s.loss_rate, "pct")}</td>
                <td style={rightCell}>{fmt(s.average_win, "num")}</td>
                <td style={rightCell}>{fmt(s.average_loss, "num")}</td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {hasData && (
        <>
          <SectionTitle style={{ marginTop: 24 }}>Win vs Loss Rate (%)</SectionTitle>
          <div style={{ height: 180 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={winLossData} barCategoryGap="30%">
                <XAxis dataKey="name" tick={{ fill: "#8b949e", fontSize: 10 }} />
                <YAxis tick={{ fill: "#8b949e", fontSize: 10 }} tickFormatter={v => v + "%"} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ background: "#161b22", border: "1px solid #2a2f3a", fontSize: 12 }}
                  formatter={(v: any) => v.toFixed(1) + "%"}
                />
                <Bar dataKey="Win Rate"  fill="#3fb950" radius={[3,3,0,0]} />
                <Bar dataKey="Loss Rate" fill="#f85149" radius={[3,3,0,0]} />
                <Legend wrapperStyle={{ fontSize: 11, color: "#8b949e" }} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <SectionTitle style={{ marginTop: 24 }}>Avg Win vs Avg Loss (absolute %)</SectionTitle>
          <div style={{ height: 180 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={avgWinLossData} barCategoryGap="30%">
                <XAxis dataKey="name" tick={{ fill: "#8b949e", fontSize: 10 }} />
                <YAxis tick={{ fill: "#8b949e", fontSize: 10 }} tickFormatter={v => v + "%"} />
                <Tooltip
                  contentStyle={{ background: "#161b22", border: "1px solid #2a2f3a", fontSize: 12 }}
                  formatter={(v: any) => v.toFixed(2) + "%"}
                />
                <Bar dataKey="Avg Win"  fill="#3fb950" radius={[3,3,0,0]} />
                <Bar dataKey="Avg Loss" fill="#f85149" radius={[3,3,0,0]} />
                <Legend wrapperStyle={{ fontSize: 11, color: "#8b949e" }} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  )
}

/* ── Helpers ── */
function SectionTitle({ children, style }: any) {
  return <h4 style={{ ...sectionTitleStyle, ...style }}>{children}</h4>
}

function buildRadarData(runs: any[]) {
  const keys   = ["volatility", "max_drawdown", "sharpe_ratio", "sortino_ratio", "calmar_ratio"]
  const labels = ["Volatility", "Max DD", "Sharpe", "Sortino", "Calmar"]
  const invertedKeys = new Set(["sharpe_ratio", "sortino_ratio", "calmar_ratio"])

  const mins: Record<string, number> = {}
  const maxs: Record<string, number> = {}
  keys.forEach(k => {
    const vals = runs.map(r => Math.abs(r.effectiveSummary?.[k] ?? 0))
    mins[k] = Math.min(...vals)
    maxs[k] = Math.max(...vals)
  })

  return keys.map((k, idx) => {
    const row: any = { metric: labels[idx] }
    runs.forEach(run => {
      const raw = Math.abs(run.effectiveSummary?.[k] ?? 0)
      const range = maxs[k] - mins[k]
      const normalized = range === 0 ? 0.5 : (raw - mins[k]) / range
      row[run.run_id] = invertedKeys.has(k) ? 1 - normalized : normalized
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

function formatDate(d: string): string {
  return new Date(d).toLocaleDateString("en-US", { year: "numeric", month: "short" })
}

/* ── Styles ── */
const panel: CSSProperties = {
  background: "#161b22", border: "1px solid #2a2f3a",
  borderRadius: 8, overflow: "visible", height: "100%"
}
const tabStrip: CSSProperties = {
  display: "flex", borderBottom: "1px solid #2a2f3a", background: "#0d1117"
}
const baseTab: CSSProperties = {
  flex: 1, padding: "10px 0", background: "none", border: "none",
  borderBottom: "2px solid transparent", cursor: "pointer",
  fontSize: 12, fontWeight: 600, letterSpacing: "0.3px", color: "#8b949e"
}
const activeTab: CSSProperties = { ...baseTab, color: "#e6edf3", borderBottom: "2px solid #238636" }
const inactiveTab: CSSProperties = baseTab
const windowBar: CSSProperties = {
  padding: "5px 16px", fontSize: 10, color: "#388bfd",
  background: "#0d1117", borderBottom: "1px solid #21262d"
}
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
const colorDot: CSSProperties = { display: "inline-block", width: 8, height: 8, borderRadius: "50%", flexShrink: 0 }
const legend: CSSProperties = { display: "flex", flexWrap: "wrap", gap: "6px 16px", marginTop: 8, justifyContent: "center" }
const legendItem: CSSProperties = { display: "flex", alignItems: "center", gap: 5 }
const chartNote: CSSProperties = { fontSize: 11, color: "#8b949e", margin: "0 0 12px 0", fontStyle: "italic" }
const tooltipLabel: CSSProperties = { cursor: "help" }
const dotStyle: CSSProperties = {
  display: "inline-flex", alignItems: "center", justifyContent: "center",
  width: 12, height: 12, borderRadius: "50%", background: "#30363d",
  color: "#8b949e", fontSize: 9, fontWeight: 700, marginLeft: 3, verticalAlign: "middle"
}
const tooltipBox: CSSProperties = {
  position: "fixed", top: "auto", left: "auto",
  width: 230, background: "#161b22", border: "1px solid #30363d",
  borderRadius: 6, padding: "10px 12px", fontSize: 12,
  color: "#8b949e", lineHeight: 1.5, zIndex: 9999,
  boxShadow: "0 4px 16px rgba(0,0,0,0.5)", pointerEvents: "none",
  textAlign: "left", fontWeight: 400
}
