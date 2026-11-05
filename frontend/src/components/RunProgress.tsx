import type { CSSProperties } from "react"
import type { RunProgress as Progress, StrategyProgress } from "../utils/runExperiment"

const PHASE_LABEL: Record<StrategyProgress["phase"], string> = {
  queued: "Queued",
  loading_data: "Loading data",
  running: "Backtesting",
  analyzing: "Analyzing",
  done: "Done",
  failed: "Failed",
}

export default function RunProgress({ progress }: { progress: Progress }) {
  const allStrategiesDone = progress.strategies.every(s => s.phase === "done")
  const headline =
    progress.status === "failed" ? "Run failed"
    : progress.status === "done" ? "Complete"
    : progress.status === "saving" ? "Saving to database…"
    : allStrategiesDone ? "Building benchmark and results…"
    : `Running ${progress.strategies.length} ${progress.strategies.length === 1 ? "strategy" : "strategies"}`

  return (
    <div style={panel} role="status" aria-live="polite">
      <div style={header}>
        <span style={headlineStyle}>{headline}</span>
        <span style={num}>{Math.round(progress.pct)}% · {formatSeconds(progress.elapsed_s)}</span>
      </div>
      <Bar pct={progress.pct} failed={progress.status === "failed"} />

      <div style={list}>
        {progress.strategies.map(s => (
          <div key={s.name} style={row}>
            <div style={rowTop}>
              <span style={name} title={s.name}>{s.name.replace(/_/g, " ")}</span>
              <span style={{ ...phaseStyle, color: phaseColor(s.phase) }}>{PHASE_LABEL[s.phase]}</span>
            </div>
            <Bar pct={s.pct} failed={s.phase === "failed"} thin />
            <div style={rowMeta}>
              <span style={num}>{s.as_of ?? "—"}</span>
              <span style={num}>
                {s.phase === "running" && s.eta_s != null
                  ? `~${formatSeconds(s.eta_s)} left`
                  : s.elapsed_s > 0 ? formatSeconds(s.elapsed_s) : ""}
              </span>
            </div>
            {s.error && <div style={errorText}>{s.error}</div>}
          </div>
        ))}
      </div>
    </div>
  )
}

function Bar({ pct, failed, thin }: { pct: number; failed?: boolean; thin?: boolean }) {
  return (
    <div style={{ ...track, height: thin ? 3 : 5 }}>
      <div style={{
        ...fill,
        width: `${Math.max(0, Math.min(100, pct))}%`,
        background: failed ? "#f85149" : "#388bfd",
      }} />
    </div>
  )
}

function phaseColor(phase: StrategyProgress["phase"]) {
  if (phase === "failed") return "#f85149"
  if (phase === "done") return "#3fb950"
  if (phase === "queued") return "#6e7681"
  return "#c9d1d9"
}

function formatSeconds(s: number) {
  if (s < 60) return `${s.toFixed(s < 10 ? 1 : 0)}s`
  const m = Math.floor(s / 60)
  return `${m}m ${String(Math.round(s % 60)).padStart(2, "0")}s`
}

const panel: CSSProperties = {
  marginTop: 8, padding: "10px 10px 6px", background: "#0d1117",
  border: "1px solid #21262d", borderRadius: 6,
}
const header: CSSProperties = { display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }
const headlineStyle: CSSProperties = { fontSize: 12, fontWeight: 600, color: "#e6edf3" }
const num: CSSProperties = { fontSize: 10.5, color: "#8b949e", fontVariantNumeric: "tabular-nums" }
const track: CSSProperties = { background: "#21262d", borderRadius: 3, overflow: "hidden" }
const fill: CSSProperties = { height: "100%", transition: "width 400ms linear" }
const list: CSSProperties = { display: "flex", flexDirection: "column", gap: 8, marginTop: 10, maxHeight: 260, overflowY: "auto" }
const row: CSSProperties = { display: "flex", flexDirection: "column", gap: 3 }
const rowTop: CSSProperties = { display: "flex", justifyContent: "space-between", gap: 8 }
const name: CSSProperties = { fontSize: 11, color: "#c9d1d9", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }
const phaseStyle: CSSProperties = { fontSize: 10.5, flexShrink: 0 }
const rowMeta: CSSProperties = { display: "flex", justifyContent: "space-between" }
const errorText: CSSProperties = { fontSize: 10.5, color: "#f85149", whiteSpace: "pre-wrap" }
