import { useState, useMemo } from "react"
import type { CSSProperties } from "react"

type SortKey = "strategy_name" | "return" | "volatility" | "sharpe_ratio" | "max_drawdown" | "turnover"

const COLORS = ["#3fb950", "#1f6feb", "#d29922", "#f85149", "#a371f7", "#56d364"]

export default function StrategyGrid({ runs, onSelect }: any) {
  const [sortKey, setSortKey] = useState<SortKey>("sharpe_ratio")
  const [ascending, setAscending] = useState(false)

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setAscending(!ascending)
    else { setSortKey(key); setAscending(false) }
  }

  const sortedRuns = useMemo(() => {
    return [...runs].sort((a, b) => {
      const getValue = (run: any) => keyIsSummary(sortKey) ? run.result.summary[sortKey] : run[sortKey]
      const valA = getValue(a)
      const valB = getValue(b)
      if (valA == null) return 1
      if (valB == null) return -1
      if (typeof valA === "string") return ascending ? valA.localeCompare(valB) : valB.localeCompare(valA)
      return ascending ? valA - valB : valB - valA
    })
  }, [runs, sortKey, ascending])

  return (
    <div style={outerContainer}>
      <div style={headerBar}>
        <span style={headerLabel}>Strategy Overview</span>
      </div>
      <div style={innerContainer}>
      <table style={table}>
        <thead>
          <tr style={headerRow}>
            <th style={leftHeader} onClick={() => handleSort("strategy_name")}>Strategy</th>
            <SortHeader label="Return"   k="return"       sortKey={sortKey} ascending={ascending} onSort={handleSort} />
            <SortHeader label="Vol"      k="volatility"   sortKey={sortKey} ascending={ascending} onSort={handleSort} />
            <SortHeader label="Sharpe"   k="sharpe_ratio" sortKey={sortKey} ascending={ascending} onSort={handleSort} />
            <SortHeader label="Max DD"   k="max_drawdown" sortKey={sortKey} ascending={ascending} onSort={handleSort} />
            <SortHeader label="Turnover" k="turnover"     sortKey={sortKey} ascending={ascending} onSort={handleSort} />
          </tr>
        </thead>
        <tbody>
          {sortedRuns.map((run: any, i: number) => {
            const s = run.result.summary
            // Find original index for consistent color
            const colorIdx = runs.findIndex((r: any) => r.run_id === run.run_id)
            return (
              <tr key={run.run_id} onClick={() => onSelect(run)} style={row}>
                <td style={leftCell}>
                  <span style={{ ...colorDot, backgroundColor: COLORS[colorIdx % COLORS.length] }} />
                  {formatStrategyName(run.strategy_name)}
                </td>
                <td style={rightCellGreen(s.return)}>{formatPct(s.return)}</td>
                <td style={rightCell}>{formatPct(s.volatility)}</td>
                <td style={rightCell}>{formatNumber(s.sharpe_ratio)}</td>
                <td style={rightCellRed(s.max_drawdown)}>{formatPct(s.max_drawdown)}</td>
                <td style={rightCell}>{formatNumber(s.turnover)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      </div>
    </div>
  )
}

function SortHeader({ label, k, sortKey, ascending, onSort }: any) {
  const active = sortKey === k
  return (
    <th style={{ ...rightHeader, color: active ? "#e6edf3" : "#8b949e" }} onClick={() => onSort(k)}>
      {label} {active ? (ascending ? "↑" : "↓") : ""}
    </th>
  )
}

function formatStrategyName(name: string) {
  return name.replace("_portfolio", "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}
function keyIsSummary(key: string) { return key !== "strategy_name" }
function formatPct(v: number | null | undefined) { return v == null ? "-" : (v * 100).toFixed(2) + "%" }
function formatNumber(v: number | null | undefined) { return v == null ? "-" : v.toFixed(2) }

const outerContainer: CSSProperties = { background: "#161b22", borderRadius: 8, border: "1px solid #2a2f3a", overflow: "hidden" }
const headerBar: CSSProperties = { background: "#0d1117", borderBottom: "1px solid #2a2f3a", padding: "10px 16px", display: "flex", alignItems: "center", justifyContent: "center" }
const headerLabel: CSSProperties = { fontSize: 12, fontWeight: 600, color: "#e6edf3", letterSpacing: "0.3px" }
const innerContainer: CSSProperties = { padding: "0" }
const table: CSSProperties = { width: "100%", borderCollapse: "collapse" }
const headerRow: CSSProperties = { borderBottom: "1px solid #2a2f3a" }
const leftHeader: CSSProperties = { padding: "8px 10px", textAlign: "left", fontSize: 12, fontWeight: 600, color: "#8b949e", cursor: "pointer", userSelect: "none" }
const rightHeader: CSSProperties = { padding: "8px 10px", textAlign: "right", fontSize: 12, fontWeight: 600, cursor: "pointer", userSelect: "none" }
const row: CSSProperties = { borderBottom: "1px solid #21262d", cursor: "pointer" }
const leftCell: CSSProperties = { padding: "8px 10px", textAlign: "left", fontSize: 12, display: "flex", alignItems: "center", gap: 6 }
const rightCell: CSSProperties = { padding: "8px 10px", textAlign: "right", fontSize: 12 }
const rightCellGreen = (val: number | null | undefined): CSSProperties => ({
  ...rightCell, color: val != null && val > 0 ? "#3fb950" : "#f85149"
})
const rightCellRed = (_: number | null | undefined): CSSProperties => ({
  ...rightCell, color: "#f85149"
})
const colorDot: CSSProperties = {
  display: "inline-block", width: 8, height: 8, borderRadius: "50%", flexShrink: 0
}
