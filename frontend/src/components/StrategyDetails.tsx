import { useState, useMemo } from "react"
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ResponsiveContainer,
} from "recharts"
import type { CSSProperties } from "react"
import { deserializeToArray } from "../utils/metricsUtils"
import type { DateWindow } from "../utils/metricsUtils"

const COLORS = [
  "#3fb950",
  "#1f6feb",
  "#d29922",
  "#f85149",
  "#a371f7",
  "#56d364"
]

interface Props {
  runs: any[]
  onWindowChange: (window: DateWindow | null) => void
  dateWindow: DateWindow | null
}

export default function StrategyDetails({ runs, onWindowChange, dateWindow }: Props) {
  const [sliderStart, setSliderStart] = useState(0)
  const [sliderEnd, setSliderEnd] = useState(100)
  const [lastMoved, setLastMoved] = useState<"start" | "end">("end")

  if (!runs || runs.length === 0) return null

  // Build unified date index across all runs
  const allDates = useMemo(() => {
    const dateSet = new Set<string>()
    runs.forEach(run => {
      const wf = run.result.series?.portfolio_wealth_factors
      if (!wf) return
      const series = deserializeToArray(wf)
      series.forEach(p => dateSet.add(p.date))
    })
    return Array.from(dateSet).sort()
  }, [runs])

  // Build chart data — rebase each strategy to 1.0 at the window start date
  const data = useMemo(() => {
    const rebaseDate = dateWindow?.start ?? allDates[0]
    const rebaseIdx = allDates.findIndex(d => d >= rebaseDate)
    const effectiveRebaseIdx = rebaseIdx === -1 ? 0 : rebaseIdx

    const runMaps: Record<string, Record<string, number>> = {}
    runs.forEach(run => {
      const wf = run.result.series?.portfolio_wealth_factors
      if (!wf) return
      const series = deserializeToArray(wf)
      const map: Record<string, number> = {}
      series.forEach(p => { map[p.date] = p.value })
      runMaps[run.run_id] = map
    })

    return allDates.map((date) => {
      const row: any = { date }
      runs.forEach(run => {
        const map = runMaps[run.run_id]
        if (!map) return
        // Find this run's own first available date as rebase point
        const runDates = Object.keys(map).sort()
        const rebaseDate = dateWindow?.start
          ? runDates.find(d => d >= dateWindow.start) ?? runDates[0]
          : runDates[0]
        const rebaseValue = map[rebaseDate] ?? null
        const currentValue = map[date] ?? null
        if (rebaseValue && currentValue) row[run.run_id] = currentValue / rebaseValue
      })
      return row
    })
  }, [runs, allDates, dateWindow])

  // Downsample for chart rendering — max 500 points
  const chartData = useMemo(() => {
    if (data.length <= 500) return data
    const step = Math.ceil(data.length / 500)
    return data.filter((_: any, i: number) => i % step === 0 || i === data.length - 1)
  }, [data])

  const getDateAtPct = (pct: number) => {
    const idx = Math.round(pct / 100 * (allDates.length - 1))
    return allDates[Math.min(Math.max(idx, 0), allDates.length - 1)]
  }

  const handleStartChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Math.min(Number(e.target.value), sliderEnd - 5)
    setSliderStart(val)
    const startDate = getDateAtPct(val)
    const endDate = getDateAtPct(sliderEnd)
    if (startDate && endDate) onWindowChange({ start: startDate, end: endDate })
  }

  const handleEndChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Math.max(Number(e.target.value), sliderStart + 5)
    setSliderEnd(val)
    const startDate = getDateAtPct(sliderStart)
    const endDate = getDateAtPct(val)
    if (startDate && endDate) onWindowChange({ start: startDate, end: endDate })
  }

  const handleReset = () => {
    setSliderStart(0)
    setSliderEnd(100)
    onWindowChange(null)
  }

  const startDateLabel = getDateAtPct(sliderStart)
  const endDateLabel = getDateAtPct(sliderEnd)
  const isWindowed = sliderStart > 0 || sliderEnd < 100

  // Filter chartData to window
  const visibleData = useMemo(() => {
    if (!dateWindow) return chartData
    return chartData.filter((d: any) => d.date >= dateWindow.start && d.date <= dateWindow.end)
  }, [chartData, dateWindow])

  return (
    <div style={container}>
      {/* Header */}
      <div style={headerBar}>
        <span style={headerLabel}>Cumulative Performance (Log Scale)</span>
        {isWindowed && (
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={windowBadge}>
              {formatDate(startDateLabel)} → {formatDate(endDateLabel)}
            </span>
            <span style={rebaseNote}>Rebased</span>
            <button style={resetBtn} onClick={handleReset}>Reset</button>
          </div>
        )}
        {!isWindowed && (
          <span style={hintText}>Drag sliders below to zoom</span>
        )}
      </div>

      {/* Chart */}
      <div style={{ height: 300, padding: "12px 16px 0" }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={visibleData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <XAxis
              dataKey="date"
              tickFormatter={(d: string) => new Date(d).getFullYear().toString()}
              interval="preserveStartEnd"
              tick={{ fill: "#8b949e", fontSize: 11 }}
              minTickGap={50}
            />
            <YAxis
              scale="log"
              domain={["auto", "auto"]}
              tickFormatter={(v) => v.toFixed(1) + "x"}
              tick={{ fill: "#8b949e", fontSize: 11 }}
              width={40}
            />
            {/* Custom tooltip */}
            {/* Using recharts Tooltip with custom content */}
            <foreignObject x={0} y={0} width={0} height={0} />
            {runs.map((run: any, i: number) => (
              <Line
                key={run.run_id}
                type="monotone"
                dataKey={run.run_id}
                stroke={COLORS[i % COLORS.length]}
                strokeWidth={1.5}
                dot={false}
                connectNulls={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Dual range slider */}
      <div style={sliderContainer}>
        <div style={sliderTrackWrapper}>
          {/* Background track */}
          <div style={sliderTrack} />
          {/* Filled range */}
          <div style={{
            ...sliderFill,
            left: `${sliderStart}%`,
            width: `${sliderEnd - sliderStart}%`
          }} />
          {/* Start thumb — only covers left portion */}
          <input
            type="range" min={0} max={100} value={sliderStart}
            style={{
              ...sliderInput,
              width: `${sliderEnd}%`,
              zIndex: 5
            }}
            onChange={handleStartChange}
          />
          {/* End thumb — only covers right portion */}
          <input
            type="range" min={0} max={100} value={sliderEnd}
            style={{
              ...sliderInput,
              left: `${sliderStart}%`,
              width: `${100 - sliderStart}%`,
              zIndex: 5
            }}
            onChange={handleEndChange}
          />
        </div>
        <div style={sliderLabels}>
          <span style={sliderLabelText}>{formatDate(allDates[0])}</span>
          <span style={sliderLabelText}>{formatDate(allDates[allDates.length - 1])}</span>
        </div>
      </div>

      {/* Legend */}
      <div style={legendContainer}>
        {runs.map((run: any, i: number) => (
          <div key={run.run_id} style={legendItem}>
            <span style={{ ...legendDot, backgroundColor: COLORS[i % COLORS.length] }} />
            <span style={legendText}>{formatStrategyName(run.strategy_name)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function formatDate(d: string): string {
  if (!d) return ""
  return new Date(d).toLocaleDateString("en-US", { year: "numeric", month: "short" })
}

function formatStrategyName(name: string) {
  return name.replace("_portfolio", "").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())
}

const container: CSSProperties = {
  background: "#161b22",
  borderRadius: 8,
  border: "1px solid #2a2f3a",
  overflow: "hidden",
  marginTop: 16
}

const headerBar: CSSProperties = {
  background: "#0d1117",
  borderBottom: "1px solid #2a2f3a",
  padding: "10px 16px",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between"
}

const headerLabel: CSSProperties = {
  fontSize: 12, fontWeight: 600, color: "#e6edf3", letterSpacing: "0.3px"
}

const windowBadge: CSSProperties = {
  fontSize: 11, color: "#388bfd", fontWeight: 600
}

const rebaseNote: CSSProperties = {
  fontSize: 10, color: "#8b949e", fontStyle: "italic"
}

const resetBtn: CSSProperties = {
  background: "none", border: "1px solid #30363d", borderRadius: 3,
  color: "#8b949e", fontSize: 10, cursor: "pointer", padding: "1px 8px"
}

const hintText: CSSProperties = {
  fontSize: 10, color: "#8b949e", fontStyle: "italic"
}

const sliderContainer: CSSProperties = {
  padding: "12px 20px 4px"
}

const sliderTrackWrapper: CSSProperties = {
  position: "relative",
  height: 20,
  display: "flex",
  alignItems: "center"
}

const sliderFill: CSSProperties = {
  position: "absolute",
  height: 4,
  background: "#238636",
  borderRadius: 2,
  pointerEvents: "none",
  zIndex: 2
}

const sliderInput: CSSProperties = {
  position: "absolute",
  width: "100%",
  height: 4,
  background: "transparent",
  appearance: "none",
  outline: "none",
  cursor: "pointer",
  margin: 0,
  padding: 0
}

const sliderLabels: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  marginTop: 4
}

const sliderLabelText: CSSProperties = {
  fontSize: 10, color: "#8b949e"
}

const legendContainer: CSSProperties = {
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  gap: 24,
  padding: "10px 16px",
  flexWrap: "wrap"
}

const legendItem: CSSProperties = {
  display: "flex", alignItems: "center", gap: 6, whiteSpace: "nowrap"
}

const legendDot: CSSProperties = {
  width: 8, height: 8, borderRadius: "50%", display: "inline-block"
}

const legendText: CSSProperties = {
  fontSize: 11, color: "#8b949e"
}

const sliderTrack: CSSProperties = {
  position: "absolute",
  width: "100%",
  height: 4,
  background: "#2a2f3a",
  borderRadius: 2,
  pointerEvents: "none",
  zIndex: 1
}