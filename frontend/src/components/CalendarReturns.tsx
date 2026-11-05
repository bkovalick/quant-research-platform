import { useMemo, useState } from "react"
import type { CSSProperties } from "react"
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, ReferenceLine, Tooltip,
} from "recharts"
import { periodReturns, partialYears } from "../utils/periodReturns"
import type { PeriodReturn, RunWithSeries } from "../utils/periodReturns"

interface YearRow { year: string; strategy: number; benchmark: number | null }

/**
 * Calendar returns for the selected run: a monthly heatmap (diverging blue/red
 * around a neutral gray, symmetric scale) and calendar-year bars against the
 * benchmark. Colors follow the dataviz reference palette's dark steps; the bar
 * pair (#3987e5 / #d95926) is validated against this card surface (#161b22).
 */

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

const COLOR = {
  positive: "#3987e5",     // diverging cool pole (dark step)
  negative: "#e66767",     // diverging warm pole (dark step)
  neutral: "#383835",      // diverging midpoint (dark)
  strategy: "#3987e5",     // categorical slot 1 (dark)
  benchmark: "#d95926",    // categorical slot 2 (dark)
  inkPrimary: "#e6edf3",
  inkSecondary: "#8b949e",
  inkOnLight: "#0b0b0b",
  inkOnDark: "#f0efec",
  grid: "#21262d",
  baseline: "#484f58",
}

const MONO: CSSProperties = {
  fontFamily: "ui-monospace, 'SF Mono', 'JetBrains Mono', Menlo, monospace",
  fontVariantNumeric: "tabular-nums",
}

const pct = (v: number, digits = 1) => `${v >= 0 ? "" : "−"}${Math.abs(v * 100).toFixed(digits)}%`

export default function CalendarReturns({ run, color, benchmarkColor }: {
  run: RunWithSeries | null
  /** The selected strategy's series color elsewhere on the page, so identity stays consistent. */
  color?: string | null
  benchmarkColor?: string | null
}) {
  const monthly = useMemo(() => periodReturns(run, "monthly"), [run])
  const yearly = useMemo(() => periodReturns(run, "yearly"), [run])
  const benchMonthly = useMemo(() => periodReturns(run, "monthly", true), [run])
  const benchYearly = useMemo(() => periodReturns(run, "yearly", true), [run])

  if (!run || monthly.length === 0) return null

  const partial = partialYears(monthly)
  const name = (run.strategy_name ?? "").replace(/_/g, " ")

  return (
    <section style={container}>
      <div style={headerBar}>
        <span style={headerLabel}>Calendar Returns</span>
        <span style={{ ...headerStrategy, ...MONO }}>{name}</span>
      </div>
      <div style={body}>
        <MonthlyHeatmap monthly={monthly} yearly={yearly} benchMonthly={benchMonthly} partial={partial} />
        <YearlyBars yearly={yearly} benchYearly={benchYearly} partial={partial}
                    colors={{ strategy: color ?? COLOR.strategy, benchmark: benchmarkColor ?? COLOR.benchmark }} />
      </div>
    </section>
  )
}

/* ---------------- monthly heatmap ---------------- */

function MonthlyHeatmap({ monthly, yearly, benchMonthly, partial }: {
  monthly: PeriodReturn[]; yearly: PeriodReturn[]; benchMonthly: PeriodReturn[]; partial: Set<number>
}) {
  const [hover, setHover] = useState<{ year: number; month: number; x: number; y: number } | null>(null)

  const byKey = useMemo(() => new Map(monthly.map(p => [`${p.year}-${p.month}`, p.value])), [monthly])
  const benchByKey = useMemo(() => new Map(benchMonthly.map(p => [`${p.year}-${p.month}`, p.value])), [benchMonthly])
  const yearTotal = useMemo(() => new Map(yearly.map(p => [p.year, p.value])), [yearly])
  const years = useMemo(() => [...new Set(monthly.map(p => p.year))].sort((a, b) => b - a), [monthly])

  // Symmetric scale: 90th percentile of |monthly return|, rounded up to 1%, kept within 3%..15%.
  const cap = useMemo(() => {
    const abs = monthly.map(p => Math.abs(p.value)).sort((a, b) => a - b)
    const p90 = abs[Math.floor(0.9 * (abs.length - 1))] ?? 0.03
    return Math.min(0.15, Math.max(0.03, Math.ceil(p90 * 100) / 100))
  }, [monthly])

  const hovered = hover ? byKey.get(`${hover.year}-${hover.month}`) : undefined
  const hoveredBench = hover ? benchByKey.get(`${hover.year}-${hover.month}`) : undefined

  return (
    <div style={card}>
      <div style={cardHead}>
        <div style={cardTitle}>Monthly returns <span style={cardMeta}>%, newest year first</span></div>
        <ScaleLegend cap={cap} />
      </div>
      <div style={{ position: "relative" }} onMouseLeave={() => setHover(null)}>
        <div style={scroller}>
          <table style={heatTable}>
            <thead>
              <tr>
                <th style={{ ...heatTh, textAlign: "left" }}>Year</th>
                {MONTHS.map(m => <th key={m} style={heatTh}>{m}</th>)}
                <th style={{ ...heatTh, paddingLeft: 10 }}>Total</th>
              </tr>
            </thead>
            <tbody>
              {years.map(year => (
                <tr key={year}>
                  <td style={{ ...yearCell, ...MONO }}>{year}{partial.has(year) ? "*" : ""}</td>
                  {MONTHS.map((_, i) => {
                    const month = i + 1
                    const v = byKey.get(`${year}-${month}`)
                    if (v === undefined) return <td key={month} style={emptyCell} />
                    const fill = divergingColor(v, cap)
                    return (
                      <td
                        key={month}
                        style={{ ...heatCell, ...MONO, background: fill, color: inkFor(fill) }}
                        onMouseEnter={e => {
                          const cell = e.currentTarget.getBoundingClientRect()
                          const box = e.currentTarget.closest("table")!.parentElement!.parentElement!.getBoundingClientRect()
                          setHover({ year, month, x: cell.left - box.left + cell.width / 2, y: cell.top - box.top })
                        }}
                      >
                        {(v * 100).toFixed(1)}
                      </td>
                    )
                  })}
                  <td style={{ ...totalCell, ...MONO }}>
                    {yearTotal.has(year) ? pct(yearTotal.get(year)!) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {hover && hovered !== undefined && (
          <div style={{ ...tooltip, left: hover.x, top: hover.y }} role="status">
            <div style={tooltipTitle}>{MONTHS[hover.month - 1]} {hover.year}</div>
            <div style={tooltipRow}><span>Strategy</span><span style={MONO}>{pct(hovered, 2)}</span></div>
            {hoveredBench !== undefined && (
              <>
                <div style={tooltipRow}><span>Benchmark</span><span style={MONO}>{pct(hoveredBench, 2)}</span></div>
                <div style={tooltipRow}><span>Difference</span><span style={MONO}>{pct(hovered - hoveredBench, 2)}</span></div>
              </>
            )}
          </div>
        )}
      </div>
      {partial.size > 0 && <div style={foot}>* Partial year: the backtest starts or ends inside it, so its total covers only the months shown.</div>}
    </div>
  )
}

function ScaleLegend({ cap }: { cap: number }) {
  const stops = [-1, -0.5, 0, 0.5, 1].map(t => `${divergingColor(t * cap, cap)} ${((t + 1) / 2) * 100}%`)
  return (
    <div style={legendWrap} aria-label={`Color scale from ${pct(-cap, 0)} to ${pct(cap, 0)}`}>
      <span style={{ ...legendLabel, ...MONO }}>{pct(-cap, 0)}</span>
      <span style={{ ...legendBar, background: `linear-gradient(to right, ${stops.join(", ")})` }} />
      <span style={{ ...legendLabel, ...MONO }}>+{pct(cap, 0)}</span>
    </div>
  )
}

/* ---------------- yearly bars ---------------- */

function YearlyBars({ yearly, benchYearly, partial, colors }: {
  yearly: PeriodReturn[]; benchYearly: PeriodReturn[]; partial: Set<number>
  colors: { strategy: string; benchmark: string }
}) {
  const data = useMemo(() => {
    const bench = new Map(benchYearly.map(p => [p.year, p.value]))
    return yearly
      .map(p => ({ year: `${p.year}${partial.has(p.year) ? "*" : ""}`, strategy: p.value, benchmark: bench.get(p.year) ?? null }))
      .sort((a, b) => a.year.localeCompare(b.year))
  }, [yearly, benchYearly, partial])
  const hasBenchmark = data.some(d => d.benchmark !== null)

  return (
    <div style={card}>
      <div style={cardHead}>
        <div style={cardTitle}>Calendar-year returns</div>
        <div style={legendWrap}>
          <LegendKey color={colors.strategy} label="Strategy" />
          {hasBenchmark && <LegendKey color={colors.benchmark} label="Benchmark" />}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barGap={2} barCategoryGap="22%">
          <CartesianGrid vertical={false} stroke={COLOR.grid} />
          <XAxis dataKey="year" tick={{ fill: COLOR.inkSecondary, fontSize: 10 }} tickLine={false}
                 axisLine={false} interval="preserveStartEnd" minTickGap={6} />
          <YAxis tickFormatter={v => `${Math.round(v * 100)}%`} tick={{ fill: COLOR.inkSecondary, fontSize: 10 }}
                 tickLine={false} axisLine={false} width={40} />
          <ReferenceLine y={0} stroke={COLOR.baseline} />
          <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} content={<YearTooltip colors={colors} />} />
          <Bar dataKey="strategy" name="Strategy" fill={colors.strategy} shape={<RoundedEndBar />} isAnimationActive={false} />
          {hasBenchmark && (
            <Bar dataKey="benchmark" name="Benchmark" fill={colors.benchmark} shape={<RoundedEndBar />} isAnimationActive={false} />
          )}
        </BarChart>
      </ResponsiveContainer>
      {partial.size > 0 && <div style={foot}>* Partial year.</div>}
    </div>
  )
}

function LegendKey({ color, label }: { color: string; label: string }) {
  return (
    <span style={legendKey}>
      <span style={{ ...legendSwatch, background: color }} aria-hidden />
      {label}
    </span>
  )
}

function YearTooltip({ active, payload, label, colors }: {
  active?: boolean; payload?: { payload: YearRow }[]; label?: string; colors: { strategy: string; benchmark: string }
}) {
  if (!active || !payload?.length) return null
  const row = payload[0].payload
  return (
    <div style={{ ...tooltip, position: "static", transform: "none" }}>
      <div style={tooltipTitle}>{label}</div>
      <div style={tooltipRow}><span><LegendKey color={colors.strategy} label="Strategy" /></span><span style={MONO}>{pct(row.strategy, 2)}</span></div>
      {row.benchmark !== null && (
        <>
          <div style={tooltipRow}><span><LegendKey color={colors.benchmark} label="Benchmark" /></span><span style={MONO}>{pct(row.benchmark, 2)}</span></div>
          <div style={tooltipRow}><span>Difference</span><span style={MONO}>{pct(row.strategy - row.benchmark, 2)}</span></div>
        </>
      )}
    </div>
  )
}

/** Bar with 4px rounded corners on the end away from the zero baseline (square at the baseline). */
function RoundedEndBar(props: { x?: number; y?: number; width?: number; height?: number; fill?: string; value?: number | null }) {
  const { x = 0, y = 0, width, height, fill, value } = props
  if (value == null || !width || !height) return null
  const top = Math.min(y, y + height)
  const h = Math.abs(height)
  const r = Math.min(4, width / 2, h)
  const up = value >= 0
  const path = up
    ? `M${x},${top + h} L${x},${top + r} Q${x},${top} ${x + r},${top} L${x + width - r},${top} Q${x + width},${top} ${x + width},${top + r} L${x + width},${top + h} Z`
    : `M${x},${top} L${x + width},${top} L${x + width},${top + h - r} Q${x + width},${top + h} ${x + width - r},${top + h} L${x + r},${top + h} Q${x},${top + h} ${x},${top + h - r} Z`
  return <path d={path} fill={fill} />
}

/* ---------------- color helpers (OKLab interpolation) ---------------- */

function divergingColor(value: number, cap: number): string {
  const t = Math.max(-1, Math.min(1, value / cap))
  return mixOklab(COLOR.neutral, t >= 0 ? COLOR.positive : COLOR.negative, Math.abs(t))
}

/** Dark ink on light fills, light ink on dark fills (WCAG relative luminance threshold). */
function inkFor(hex: string): string {
  const [r, g, b] = hexToLinear(hex)
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.18 ? COLOR.inkOnLight : COLOR.inkOnDark
}

function hexToLinear(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255].map(c => {
    const s = c / 255
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }) as [number, number, number]
}

function linearToHex([r, g, b]: number[]): string {
  return "#" + [r, g, b].map(c => {
    const s = c <= 0.0031308 ? 12.92 * c : 1.055 * Math.max(c, 0) ** (1 / 2.4) - 0.055
    return Math.round(Math.max(0, Math.min(1, s)) * 255).toString(16).padStart(2, "0")
  }).join("")
}

function toOklab([r, g, b]: number[]): number[] {
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
  return [
    0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s,
  ]
}

function fromOklab([L, a, b]: number[]): number[] {
  const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
  const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
  const s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
  return [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
  ]
}

function mixOklab(from: string, to: string, t: number): string {
  const a = toOklab(hexToLinear(from))
  const b = toOklab(hexToLinear(to))
  return linearToHex(fromOklab(a.map((v, i) => v + (b[i] - v) * t)))
}

/* ---------------- styles ---------------- */

const container: CSSProperties = {
  background: "#161b22", borderRadius: 8, border: "1px solid #2a2f3a", overflow: "hidden", marginTop: 16,
}
const headerBar: CSSProperties = {
  background: "#0d1117", borderBottom: "1px solid #2a2f3a", padding: "10px 16px",
  display: "flex", alignItems: "center", justifyContent: "space-between",
}
const headerLabel: CSSProperties = { fontSize: 12, fontWeight: 600, color: COLOR.inkPrimary, letterSpacing: "0.3px" }
const headerStrategy: CSSProperties = { fontSize: 11, color: COLOR.inkSecondary }
const body: CSSProperties = {
  display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(440px, 1fr))", gap: 12, padding: "14px 16px",
}
const card: CSSProperties = { border: "1px solid #21262d", borderRadius: 6, padding: "12px 14px", minWidth: 0 }
const cardHead: CSSProperties = {
  display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 10,
}
const cardTitle: CSSProperties = { fontSize: 11, fontWeight: 600, color: COLOR.inkPrimary }
const cardMeta: CSSProperties = { fontWeight: 400, color: COLOR.inkSecondary, fontSize: 10, marginLeft: 6 }
const foot: CSSProperties = { fontSize: 10, color: COLOR.inkSecondary, marginTop: 8, lineHeight: 1.5 }

const scroller: CSSProperties = { overflowX: "auto", maxHeight: 420, overflowY: "auto", colorScheme: "dark" }
const heatTable: CSSProperties = { borderCollapse: "separate", borderSpacing: 2, width: "100%", minWidth: 480 }
const heatTh: CSSProperties = {
  fontSize: 9.5, fontWeight: 600, color: COLOR.inkSecondary, textAlign: "center",
  padding: "0 0 4px", position: "sticky", top: 0, background: "#161b22",
}
const heatCell: CSSProperties = {
  fontSize: 10, textAlign: "center", padding: "4px 2px", borderRadius: 2, cursor: "default", minWidth: 28,
}
const emptyCell: CSSProperties = { padding: "4px 2px" }
const yearCell: CSSProperties = { fontSize: 10.5, color: COLOR.inkSecondary, paddingRight: 6, whiteSpace: "nowrap" }
const totalCell: CSSProperties = {
  fontSize: 10.5, fontWeight: 600, color: COLOR.inkPrimary, textAlign: "right", paddingLeft: 10, whiteSpace: "nowrap",
}

const legendWrap: CSSProperties = { display: "flex", alignItems: "center", gap: 10 }
const legendLabel: CSSProperties = { fontSize: 9.5, color: COLOR.inkSecondary }
const legendBar: CSSProperties = { width: 96, height: 8, borderRadius: 2 }
const legendKey: CSSProperties = { display: "inline-flex", alignItems: "center", gap: 5, fontSize: 10.5, color: COLOR.inkSecondary }
const legendSwatch: CSSProperties = { width: 8, height: 8, borderRadius: 2, flexShrink: 0 }

const tooltip: CSSProperties = {
  position: "absolute", transform: "translate(-50%, calc(-100% - 6px))", pointerEvents: "none", zIndex: 5,
  background: "#0d1117", border: "1px solid #30363d", borderRadius: 6, padding: "8px 10px",
  boxShadow: "0 4px 16px rgba(0,0,0,0.5)", minWidth: 150,
}
const tooltipTitle: CSSProperties = { fontSize: 11, fontWeight: 600, color: COLOR.inkPrimary, marginBottom: 4 }
const tooltipRow: CSSProperties = {
  display: "flex", justifyContent: "space-between", gap: 14, fontSize: 10.5, color: COLOR.inkSecondary, lineHeight: 1.7,
}
