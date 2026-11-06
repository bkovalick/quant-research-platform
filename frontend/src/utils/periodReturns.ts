import { deserializeToArray } from "./metricsUtils"

export interface PeriodReturn { year: number; month: number | null; value: number }

/** The part of a strategy run these helpers read. */
export interface RunWithSeries { strategy_name?: string; result?: { series?: Record<string, unknown> } }

/**
 * Calendar-period returns for a run. Prefers the backend series
 * (monthly_returns / yearly_returns); runs produced before those existed fall
 * back to compounding the per-period portfolio returns here.
 */
export function periodReturns(run: RunWithSeries | null | undefined, kind: "monthly" | "yearly", benchmark = false): PeriodReturn[] {
  const series = run?.result?.series ?? {}
  const key = `${benchmark ? "benchmark_" : ""}${kind}_returns`
  const precomputed = deserializeToArray(series[key])
  if (precomputed.length) return precomputed.filter(p => Number.isFinite(p.value)).map(p => toPeriod(p.date, p.value, kind))

  const raw = deserializeToArray(benchmark ? series.benchmark_returns : series.portfolio_returns)
  return compound(raw, kind)
}

function toPeriod(date: string, value: number, kind: "monthly" | "yearly"): PeriodReturn {
  const year = Number(date.slice(0, 4))
  return { year, month: kind === "monthly" ? Number(date.slice(5, 7)) : null, value }
}

function compound(points: { date: string; value: number }[], kind: "monthly" | "yearly"): PeriodReturn[] {
  const growth = new Map<string, number>()
  for (const { date, value } of points) {
    if (!Number.isFinite(value)) continue
    const key = kind === "monthly" ? date.slice(0, 7) : date.slice(0, 4)
    growth.set(key, (growth.get(key) ?? 1) * (1 + value))
  }
  return [...growth.entries()].map(([key, g]) => toPeriod(key + (kind === "monthly" ? "-01" : "-01-01"), g - 1, kind))
}

/** Years whose first or last month is missing from the data (backtest started/ended mid-year). */
export function partialYears(monthly: PeriodReturn[]): Set<number> {
  const months = new Map<number, Set<number>>()
  for (const p of monthly) {
    if (!months.has(p.year)) months.set(p.year, new Set())
    months.get(p.year)!.add(p.month!)
  }
  const partial = new Set<number>()
  for (const [year, set] of months) if (set.size < 12) partial.add(year)
  return partial
}
