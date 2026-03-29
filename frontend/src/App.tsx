import { useState, useMemo } from "react"
import type { CSSProperties } from "react"
import Sidebar from "./components/Sidebar"
import StrategyGrid from "./components/StrategyGrid"
import StrategyDetails from "./components/StrategyDetails"
import AnalysisPanel from "./components/AnalysisPanel"
import type { DateWindow } from "./utils/metricsUtils"

export default function App() {
  const [experiment, setExperiment] = useState<any>(null)
  const [selectedRun, setSelectedRun] = useState<any>(null)
  const [pinnedRuns, setPinnedRuns] = useState<any[]>([])
  const [dateWindow, setDateWindow] = useState<DateWindow | null>(null)

  const handlePin = (run: any) => {
    setPinnedRuns(prev =>
      prev.some(r => r.run_id === run.run_id)
        ? prev.filter(r => r.run_id !== run.run_id)
        : [...prev, run]
    )
  }

  // Reset window when new experiment runs
  const handleSetExperiment = (exp: any) => {
    setExperiment(exp)
    setDateWindow(null)
  }

  const pinnedIds = useMemo(() => new Set(pinnedRuns.map(r => r.run_id)), [pinnedRuns])
  const allRuns = useMemo(() => {
    const currentRuns = experiment?.strategy_runs ?? []
    const extraPinned = pinnedRuns.filter(r => !currentRuns.some((cr: any) => cr.run_id === r.run_id))
    return [...currentRuns, ...extraPinned]
  }, [experiment, pinnedRuns])

  return (
    <div style={styles.app}>
      <div style={styles.sidebar}>
        <Sidebar
          setExperiment={handleSetExperiment}
          experiment={experiment}
          pinnedRuns={pinnedRuns}
          onClearPinned={() => setPinnedRuns([])}
        />
      </div>

      <div style={styles.main}>
        {allRuns.length > 0 ? (
          <div style={styles.twoCol}>
            <div style={styles.leftCol}>
              <StrategyGrid
                runs={allRuns}
                onSelect={setSelectedRun}
                pinnedIds={pinnedIds}
                onPin={handlePin}
                dateWindow={dateWindow}
              />
              <StrategyDetails
                runs={allRuns}
                onWindowChange={setDateWindow}
                dateWindow={dateWindow}
              />
            </div>
            <div style={styles.rightCol}>
              <AnalysisPanel
                runs={allRuns}
                selectedRun={selectedRun}
                dateWindow={dateWindow}
              />
            </div>
          </div>
        ) : (
          <div style={styles.empty}>
            <div style={styles.emptyText}>Load a strategy set and run an experiment to get started.</div>
          </div>
        )}
      </div>
    </div>
  )
}

const styles: { [key: string]: CSSProperties } = {
  app: {
    display: "flex",
    height: "100vh",
    backgroundColor: "#0e1117",
    color: "#e6edf3",
    fontFamily: "Inter, sans-serif",
    overflow: "hidden"
  },
  sidebar: {
    width: 340,
    minWidth: 340,
    borderRight: "1px solid #2a2f3a",
    padding: "12px 14px",
    overflowY: "auto",
    height: "100vh",
    boxSizing: "border-box"
  },
  main: {
    flex: 1,
    overflowY: "auto",
    padding: "12px 20px",
    minWidth: 0,
    boxSizing: "border-box"
  },
  twoCol: {
    display: "flex",
    gap: 16,
    alignItems: "flex-start",
    width: "100%",
    boxSizing: "border-box"
  },
  leftCol: {
    flex: "1 1 0",
    minWidth: 0
  },
  rightCol: {
    flex: "1 1 0",
    minWidth: 0,
    position: "sticky",
    top: 0,
    alignSelf: "flex-start",
    height: "calc(100vh - 24px)",
    overflowY: "auto"
  },
  empty: {
    display: "flex",
    height: "100%",
    alignItems: "center",
    justifyContent: "center"
  },
  emptyText: {
    color: "#8b949e",
    fontSize: 14
  }
}
