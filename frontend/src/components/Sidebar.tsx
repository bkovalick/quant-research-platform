import axios from "axios"

export default function Sidebar({ setExperiment }: any) {
  const runExperiment = async () => {
    const config = await fetch("/experiment_20260220.json").then(res => res.json())

    const res = await axios.post(
        "http://localhost:8000/run-experiment",
        config
    )

    setExperiment(res.data)
  }

  return (
    <div>
      <h3>Experiments</h3>
      <button onClick={runExperiment} style={btn}>
        Run Experiment
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