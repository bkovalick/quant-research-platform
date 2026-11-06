import { useMemo, useState } from "react"
import type { CSSProperties } from "react"
import {
  ResponsiveContainer, ScatterChart, Scatter, ComposedChart, Bar, Line, Cell,
  XAxis, YAxis, CartesianGrid, ReferenceLine, Tooltip,
} from "recharts"
import { deserializeToArray } from "../utils/metricsUtils"
import { histogram, qqPoints, standardize } from "../utils/distribution"
import type { HistogramBin, QQPoint } from "../utils/distribution"
import { periodReturns } from "../utils/periodReturns"
import type { RunWithSeries } from "../utils/periodReturns"

/**
 * Return distribution for the selected run:
 *  - Q-Q plot of standardized returns against the normal distribution. Points on
 *    the dashed line = normal; tails bending away from it = fat tails / skew.
 *  - Histogram of calendar-month returns with the normal curve of the same mean
 *    and sd overlaid. Bars use the same diverging poles as the monthly heatmap.
 *  - 12-month risk: normal model vs. the strategy's own rolling 12-month returns,
 *    as PDF / CDF / inverse CDF, with VaR and probability of loss for both.
 */

const COLOR = {
  positive: "#3987e5",
  negative: "#e66767",
  fallbackSeries: "#3987e5",
  reference: "#8b949e",
  surface: "#161b22",
  inkPrimary: "#e6edf3",
  inkSecondary: "#8b949e",
  grid: "#21262d",
  baseline: "#484f58",
}

const MONO: CSSProperties = {
  fontFamily: "ui-monospace, 'SF Mono', 'JetBrains Mono', Menlo, monospace",
  fontVariantNumeric: "tabular-nums",
}

const pct = (v: number, digits = 1) => `${v >= 0 ? "" : "−"}${Math.abs(v * 100).toFixed(digits)}%`
const num = (v: number, digits = 2) => `${v >= 0 ? "" : "−"}${Math.abs(v).toFixed(digits)}`

interface Props {
  run: (RunWithSeries & { result?: { summary?: Record<string, number> } }) | null
  /** The strategy's series color elsewhere on the page. */
  color?: string | null
}

export default function ReturnDistribution({ run, color }: Props) {
  const series = useMemo(() => run?.result?.series ?? {}, [run])
  const returns = useMemo(() => deserializeToArray(series.portfolio_returns), [series])
  const z = useMemo(() => {
    const backend = deserializeToArray(series.standardized_returns)
    return backend.length ? backend : standardize(returns)     // older runs: compute here
  }, [series, returns])
  const qq = useMemo(() => qqPoints(z), [z])
  const monthly = useMemo(() => periodReturns(run, "monthly").map(p => p.value), [run])
  const bins = useMemo(() => histogram(monthly), [monthly])

  if (!run || (qq.length === 0 && bins.length === 0 && returns.length === 0)) return null
  const summary = run.result?.summary ?? {}
  const returnByDate = new Map(returns.map(p => [p.date, p.value]))

  return (
    <section style={container}>
      <div style={headerBar}>
        <span style={headerLabel}>Return Distribution</span>
        <span style={{ ...headerStrategy, ...MONO }}>{(run.strategy_name ?? "").replace(/_/g, " ")}</span>
      </div>
      <div style={body}>
        <QQCard points={qq} color={color ?? COLOR.fallbackSeries} returnByDate={returnByDate}
                skew={summary.skewness} kurtosis={summary.kurtosis} />
        <HistogramCard bins={bins} values={monthly} />
        <RiskCutoffCard returns={returns} color={color ?? COLOR.fallbackSeries} />
      </div>
    </section>
  )
}

/* ---------------- Q-Q plot ---------------- */

function QQCard({ points, color, returnByDate, skew, kurtosis }: {
  points: QQPoint[]; color: string; returnByDate: Map<string, number>; skew?: number; kurtosis?: number
}) {
  const xMax = Math.ceil(Math.max(3, ...points.map(p => Math.abs(p.theoretical))))
  const yMax = Math.ceil(Math.max(3, ...points.map(p => Math.abs(p.sample))))
  const lineEnd = Math.min(xMax, yMax)

  return (
    <div style={card}>
      <div style={cardHead}>
        <div style={cardTitle}>Q-Q plot vs normal <span style={cardMeta}>standardized per-period returns</span></div>
        <div style={legendWrap}>
          <LegendKey swatch={<span style={{ ...dot, background: color }} />} label="Returns" />
          <LegendKey swatch={<span style={dashSwatch} />} label="Normal" />
        </div>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <ScatterChart margin={{ top: 8, right: 12, bottom: 18, left: 0 }}>
          <CartesianGrid stroke={COLOR.grid} />
          <XAxis type="number" dataKey="theoretical" domain={[-xMax, xMax]} tickCount={2 * xMax + 1}
                 tick={{ fill: COLOR.inkSecondary, fontSize: 10 }} tickLine={false} axisLine={{ stroke: COLOR.baseline }}
                 label={{ value: "Normal quantile (z)", position: "insideBottom", offset: -10, fill: COLOR.inkSecondary, fontSize: 10 }} />
          <YAxis type="number" dataKey="sample" domain={[-yMax, yMax]} allowDataOverflow
                 tick={{ fill: COLOR.inkSecondary, fontSize: 10 }} tickLine={false} axisLine={{ stroke: COLOR.baseline }} width={34}
                 label={{ value: "Sample (z)", angle: -90, position: "insideLeft", offset: 12, fill: COLOR.inkSecondary, fontSize: 10 }} />
          <ReferenceLine segment={[{ x: -lineEnd, y: -lineEnd }, { x: lineEnd, y: lineEnd }]}
                         stroke={COLOR.reference} strokeWidth={2} strokeDasharray="5 4" ifOverflow="hidden" />
          <Tooltip cursor={false} content={<QQTooltip returnByDate={returnByDate} />} />
          <Scatter data={points} fill={color} isAnimationActive={false}
                   shape={(p: { cx?: number; cy?: number }) => (
                     <circle cx={p.cx} cy={p.cy} r={3.5} fill={color} stroke={COLOR.surface} strokeWidth={1} />
                   )} />
        </ScatterChart>
      </ResponsiveContainer>
      <div style={foot}>
        {skew != null && kurtosis != null && (
          <span style={MONO}>skew {num(skew)} · excess kurtosis {num(kurtosis)} · </span>
        )}
        Points below the line on the left, or above it on the right, mean bigger moves than a normal
        distribution predicts (fat tails). Long daily series are thinned in the middle; every tail point is shown.
      </div>
    </div>
  )
}

function QQTooltip({ active, payload, returnByDate }: {
  active?: boolean; payload?: { payload: QQPoint }[]; returnByDate: Map<string, number>
}) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  const raw = returnByDate.get(p.date)
  return (
    <div style={tooltip}>
      <div style={tooltipTitle}>{p.date.slice(0, 10)}</div>
      {raw !== undefined && <div style={tooltipRow}><span>Return</span><span style={MONO}>{pct(raw, 2)}</span></div>}
      <div style={tooltipRow}><span>Sample z</span><span style={MONO}>{num(p.sample)}</span></div>
      <div style={tooltipRow}><span>Normal z</span><span style={MONO}>{num(p.theoretical)}</span></div>
    </div>
  )
}

/* ---------------- monthly histogram ---------------- */

function HistogramCard({ bins, values }: { bins: HistogramBin[]; values: number[] }) {
  const stats = useMemo(() => {
    if (values.length < 2) return null
    const mean = values.reduce((s, x) => s + x, 0) / values.length
    const sd = Math.sqrt(values.reduce((s, x) => s + (x - mean) ** 2, 0) / (values.length - 1))
    const up = values.filter(v => v > 0).length
    return { n: values.length, mean, sd, worst: Math.min(...values), best: Math.max(...values), up }
  }, [values])
  const data = bins.map(b => ({ ...b, label: pct(b.start, b.end - b.start < 0.01 ? 1 : 0) }))

  return (
    <div style={card}>
      <div style={cardHead}>
        <div style={cardTitle}>Monthly return distribution <span style={cardMeta}>months per bin</span></div>
        <div style={legendWrap}>
          <LegendKey swatch={<span style={{ ...square, background: COLOR.negative }} />} label="Down" />
          <LegendKey swatch={<span style={{ ...square, background: COLOR.positive }} />} label="Up" />
          <LegendKey swatch={<span style={dashSwatch} />} label="Normal fit" />
        </div>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 18, left: 0 }} barCategoryGap={2}>
          <CartesianGrid vertical={false} stroke={COLOR.grid} />
          <XAxis dataKey="label" tick={{ fill: COLOR.inkSecondary, fontSize: 10 }} tickLine={false}
                 axisLine={{ stroke: COLOR.baseline }} interval="preserveStartEnd" minTickGap={10}
                 label={{ value: "Monthly return (bin start)", position: "insideBottom", offset: -10, fill: COLOR.inkSecondary, fontSize: 10 }} />
          <YAxis allowDecimals={false} tick={{ fill: COLOR.inkSecondary, fontSize: 10 }} tickLine={false}
                 axisLine={false} width={30} />
          <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} content={<BinTooltip total={values.length} />} />
          <Bar dataKey="count" isAnimationActive={false} radius={[3, 3, 0, 0]}>
            {data.map(b => <Cell key={b.start} fill={b.mid < 0 ? COLOR.negative : COLOR.positive} />)}
          </Bar>
          <Line dataKey="expected" type="monotone" stroke={COLOR.reference} strokeWidth={2} strokeDasharray="5 4"
                dot={false} activeDot={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
      {stats && (
        <div style={{ ...foot, ...MONO }}>
          {stats.n} months · {stats.up} up ({Math.round((100 * stats.up) / stats.n)}%) · mean {pct(stats.mean, 2)} ·
          sd {pct(stats.sd, 2)} · worst {pct(stats.worst)} · best {pct(stats.best)}
        </div>
      )}
    </div>
  )
}

function BinTooltip({ active, payload, total }: {
  active?: boolean; payload?: { payload: HistogramBin }[]; total: number
}) {
  if (!active || !payload?.length) return null
  const b = payload[0].payload
  return (
    <div style={tooltip}>
      <div style={tooltipTitle}>{pct(b.start)} to {pct(b.end)}</div>
      <div style={tooltipRow}><span>Months</span><span style={MONO}>{b.count} ({Math.round((100 * b.count) / total)}%)</span></div>
      <div style={tooltipRow}><span>Normal fit</span><span style={MONO}>{b.expected.toFixed(1)}</span></div>
    </div>
  )
}

/* ---------------- 12-month risk cutoffs ---------------- */

type RiskView = "pdf" | "cdf" | "quantile"

const RISK_TAIL = 0.05   // 95% VaR

function RiskCutoffCard({ returns, color }: { returns: { date: string; value: number }[]; color: string }) {
  const [view, setView] = useState<RiskView>("cdf")
  const [muOverride, setMu] = useState<number | null>(null)
  const [sdOverride, setSd] = useState<number | null>(null)

  const ppy = useMemo(() => periodsPerYear(returns.map(p => p.date)), [returns])
  const values = useMemo(() => returns.map(p => p.value).filter(v => Number.isFinite(v) && v > -1), [returns])
  const est = useMemo(() => annualize(values, ppy), [values, ppy])
  const empirical = useMemo(() => rollingCompounded(values, ppy).sort((a, b) => a - b), [values, ppy])

  const mu = muOverride ?? est.mu
  const sd = Math.max(sdOverride ?? est.sd, 0.005)

  const stats = useMemo(() => {
    const modelCut = mu + sd * normInv(RISK_TAIL)
    const empCut = quantileSorted(empirical, RISK_TAIL)
    return {
      modelCut, empCut,
      modelLoss: normCdf(0, mu, sd),
      empLoss: empirical.length ? empirical.filter(x => x < 0).length / empirical.length : NaN,
    }
  }, [mu, sd, empirical])

  const [xMin, xMax] = useMemo(() => {
    const lo = Math.min(mu - 3.5 * sd, empirical[0] ?? Infinity)
    const hi = Math.max(mu + 3.5 * sd, empirical[empirical.length - 1] ?? -Infinity)
    return [Math.floor(lo * 10) / 10, Math.ceil(hi * 10) / 10]
  }, [mu, sd, empirical])

  const isQ = view === "quantile"
  const xTicks = useMemo(() => {
    if (isQ) return [0, 0.25, 0.5, 0.75, 1]
    const step = xMax - xMin > 1 ? 0.2 : 0.1
    const out: number[] = []
    for (let t = Math.ceil(xMin / step) * step; t <= xMax + 1e-9; t += step) out.push(Math.round(t * 100) / 100)
    return out
  }, [isQ, xMin, xMax])

  const data = useMemo(() => {
    if (isQ) {
      return Array.from({ length: 99 }, (_, i) => {
        const p = (i + 1) / 100
        return { x: p, model: mu + sd * normInv(p), empirical: empirical.length ? quantileSorted(empirical, p) : null }
      })
    }
    const N = 160, step = (xMax - xMin) / N
    const nb = 40, bw = (xMax - xMin) / nb
    const counts = new Array(nb).fill(0)
    empirical.forEach(x => { counts[Math.min(nb - 1, Math.max(0, Math.floor((x - xMin) / bw)))]++ })
    let j = 0
    return Array.from({ length: N + 1 }, (_, i) => {
      const x = xMin + i * step
      if (view === "pdf") {
        const k = Math.min(nb - 1, Math.max(0, Math.floor((x - xMin) / bw)))
        return { x, model: normPdf(x, mu, sd), empirical: empirical.length ? counts[k] / (empirical.length * bw) : null }
      }
      while (j < empirical.length && empirical[j] <= x) j++
      return { x, model: normCdf(x, mu, sd), empirical: empirical.length ? j / empirical.length : null }
    })
  }, [view, isQ, mu, sd, xMin, xMax, empirical])

  if (values.length < ppy) return null   // need at least a year of history

  const yFmt = (v: number) => (view === "pdf" ? v.toFixed(1) : pct(v, 0))

  return (
    <div style={{ ...card, gridColumn: "1 / -1" }}>
      <div style={cardHead}>
        <div style={cardTitle}>
          12-month risk <span style={cardMeta}>normal model vs. actual rolling 12-month returns · 95% VaR</span>
        </div>
        <div style={legendWrap}>
          <LegendKey swatch={<span style={{ ...dashSwatch, borderTopStyle: "solid", borderTopColor: COLOR.reference }} />} label="Normal" />
          <LegendKey swatch={<span style={{ ...dashSwatch, borderTopStyle: "solid", borderTopColor: color }} />} label="Actual" />
          <LegendKey swatch={<span style={{ ...dashSwatch, borderTopColor: COLOR.negative }} />} label="5% cutoff" />
        </div>
      </div>

      <div style={riskStats}>
        <RiskStat label="VaR · normal" value={pct(-stats.modelCut)} />
        <RiskStat label="VaR · actual" value={pct(-stats.empCut)} accent={color} />
        <RiskStat label="P(loss) · normal" value={pct(stats.modelLoss)} />
        <RiskStat label="P(loss) · actual" value={pct(stats.empLoss)} accent={color} />
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 18, left: 0 }}>
          <CartesianGrid stroke={COLOR.grid} />
          <XAxis dataKey="x" type="number" domain={isQ ? [0, 1] : [xMin, xMax]} ticks={xTicks}
                 tickFormatter={v => pct(v, 0)} tick={{ fill: COLOR.inkSecondary, fontSize: 10 }} tickLine={false}
                 axisLine={{ stroke: COLOR.baseline }}
                 label={{ value: isQ ? "Cumulative probability" : "12-month return", position: "insideBottom", offset: -10, fill: COLOR.inkSecondary, fontSize: 10 }} />
          <YAxis tick={{ fill: COLOR.inkSecondary, fontSize: 10 }} tickLine={false} axisLine={false} width={40}
                 tickFormatter={isQ ? (v: number) => pct(v, 0) : yFmt}
                 domain={view === "cdf" ? [0, 1] : ["auto", "auto"]} />
          <Tooltip cursor={{ stroke: COLOR.baseline }} content={<RiskTooltip view={view} />} />

          {view === "pdf"
            ? <Bar dataKey="empirical" fill={color} fillOpacity={0.35} isAnimationActive={false} barSize={4} />
            : <Line dataKey="empirical" stroke={color} strokeWidth={2} dot={false} activeDot={false}
                    type={view === "cdf" ? "stepAfter" : "monotone"} isAnimationActive={false} connectNulls />}
          <Line dataKey="model" stroke={COLOR.reference} strokeWidth={2} dot={false} activeDot={false}
                type="monotone" isAnimationActive={false} />

          {isQ ? (
            <>
              <ReferenceLine y={0} stroke={COLOR.baseline} />
              <ReferenceLine x={RISK_TAIL} stroke={COLOR.negative} strokeDasharray="5 4" />
            </>
          ) : (
            <>
              <ReferenceLine x={0} stroke={COLOR.baseline} />
              <ReferenceLine x={stats.modelCut} stroke={COLOR.negative} strokeDasharray="5 4" />
            </>
          )}
        </ComposedChart>
      </ResponsiveContainer>

      <div style={riskControls}>
        <div style={tabs}>
          {([["pdf", "Likelihood (PDF)"], ["cdf", "Cumulative (CDF)"], ["quantile", "Risk cutoffs (inverse CDF)"]] as [RiskView, string][])
            .map(([k, label]) => (
              <button key={k} onClick={() => setView(k)} style={k === view ? { ...tab, ...tabOn, background: color } : tab}>{label}</button>
            ))}
        </div>
        <RiskSlider label="Expected return" value={mu} min={-0.2} max={0.4} color={color}
                    onChange={setMu} onReset={muOverride !== null ? () => setMu(null) : undefined} />
        <RiskSlider label="Volatility" value={sd} min={0.01} max={0.6} color={color}
                    onChange={setSd} onReset={sdOverride !== null ? () => setSd(null) : undefined} />
      </div>
      <div style={foot}>
        Normal curve starts at the strategy's annualized mean and volatility; drag the sliders to stress it.
        Actual returns are overlapping 12-month windows ({empirical.length} of them), so they aren't independent
        and the tails are only as rich as the history.
      </div>
    </div>
  )
}

function RiskStat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div style={{ minWidth: 96 }}>
      <div style={{ fontSize: 10, color: COLOR.inkSecondary }}>{label}</div>
      <div style={{ ...MONO, fontSize: 16, color: accent ?? COLOR.inkPrimary }}>{value}</div>
    </div>
  )
}

function RiskSlider({ label, value, min, max, color, onChange, onReset }: {
  label: string; value: number; min: number; max: number; color: string
  onChange: (v: number) => void; onReset?: () => void
}) {
  return (
    <label style={{ flex: 1, minWidth: 180, fontSize: 10.5, color: COLOR.inkSecondary }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
        <span>{label}</span>
        <span style={{ ...MONO, color: COLOR.inkPrimary }}>
          {pct(value)}
          {onReset && <button onClick={e => { e.preventDefault(); onReset() }} style={resetBtn}>reset</button>}
        </span>
      </div>
      <input type="range" min={min} max={max} step={0.005} value={value}
             onChange={e => onChange(parseFloat(e.target.value))} style={{ width: "100%", accentColor: color }} />
    </label>
  )
}

function RiskTooltip({ active, payload, label, view }: {
  active?: boolean; payload?: { dataKey: string; value: number | null }[]; label?: number; view: RiskView
}) {
  if (!active || !payload?.length || label == null) return null
  const fmt = (v: number) => (view === "pdf" ? v.toFixed(2) : pct(v, 1))
  return (
    <div style={tooltip}>
      <div style={tooltipTitle}>{view === "quantile" ? `p = ${pct(label, 0)}` : `12-month return ${pct(label)}`}</div>
      {payload.filter(p => p.value != null).map(p => (
        <div key={p.dataKey} style={tooltipRow}>
          <span>{p.dataKey === "model" ? "Normal" : "Actual"}</span><span style={MONO}>{fmt(p.value as number)}</span>
        </div>
      ))}
    </div>
  )
}

/* ---------------- risk math ---------------- */

/** Infer periods per year from the median gap between observation dates. */
function periodsPerYear(dates: string[]): number {
  if (dates.length < 3) return 252
  const t = dates.map(d => Date.parse(d)).filter(Number.isFinite)
  const gaps = t.slice(1).map((x, i) => (x - t[i]) / 86_400_000).sort((a, b) => a - b)
  const median = gaps[Math.floor(gaps.length / 2)]
  return median <= 3 ? 252 : median <= 10 ? 52 : 12
}

function annualize(values: number[], ppy: number) {
  if (values.length < 2) return { mu: 0, sd: 0 }
  const m = values.reduce((s, x) => s + x, 0) / values.length
  const v = values.reduce((s, x) => s + (x - m) ** 2, 0) / (values.length - 1)
  return { mu: m * ppy, sd: Math.sqrt(v * ppy) }
}

/** Overlapping compounded returns over `n` periods. */
function rollingCompounded(values: number[], n: number): number[] {
  if (values.length < n) return []
  const logs = values.map(Math.log1p)
  const out: number[] = []
  let s = 0
  for (let i = 0; i < logs.length; i++) {
    s += logs[i]
    if (i >= n) s -= logs[i - n]
    if (i >= n - 1) out.push(Math.expm1(s))
  }
  return out
}

function quantileSorted(sorted: number[], p: number): number {
  if (!sorted.length) return NaN
  const idx = p * (sorted.length - 1), lo = Math.floor(idx), hi = Math.ceil(idx)
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo)
}

function erf(x: number): number {   // Abramowitz & Stegun 7.1.26
  const s = Math.sign(x), a = Math.abs(x), t = 1 / (1 + 0.3275911 * a)
  return s * (1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-a * a))
}
const normCdf = (x: number, mu: number, sd: number) => 0.5 * (1 + erf((x - mu) / (sd * Math.SQRT2)))
const normPdf = (x: number, mu: number, sd: number) => Math.exp(-0.5 * ((x - mu) / sd) ** 2) / (sd * Math.sqrt(2 * Math.PI))

function normInv(p: number): number {   // Acklam's approximation
  const a = [-39.69683028665376, 220.9460984245205, -275.9285104469687, 138.357751867269, -30.66479806614716, 2.506628277459239]
  const b = [-54.47609879822406, 161.5858368580409, -155.6989798598866, 66.80131188771972, -13.28068155288572]
  const c = [-0.007784894002430293, -0.3223964580411365, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783]
  const d = [0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416]
  if (p <= 0) return -Infinity
  if (p >= 1) return Infinity
  const tailPoly = (q: number) =>
    (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
  if (p < 0.02425) return tailPoly(Math.sqrt(-2 * Math.log(p)))
  if (p > 0.97575) return -tailPoly(Math.sqrt(-2 * Math.log(1 - p)))
  const q = p - 0.5, r = q * q
  return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
}

function LegendKey({ swatch, label }: { swatch: React.ReactNode; label: string }) {
  return <span style={legendKey}>{swatch}{label}</span>
}

/* ---------------- styles ---------------- */

const container: CSSProperties = {
  background: COLOR.surface, borderRadius: 8, border: "1px solid #2a2f3a", overflow: "hidden", marginTop: 16,
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
  display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 6,
}
const cardTitle: CSSProperties = { fontSize: 11, fontWeight: 600, color: COLOR.inkPrimary }
const cardMeta: CSSProperties = { fontWeight: 400, color: COLOR.inkSecondary, fontSize: 10, marginLeft: 6 }
const foot: CSSProperties = { fontSize: 10, color: COLOR.inkSecondary, marginTop: 6, lineHeight: 1.5 }

const legendWrap: CSSProperties = { display: "flex", alignItems: "center", gap: 10 }
const legendKey: CSSProperties = { display: "inline-flex", alignItems: "center", gap: 5, fontSize: 10.5, color: COLOR.inkSecondary }
const dot: CSSProperties = { width: 8, height: 8, borderRadius: "50%", flexShrink: 0 }
const square: CSSProperties = { width: 8, height: 8, borderRadius: 2, flexShrink: 0 }
const dashSwatch: CSSProperties = { width: 14, borderTop: `2px dashed ${COLOR.reference}`, flexShrink: 0 }

const tooltip: CSSProperties = {
  background: "#0d1117", border: "1px solid #30363d", borderRadius: 6, padding: "8px 10px",
  boxShadow: "0 4px 16px rgba(0,0,0,0.5)", minWidth: 140,
}
const tooltipTitle: CSSProperties = { fontSize: 11, fontWeight: 600, color: COLOR.inkPrimary, marginBottom: 4 }
const tooltipRow: CSSProperties = {
  display: "flex", justifyContent: "space-between", gap: 14, fontSize: 10.5, color: COLOR.inkSecondary, lineHeight: 1.7,
}

const riskStats: CSSProperties = { display: "flex", gap: 20, flexWrap: "wrap", margin: "2px 0 8px" }
const riskControls: CSSProperties = { display: "flex", gap: 16, alignItems: "flex-end", flexWrap: "wrap", marginTop: 4 }
const tabs: CSSProperties = { display: "flex", gap: 2, background: "#0d1117", padding: 3, borderRadius: 6, border: "1px solid #21262d" }
const tab: CSSProperties = {
  border: "none", background: "transparent", color: COLOR.inkSecondary, fontSize: 10.5,
  padding: "4px 10px", borderRadius: 4, cursor: "pointer",
}
const tabOn: CSSProperties = { color: "#ffffff" }
const resetBtn: CSSProperties = {
  marginLeft: 6, background: "none", border: "1px solid #30363d", color: COLOR.inkSecondary,
  borderRadius: 3, fontSize: 9.5, padding: "0 4px", cursor: "pointer",
}
