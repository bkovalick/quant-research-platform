import axios from "axios"
import { useState } from "react"
import type { CSSProperties } from "react"

export default function Sidebar({ setExperiment }: any) {

  const [startDate, setStartDate] = useState("2005-01-01")
  const [endDate, setEndDate] = useState("2020-12-31")
  const [rebalance, setRebalance] = useState("monthly")
  const [transactionCost, setTransactionCost] = useState(0)
  const [strategySet, setStrategySet] = useState<any>(null)

  const handleUpload = async (e: any) => {
    const file = e.target.files[0]
    const text = await file.text()
    const json = JSON.parse(text)
    setStrategySet(json)
  }

  const runExperiment = async () => {
    const config = await fetch("/experiment_20260220.json").then(res => res.json())
    const res = await axios.post(
        "http://localhost:8000/run-experiment",
        config
    )
    setExperiment(res.data)
  }
  return (
    <div style={container}>

      <h2 style={title}>Research Cockpit</h2>

      {/* Strategy Section */}

      <Section title="Experiment">

        <label style={label}>Strategy Set</label>

        <input
          type="file"
          onChange={handleUpload}
        />

      </Section>

      {/* Market Config */}

      <Section title="Market Configuration">

        <label style={label}>Start</label>

        <input
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
        />

        <label style={label}>End</label>

        <input
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
        />

        <label style={label}>Rebalance</label>

        <select
          value={rebalance}
          onChange={(e) => setRebalance(e.target.value)}
        >
          <option value="monthly">Monthly</option>
          <option value="weekly">Weekly</option>
        </select>

        <label style={label}>Transaction Cost</label>

        <input
          type="number"
          value={transactionCost}
          onChange={(e) => setTransactionCost(Number(e.target.value))}
        />

      </Section>

      {/* Run */}

      <button
        style={runButton}
        onClick={runExperiment}
      >
        Run Experiment
      </button>

      <hr style={divider} />

      {/* Strategy Lab */}

      <button style={secondaryButton}>
        Strategy Lab
      </button>

    </div>
  )
}

const btn = {
  marginTop: 10,
  padding: "8px 12px",
  background: "#1f6feb",
  border: "none",
  color: "white",
  cursor: "pointer"
}

function Section({ title, children }: any) {
  return (
    <div style={section}>
      <h4 style={sectionTitle}>{title}</h4>
      {children}
    </div>
  )
}

const container: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 20
}

const title: CSSProperties = {
  fontSize: 18,
  fontWeight: 600
}

const section: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 8
}

const sectionTitle: CSSProperties = {
  fontSize: 13,
  textTransform: "uppercase",
  color: "#8b949e",
  letterSpacing: "0.5px"
}

const label: CSSProperties = {
  fontSize: 12,
  color: "#8b949e"
}

const runButton: CSSProperties = {
  marginTop: 10,
  padding: "10px 12px",
  background: "#238636",
  border: "none",
  color: "white",
  cursor: "pointer",
  borderRadius: 6,
  fontWeight: 600
}

const secondaryButton: CSSProperties = {
  padding: "8px 12px",
  background: "#21262d",
  border: "1px solid #30363d",
  color: "#e6edf3",
  cursor: "pointer",
  borderRadius: 6
}

const divider: CSSProperties = {
  borderColor: "#2a2f3a"
}