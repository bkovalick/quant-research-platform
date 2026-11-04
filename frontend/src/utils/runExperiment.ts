import axios from "axios"

const API = "http://localhost:8000"
const POLL_MS = 500

export type StrategyPhase = "queued" | "loading_data" | "running" | "analyzing" | "done" | "failed"

export interface StrategyProgress {
  name: string
  phase: StrategyPhase
  pct: number
  as_of: string | null
  elapsed_s: number
  eta_s: number | null
  error: string | null
}

export interface RunProgress {
  job_id: string
  status: "running" | "finalizing" | "done" | "failed"
  error: string | null
  elapsed_s: number
  pct: number
  strategies: StrategyProgress[]
}

/**
 * Start a background experiment run, report progress on every poll, and resolve
 * with the finished experiment. Rejects with a readable message on failure.
 */
export async function runExperimentWithProgress(
  config: unknown,
  onProgress: (p: RunProgress) => void,
  { parallel = false }: { parallel?: boolean } = {},
): Promise<unknown> {
  const { data } = await axios.post(`${API}/experiments`, config, { params: { parallel } })
  const jobId: string = data.job_id

  for (;;) {
    const { data: progress } = await axios.get<RunProgress>(`${API}/experiments/${jobId}`)
    onProgress(progress)
    if (progress.status === "done") break
    if (progress.status === "failed") {
      const failed = progress.strategies.find(s => s.phase === "failed")
      throw new Error(failed?.error ?? progress.error ?? "Experiment failed")
    }
    await new Promise(r => setTimeout(r, POLL_MS))
  }

  const { data: experiment } = await axios.get(`${API}/experiments/${jobId}/result`)
  return experiment
}
