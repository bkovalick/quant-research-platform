import { useState } from "react"
import type { CSSProperties } from "react"
import Sidebar from "./components/Sidebar"
import StrategyGrid from "./components/StrategyGrid"
import StrategyDetails from "./components/StrategyDetails"

export default function App() {
  const [experiment, setExperiment] = useState<any>(null)
  const [selectedRun, setSelectedRun] = useState<any>(null)

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
            {selectedRun && (
              <StrategyDetails run={selectedRun} />
            )}
          </>
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
    fontFamily: "Inter, sans-serif"
  },
  sidebar: {
    width: 250,
    borderRight: "1px solid #2a2f3a",
    padding: 16
  },
  main: {
    flex: 1,
    padding: 24,
    overflowY: "auto"
  }
}