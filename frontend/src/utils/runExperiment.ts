import axios from "axios"

const API = "http://localhost:8000"
const POLL_MS = 500

export type StrategyPhase = "queued" | "loading_data" | "running" | "analyzing" | "done" | "failed" | "cancelled"

export interface StrategyProgress {
  name: string
  phase: StrategyPhase
  pct: number
  as_of: string | null
  elapsed_s: number
  eta_s: number | null
  error: string | null
}

export interface SaveStatus {
  database: string
  saved: boolean
  error: string | null
}

export interface RunProgress {
  job_id: string
  status: "running" | "cancelling" | "finalizing" | "saving" | "done" | "failed" | "cancelled"
  error: string | null
  save: SaveStatus | null
  elapsed_s: number
  pct: number
  strategies: StrategyProgress[]
}

/** Features the ML signal supports (GET /ml-features), grouped by what each needs. */
export interface MlFeatureCatalog {
  groups: Record<string, string[]>
  /** What the backend builds when a strategy lists no features. */
  default: string[]
}

export async function fetchMlFeatures(): Promise<MlFeatureCatalog> {
  return (await axios.get<MlFeatureCatalog>(`${API}/ml-features`)).data
}

/** Thrown by runExperimentWithProgress when the run was stopped with cancelExperiment. */
export class RunCancelledError extends Error {
  constructor() {
    super("Run stopped")
    this.name = "RunCancelledError"
  }
}

/** Ask a running job to stop. Running strategies stop at their next progress update. */
export async function cancelExperiment(jobId: string): Promise<RunProgress> {
  return (await axios.post<RunProgress>(`${API}/experiments/${jobId}/cancel`)).data
}

export interface RunOutcome {
  experiment: unknown
  /** null when saving wasn't requested */
  save: SaveStatus | null
}

/**
 * Start a background experiment run, report progress on every poll, and resolve
 * with the finished experiment (and the save outcome when persist is on).
 * Rejects with a readable message if the run fails. A failed save does not
 * reject: the results are still returned, with save.error set. Rejects with
 * RunCancelledError if the run was stopped.
 */
export async function runExperimentWithProgress(
  config: unknown,
  onProgress: (p: RunProgress) => void,
  { parallel = true, max_workers = 2, persist = false }: { parallel?: boolean; max_workers?: number; persist?: boolean } = {},
): Promise<RunOutcome> {
  const { data } = await axios.post(`${API}/experiments`, config, { params: { parallel, max_workers, persist } })
  const jobId: string = data.job_id

  let progress: RunProgress
  for (;;) {
    progress = (await axios.get<RunProgress>(`${API}/experiments/${jobId}`)).data
    onProgress(progress)
    if (progress.status === "done") break
    if (progress.status === "cancelled") throw new RunCancelledError()
    if (progress.status === "failed") {
      const failed = progress.strategies.find(s => s.phase === "failed")
      throw new Error(failed?.error ?? progress.error ?? "Experiment failed")
    }
    await new Promise(r => setTimeout(r, POLL_MS))
  }

  const { data: experiment } = await axios.get(`${API}/experiments/${jobId}/result`)
  return { experiment, save: progress.save }
}
