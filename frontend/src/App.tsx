import { useState } from "react"
import type { CSSProperties } from "react"
import Sidebar from "./components/Sidebar"
import StrategyGrid from "./components/StrategyGrid"
import StrategyDetails from "./components/StrategyDetails"
import StrategyDiagnostics from "./components/StrategyDiagnostics"

export default function App() {
  const [experiment, setExperiment] = useState<any>(null)
  const [selectedRun, setSelectedRun] = useState<any>(null)
  const [timeWindow, setTimeWindow] = useState<{
  start: string | null
  end: string | null
  }>({ start: null, end: null })

  return (
    <div style={styles.app}>
      <div style={styles.sidebar}>
        <Sidebar setExperiment={setExperiment} />
      </div>

      <div style={styles.main}>
        <h2 style={{ marginBottom: 20 }}>Research Cockpit</h2>
          {experiment && (
            <>
              <StrategyGrid
                runs={experiment.strategy_runs}
                onSelect={setSelectedRun}
              />

              <StrategyDetails
                runs={experiment.strategy_runs}
              />

              <div style={sectionSpacing}>
                <StrategyDiagnostics runs={experiment.strategy_runs} />
              </div>
            </>
          )}
      </div>
    </div>
  )
}

const sectionSpacing: CSSProperties = {
  marginTop: 50
}

const styles: { [key: string]: CSSProperties } = {
  app: {
    display: "flex",
    height: "100vh",
    backgroundColor: "#0e1117",
    color: "#e6edf3",
    fontFamily: "Inter, sans-serif"
  },
  sidebar: {
    width: 250,
    borderRight: "1px solid #2a2f3a",
    padding: 16
  },
  main: {
    flex: 1,
    padding: "32px 48px",
    overflowY: "auto",  
    maxWidth: 1600,
    margin: "0 auto"
  }
}