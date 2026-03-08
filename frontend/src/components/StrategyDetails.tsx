import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts"
import type { CSSProperties } from "react"

const colors = ["#3fb950", "#1f6feb", "#d29922", "#f85149", "#a371f7", "#56d364"]

export default function StrategyDetails({ runs }: any) {
  if (!runs || runs.length === 0) return null

  const baseSeries = runs[0].result.series.portfolio_wealth_factors
  if (!baseSeries) return null

  const data = baseSeries.index.map((date: string, i: number) => {
    const row: any = { date }
    runs.forEach((run: any) => {
      row[run.strategy_name] = run.result.series.portfolio_wealth_factors?.values[i]
    })
    return row
  })

  return (
    <div style={outerContainer}>
      {/* Header bar matches AnalysisPanel tab strip height */}
      <div style={headerBar}>
        <span style={headerLabel}>Cumulative Performance (Log Scale)</span>
      </div>

      <div style={innerContainer}>
        <div style={{ height: 280 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <XAxis
                dataKey="date"
                tickFormatter={(date: string | number) => new Date(date).getFullYear().toString()}
                interval="preserveStartEnd"
                tick={{ fill: "#8b949e", fontSize: 11 }}
                minTickGap={50}
              />
              <YAxis
                scale="log"
                domain={["auto", "auto"]}
                tickFormatter={(val) => val.toFixed(0)}
                tick={{ fill: "#8b949e", fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{ backgroundColor: "#161b22", border: "1px solid #2a2f3a", fontSize: 12 }}
              />
              {runs.map((run: any, i: number) => (
                <Line
                  key={run.run_id}
                  type="monotone"
                  dataKey={run.strategy_name}
                  stroke={colors[i % colors.length]}
                  strokeWidth={1.5}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div style={legendContainer}>
          {runs.map((run: any, i: number) => (
            <div key={run.run_id} style={legendItem}>
              <span style={{ ...legendDot, backgroundColor: colors[i % colors.length] }} />
              <span style={legendText}>{formatStrategyName(run.strategy_name)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function formatStrategyName(name: string) {
  return name.replace("_portfolio", "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

const outerContainer: CSSProperties = {
  background: "#161b22",
  borderRadius: 8,
  border: "1px solid #2a2f3a",
  overflow: "hidden"
}
const headerBar: CSSProperties = {
  background: "#0d1117",
  borderBottom: "1px solid #2a2f3a",
  padding: "10px 16px",
  display: "flex",
  alignItems: "center",
  justifyContent: "center"
}
const headerLabel: CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: "#e6edf3",
  letterSpacing: "0.3px"
}
const innerContainer: CSSProperties = {
  padding: "16px 16px 12px"
}
const legendContainer: CSSProperties = {
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  gap: 20,
  marginTop: 10,
  flexWrap: "wrap"
}
const legendItem: CSSProperties = { display: "flex", alignItems: "center", gap: 5, whiteSpace: "nowrap" }
const legendDot: CSSProperties = { width: 8, height: 8, borderRadius: "50%" }
const legendText: CSSProperties = { fontSize: 11, color: "#8b949e", fontWeight: 500 }
