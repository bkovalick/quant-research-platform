/** Distribution helpers for the Q-Q plot and the monthly-return histogram. */

export interface DatedValue { date: string; value: number }
export interface QQPoint { theoretical: number; sample: number; date: string }
export interface HistogramBin { start: number; end: number; mid: number; count: number; expected: number }

/** Inverse standard normal CDF (Acklam's rational approximation, |error| < 1.2e-9). */
export function inverseNormalCdf(p: number): number {
  const a = [-3.969683028665376e1, 2.209460984245205e2, -2.759285104469687e2, 1.38357751867269e2, -3.066479806614716e1, 2.506628277459239]
  const b = [-5.447609879822406e1, 1.615858368580409e2, -1.556989798598866e2, 6.680131188771972e1, -1.328068155288572e1]
  const c = [-7.784894002430293e-3, -3.223964580411365e-1, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783]
  const d = [7.784695709041462e-3, 3.224671290700398e-1, 2.445134137142996, 3.754408661907416]
  const low = 0.02425
  if (p <= 0 || p >= 1) return p <= 0 ? -Infinity : Infinity
  if (p < low) {
    const q = Math.sqrt(-2 * Math.log(p))
    return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
  }
  if (p > 1 - low) return -inverseNormalCdf(1 - p)
  const q = p - 0.5
  const r = q * q
  return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q /
    (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
}

export function normalPdf(x: number, mean = 0, sd = 1): number {
  const z = (x - mean) / sd
  return Math.exp(-0.5 * z * z) / (sd * Math.sqrt(2 * Math.PI))
}

/** z-score a return series (used when a run predates the backend's standardized_returns). */
export function standardize(points: DatedValue[]): DatedValue[] {
  const v = points.map(p => p.value).filter(Number.isFinite)
  if (v.length < 3) return []
  const mean = v.reduce((s, x) => s + x, 0) / v.length
  const sd = Math.sqrt(v.reduce((s, x) => s + (x - mean) ** 2, 0) / (v.length - 1))
  if (sd === 0) return []
  return points.filter(p => Number.isFinite(p.value)).map(p => ({ date: p.date, value: (p.value - mean) / sd }))
}

/**
 * Q-Q points: sorted sample z-scores against standard normal quantiles at the
 * (i - 0.5) / n plotting positions. Long daily series are thinned in the body
 * (every k-th point) but every point beyond |theoretical| > 2 is kept, since the
 * tails are what the plot is for.
 */
export function qqPoints(z: DatedValue[], maxBodyPoints = 300): QQPoint[] {
  const sorted = z.filter(p => Number.isFinite(p.value)).sort((a, b) => a.value - b.value)
  const n = sorted.length
  if (n < 3) return []
  const all = sorted.map((p, i) => ({ theoretical: inverseNormalCdf((i + 0.5) / n), sample: p.value, date: p.date }))
  const body = all.filter(p => Math.abs(p.theoretical) <= 2)
  const step = Math.max(1, Math.ceil(body.length / maxBodyPoints))
  return all.filter((p, i) => Math.abs(p.theoretical) > 2 || i % step === 0)
}

/**
 * Histogram with "nice" bin widths (0.25%, 0.5%, 1%, 2%, 2.5%, 5%, ...) and an
 * expected count per bin from a normal distribution with the sample's mean and sd.
 * Bin edges are aligned to 0 so no bin straddles the zero line.
 */
export function histogram(values: number[], targetBins = 20): HistogramBin[] {
  const v = values.filter(Number.isFinite)
  if (v.length < 2) return []
  const min = Math.min(...v)
  const max = Math.max(...v)
  const width = niceStep((max - min) / targetBins || 0.01)
  const first = Math.floor(min / width) * width
  const count = Math.max(1, Math.ceil((max - first) / width + 1e-9))
  const mean = v.reduce((s, x) => s + x, 0) / v.length
  const sd = Math.sqrt(v.reduce((s, x) => s + (x - mean) ** 2, 0) / (v.length - 1))

  const bins: HistogramBin[] = Array.from({ length: count }, (_, i) => {
    const start = first + i * width
    return { start, end: start + width, mid: start + width / 2, count: 0,
             expected: sd > 0 ? v.length * width * normalPdf(start + width / 2, mean, sd) : 0 }
  })
  for (const x of v) {
    const i = Math.min(count - 1, Math.max(0, Math.floor((x - first) / width + 1e-9)))
    bins[i].count++
  }
  return bins
}

function niceStep(raw: number): number {
  const exponent = Math.floor(Math.log10(raw))
  const base = 10 ** exponent
  const fraction = raw / base
  const nice = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 2.5 ? 2.5 : fraction <= 5 ? 5 : 10
  return nice * base
}
