import { useState, useMemo } from "react"
import type { CSSProperties } from "react"

type SortKey =
  | "strategy_name"
  | "return"
  | "volatility"
  | "sharpe_ratio"
  | "max_drawdown"
  | "turnover"

export default function StrategyGrid({ runs, onSelect }: any) {
  const [sortKey, setSortKey] = useState<SortKey>("sharpe_ratio")
  const [ascending, setAscending] = useState(false)

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setAscending(!ascending)
    } else {
      setSortKey(key)
      setAscending(false)
    }
  }

  const sortedRuns = useMemo(() => {
    return [...runs].sort((a, b) => {
      const getValue = (run: any) => {
        if (keyIsSummary(sortKey)) {
          return run.result.summary[sortKey]
        }
        return run[sortKey]
      }

      const valA = getValue(a)
      const valB = getValue(b)

      if (valA == null) return 1
      if (valB == null) return -1

      if (typeof valA === "string") {
        return ascending
          ? valA.localeCompare(valB)
          : valB.localeCompare(valA)
      }

      return ascending ? valA - valB : valB - valA
    })
  }, [runs, sortKey, ascending])

  return (
    <div style={container}>
      <h3 style={sectionTitle}>Strategy Overview</h3>
      <table style={table}>
        <thead>
          <tr style={headerRow}>
            <HeaderCell label="Strategy" onClick={() => handleSort("strategy_name")} />
            <HeaderCell label="Return" onClick={() => handleSort("return")} />
            <HeaderCell label="Vol" onClick={() => handleSort("volatility")} />
            <HeaderCell label="Sharpe" onClick={() => handleSort("sharpe_ratio")} />
            <HeaderCell label="Max DD" onClick={() => handleSort("max_drawdown")} />
            <HeaderCell label="Turnover" onClick={() => handleSort("turnover")} />
          </tr>
        </thead>

        <tbody>
          {sortedRuns.map((run: any) => {
            const s = run.result.summary

            return (
              <tr
                key={run.run_id}
                onClick={() => onSelect(run)}
                style={row}
              >
                <td style={leftCell}>{formatStrategyName(run.strategy_name)}</td>
                <td style={rightCellGreen(s.return)}>
                  {formatPct(s.return)}
                </td>
                <td style={rightCell}>
                  {formatPct(s.volatility)}
                </td>
                <td style={rightCell}>
                  {formatNumber(s.sharpe_ratio)}
                </td>
                <td style={rightCellRed(s.max_drawdown)}>
                  {formatPct(s.max_drawdown)}
                </td>
                <td style={rightCell}>
                  {formatNumber(s.turnover)}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/* ---------- Helpers ---------- */
function formatStrategyName(name: string) {
  return name
    .replace("_portfolio", "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function keyIsSummary(key: string) {
  return key !== "strategy_name"
}

function formatPct(value: number | null | undefined) {
  if (value == null) return "-"
  return (value * 100).toFixed(2) + "%"
}

function formatNumber(value: number | null | undefined) {
  if (value == null) return "-"
  return value.toFixed(2)
}

function HeaderCell({ label, onClick }: any) {
  return (
    <th style={clickableHeader} onClick={onClick}>
      {label}
    </th>
  )
}

/* ---------- Styles ---------- */
const sectionTitle: CSSProperties = {
  marginTop: 40,
  marginBottom: 16,
  fontSize: 16,
  fontWeight: 600,
  letterSpacing: "0.5px",
  textAlign: "center"
}

const container: CSSProperties = {
  background: "#161b22",
  borderRadius: 8,
  padding: 16,
  border: "1px solid #2a2f3a"
}

const table: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse"
}

const headerRow: CSSProperties = {
  borderBottom: "1px solid #2a2f3a"
}

const clickableHeader: CSSProperties = {
  textAlign: "right",
  padding: "10px 12px",
  fontWeight: 600,
  fontSize: 13,
  color: "#8b949e",
  cursor: "pointer",
  userSelect: "none"
}

const row: CSSProperties = {
  borderBottom: "1px solid #21262d",
  cursor: "pointer"
}

const leftCell: CSSProperties = {
  padding: "10px 12px",
  textAlign: "left"
}

const rightCell: CSSProperties = {
  padding: "10px 12px",
  textAlign: "right"
}

const rightCellGreen = (val: number | null | undefined): CSSProperties => ({
  ...rightCell,
  color: val != null && val > 0 ? "#3fb950" : "#f85149"
})

const rightCellRed = (_: number | null | undefined): CSSProperties => ({
  ...rightCell,
  color: "#f85149"
})