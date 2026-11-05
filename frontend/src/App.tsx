import { Component, useEffect, useState } from "react"
import type { CSSProperties, ReactNode } from "react"

import NavRail from "./components/NavRail"
import type { Page } from "./components/NavRail"
import LabDrawer from "./components/LabDrawer"
import StrategyGrid from "./components/StrategyGrid"
import StrategyDetails from "./components/StrategyDetails"
import AnalysisPanel from "./components/AnalysisPanel"
import StatisticalEvidence from "./components/StatisticalEvidence"
import CalendarReturns from "./components/CalendarReturns"
import { colorForRun } from "./utils/strategyColors"
import DownloadReport from "./components/DownloadReport"
import AttributionPage from "./components/AttributionPage"
import type { DateWindow } from "./utils/metricsUtils"

/** The fields App relies on; the rest of a strategy run passes through untouched. */
interface Run { run_id: string; strategy_name: string; [key: string]: unknown }

export default function App() {
  const [experiment, setExperiment] = useState<any>(null)
  const [page, setPage] = useState<Page>("results")
  const [labOpen, setLabOpen] = useState(true)   // first visit: the Lab is the invitation

  const [selectedRun, setSelectedRun] = useState<any>(null)
  // Pinned runs are held as snapshots, not ids into the current experiment, so
  // they survive the next run: the Lab skips them and their old result stays on
  // the Results page alongside the new runs.
  const [pinnedRuns, setPinnedRuns] = useState<Run[]>([])
  const [dateWindow, setDateWindow] = useState<DateWindow | null>(null)

  const experimentRuns: Run[] = experiment?.strategy_runs ?? []
  const experimentRunIds = new Set(experimentRuns.map(r => r.run_id))
  const carriedOver = pinnedRuns.filter(r => !experimentRunIds.has(r.run_id))
  const runs: Run[] = [...experimentRuns, ...carriedOver]     // RUNS-SOURCE
  const pinnedIds = new Set(pinnedRuns.map(r => r.run_id))
  const pinnedNames = new Set(pinnedRuns.map(r => r.strategy_name))

  // When a suite finishes (a new experiment arrives), close the Lab and show Results.
  // Keyed on the experiment, not the run count: re-running the same number of
  // strategies must still replace the selected run with the fresh one.
  useEffect(() => {
    // A pinned run whose name reappears in the new experiment has been superseded
    // (in practice only the benchmark, which is rebuilt every run): drop the pin
    // rather than show two rows with the same name.
    const newNames = new Set(experimentRuns.map(r => r.strategy_name))
    setPinnedRuns(prev => prev.filter(r =>
      experimentRunIds.has(r.run_id) || !newNames.has(r.strategy_name)))

    if (runs.length > 0) {
      setLabOpen(false)
      setPage("results")
      if (!selectedRun || !runs.some(r => r.run_id === selectedRun.run_id)) {
        setSelectedRun(runs[0])
      }
    }
  }, [experiment])   // eslint-disable-line react-hooks/exhaustive-deps

  const togglePin = (run: Run) => {
    setPinnedRuns(prev => prev.some(r => r.run_id === run.run_id)
      ? prev.filter(r => r.run_id !== run.run_id)
      : [...prev, run])
  }

  return (
    <div style={shell}>
      <NavRail
        page={page}
        onNavigate={p => { setPage(p); setLabOpen(false) }}
        onOpenLab={() => setLabOpen(true)}
        labOpen={labOpen}
      />

      <LabDrawer
        open={labOpen}
        onClose={() => setLabOpen(false)}
        experiment={experiment}
        setExperiment={setExperiment}
        pinnedNames={pinnedNames}
      />

      <main style={main}>
        <ErrorBoundary>
          {page === "results" && (
            runs.length === 0 ? (
              <EmptyResults onOpenLab={() => setLabOpen(true)} />
            ) : (
              <div style={resultsPage}>
                <div style={resultsHeader}>
                  <h1 style={resultsTitle}>Results</h1>
                  <div style={headerControls}>
                    <label style={selectLabel}>
                      Detail for
                      <select
                        style={runSelect}
                        value={selectedRun?.run_id ?? ""}
                        onChange={(e) => {
                          const run = runs.find((r: any) => r.run_id === e.target.value)
                          if (run) setSelectedRun(run)
                        }}
                      >
                        {runs.map((r: any) => (
                          <option key={r.run_id} value={r.run_id}>
                            {formatStrategyName(r.strategy_name)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <DownloadReport experiment={experiment} pinnedRuns={pinnedRuns} />
                  </div>
                </div>
                <StrategyGrid
                  runs={runs}
                  onSelect={setSelectedRun}
                  selectedRunId={selectedRun?.run_id ?? null}
                  pinnedIds={pinnedIds}
                  onPin={togglePin}
                  dateWindow={dateWindow}
                />
                <StrategyDetails
                  runs={runs}
                  onWindowChange={setDateWindow}
                  dateWindow={dateWindow}
                />
                <CalendarReturns
                  run={selectedRun}
                  color={colorForRun(runs, selectedRun)}
                  benchmarkColor={colorForRun(runs, runs.find(r => r.strategy_name === experiment?.market_config?.benchmark))}
                />
                <AnalysisPanel
                  runs={runs}
                  selectedRun={selectedRun}
                  dateWindow={dateWindow}
                />
                <StatisticalEvidence
                  run={selectedRun}
                  dateWindow={dateWindow}
                />
              </div>
            )
          )}

          {page === "attribution" && (
            <AttributionPage
              runs={runs}
              selectedRun={selectedRun}
              onSelectRun={setSelectedRun}
            />
          )}
        </ErrorBoundary>
      </main>
    </div>
  )
}

function formatStrategyName(name: string) {
  return name.replace("_portfolio", "").replace(/_/g, " ")
}

function EmptyResults({ onOpenLab }: { onOpenLab: () => void }) {
  return (
    <div style={emptyResults}>
      <div style={emptyTitle}>No results yet</div>
      <div style={emptyLine}>
        Configure a strategy suite in the Lab and run it. Results, factor
        attribution, and robustness evidence land here.
      </div>
      <button style={emptyCta} onClick={onOpenLab}>Open the Lab</button>
    </div>
  )
}

/**
 * Error boundary — a render throw becomes a readable message instead of a
 * white screen. The three Sidebar crashes this project has eaten would each
 * have been a five-second diagnosis with this in place.
 */
class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }
  static getDerivedStateFromError(error: Error) { return { error } }
  render() {
    if (this.state.error) {
      return (
        <div style={errorBox}>
          <div style={errorTitle}>A component crashed while rendering</div>
          <pre style={errorPre}>{String(this.state.error)}</pre>
          <button style={emptyCta} onClick={() => this.setState({ error: null })}>
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

/* ---- styles ---- */

const shell: CSSProperties = {
  display: "flex",
  minHeight: "100vh",
  background: "#0d1117",
  color: "#e6edf3",
  fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif",
}
const main: CSSProperties = { flex: 1, minWidth: 0 }
const resultsPage: CSSProperties = { padding: "16px 20px" }
const resultsHeader: CSSProperties = {
  display: "flex", alignItems: "center", justifyContent: "space-between",
  marginBottom: 12, gap: 16,
}
const resultsTitle: CSSProperties = {
  fontSize: 16, fontWeight: 600, color: "#e6edf3", margin: 0, letterSpacing: "0.2px",
}
const headerControls: CSSProperties = {
  display: "flex", alignItems: "center", gap: 14,
}
const selectLabel: CSSProperties = {
  display: "flex", alignItems: "center", gap: 8,
  fontSize: 11, color: "#8b949e", whiteSpace: "nowrap",
}
const runSelect: CSSProperties = {
  background: "#161b22", color: "#e6edf3", border: "1px solid #2a2f3a",
  borderRadius: 6, padding: "5px 10px", fontSize: 12, minWidth: 180,
}

const emptyResults: CSSProperties = {
  display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
  minHeight: "70vh", textAlign: "center", padding: 24,
}
const emptyTitle: CSSProperties = { fontSize: 16, fontWeight: 600, color: "#e6edf3", marginBottom: 8 }
const emptyLine: CSSProperties = { fontSize: 12.5, color: "#8b949e", maxWidth: 380, lineHeight: 1.6, marginBottom: 18 }
const emptyCta: CSSProperties = {
  background: "#238636", color: "#fff", border: "none", borderRadius: 6,
  padding: "8px 16px", fontSize: 13, cursor: "pointer",
}
const errorBox: CSSProperties = { padding: 32, maxWidth: 720, margin: "0 auto" }
const errorTitle: CSSProperties = { fontSize: 14, fontWeight: 600, color: "#f85149", marginBottom: 10 }
const errorPre: CSSProperties = {
  background: "#161b22", border: "1px solid #2a2f3a", borderRadius: 6,
  padding: 14, fontSize: 12, color: "#c9d1d9", whiteSpace: "pre-wrap",
  marginBottom: 16,
}
