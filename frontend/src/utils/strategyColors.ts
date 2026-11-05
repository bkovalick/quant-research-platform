/**
 * Strategy series colors, shared so a strategy keeps the same color in every
 * chart. Assigned by the run's position in the experiment (the same rule
 * StrategyGrid, StrategyDetails and AnalysisPanel use with their local copies).
 */
export const STRATEGY_COLORS = ["#3fb950", "#1f6feb", "#d29922", "#f85149", "#a371f7", "#56d364"]

export function colorForRun(runs: { run_id: string }[], run: { run_id: string } | null | undefined): string | null {
  if (!run) return null
  const i = runs.findIndex(r => r.run_id === run.run_id)
  return i < 0 ? null : STRATEGY_COLORS[i % STRATEGY_COLORS.length]
}
