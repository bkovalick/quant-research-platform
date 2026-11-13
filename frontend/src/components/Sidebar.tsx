import { useState } from "react"
import type { CSSProperties } from "react"
import RunProgressPanel from "./RunProgress"
import Switch from "./Switch"
import { runExperimentWithProgress } from "../utils/runExperiment"
import type { RunProgress, SaveStatus } from "../utils/runExperiment"
import { mergeStrategySets } from "../utils/mergeStrategySets"
import type { MergeResult } from "../utils/mergeStrategySets"

const PERSIST_PREF_KEY = "qrp.persistRuns"

function readPersistPref(): boolean {
  try { return localStorage.getItem(PERSIST_PREF_KEY) === "1" } catch { return false }
}

function writePersistPref(value: boolean) {
  try { localStorage.setItem(PERSIST_PREF_KEY, value ? "1" : "0") } catch { /* storage unavailable */ }
}

function baseName(path: string) {
  return path.split(/[\\/]/).pop() ?? path
}

const SIGNAL_SOURCE_OPTIONS = [
  ["risk_return", "Risk / Return"],
  ["mean_reversion", "Mean Reversion"],
  ["moving_average", "Moving Average"],
  ["volatility_forecast", "Volatility Forecast"],
  ["momentum", "Momentum"],
  ["ml_cross_sectional", "Machine Learning"],
  ["black_litterman", "Black Litterman"],
  ["pairs_trading", "Pairs Trading"],
  ["vix_basis", "VIX Basis"],
] as const

/**
 * Which signal sources each strategy type can consume. Mirrors the isinstance
 * checks in the backend strategies (src/domain/strategies/): an empty list means
 * the strategy allocates without signals; a single entry means the signal is fixed.
 */
const STRATEGY_SIGNALS: Record<string, readonly string[]> = {
  systematic_strategy: ["risk_return", "mean_reversion", "moving_average", "volatility_forecast",
                        "momentum", "ml_cross_sectional", "black_litterman"],
  mean_reversion_strategy: ["moving_average"],
  pairs_trading_strategy: ["pairs_trading"],
  vix_basis_strategy: ["vix_basis"],
  inverse_vol_strategy: ["volatility_forecast"],
  fwp_strategy: [],
  ewp_strategy: [],
}
const STRATEGY_TYPE_ORDER = Object.keys(STRATEGY_SIGNALS)

const STRATEGY_TYPE_LABELS: Record<string, string> = {
  systematic_strategy: "Systematic (optimizer)",
  mean_reversion_strategy: "Mean reversion",
  pairs_trading_strategy: "Pairs trading",
  vix_basis_strategy: "VIX basis",
  inverse_vol_strategy: "Inverse volatility",
  fwp_strategy: "Fixed weight",
  ewp_strategy: "Equal weight",
}

// Parameters each ML model reads (see CrossSectionalModel): [label, config key, input step, tooltip].
const ML_MODEL_PARAMS: Record<string, [string, string, number, string][]> = {
  ridge: [
    ["Alpha", "alpha", 0.1, "Regularization strength; higher = more regularization and a simpler model, lower = a closer fit"],
  ],
  gradientboostingregressor: [
    ["Trees", "n_estimators", 10, "Number of boosting iterations (trees); more = closer fit and slower training"],
    ["Max Depth", "max_depth", 1, "Maximum depth of each tree; deeper trees capture more feature interactions and overfit more easily"],
    ["Learning Rate", "learning_rate", 0.01, "How much each tree contributes; lower values need more trees but generalize better"],
  ],
}

// Backend defaults (MachineLearningConfig.from_dict), used to seed a model's parameters when it is selected.
const ML_MODEL_DEFAULTS: Record<string, Record<string, number>> = {
  ridge: { alpha: 1.0 },
  gradientboostingregressor: { n_estimators: 100, max_depth: 3, learning_rate: 0.05 },
}

function signalLabel(source: string) {
  return SIGNAL_SOURCE_OPTIONS.find(([v]) => v === source)?.[1] ?? source
}

type Tab = "experiment" | "lab"

export default function Sidebar({ setExperiment, experiment, pinnedNames }: any) {
  const [tab, setTab] = useState<Tab>("experiment")
  const [loading, setLoading] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [runProgress, setRunProgress] = useState<RunProgress | null>(null)
  const [runCount, setRunCount] = useState(0)
  const [persistRun, setPersistRun] = useState<boolean>(readPersistPref)
  const [lastSave, setLastSave] = useState<SaveStatus | null>(null)
  const [loadInfo, setLoadInfo] = useState<MergeResult | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [resultsFile, setResultsFile] = useState<string | null>(null)
  const [resultsError, setResultsError] = useState<string | null>(null)

  /** Open an experiment_*.json saved by a run (run_local.py writes one to backtest_results/<date>/). */
  const handleOpenResults = async (e: any) => {
    const file: File | undefined = e.target.files?.[0]
    e.target.value = ""
    if (!file) return
    setResultsError(null)
    try {
      const json = JSON.parse(await file.text())
      if (!Array.isArray(json?.strategy_runs) || json.strategy_runs.length === 0) {
        throw new Error(`${file.name} has no strategy results. Pick an experiment_*.json saved by a run.`)
      }
      setExperiment(json)
      setResultsFile(`${file.name} · ${json.strategy_runs.length} runs`)
    } catch (err: any) {
      setResultsError(err instanceof SyntaxError ? `${file.name} is not valid JSON` : err.message)
    }
  }
  const [startDate, setStartDate] = useState("2000-01-01")
  const [endDate, setEndDate] = useState(() => {
    const d = getPreviousBusinessDay()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  })
  const [transactionCost, setTransactionCost] = useState(0.003)
  const [benchmark, setBenchmark] = useState("SPY")
  const [riskFreeRate, setRiskFreeRate] = useState(0.03)
  const [strategySet, setStrategySet] = useState<any>(null)
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [editedStrategies, setEditedStrategies] = useState<any[]>([])
  const [jsonMode, setJsonMode] = useState(false)
  const [jsonText, setJsonText] = useState("")
  const [jsonError, setJsonError] = useState<string | null>(null)
  const [newUniverseTicker, setNewUniverseTicker] = useState("")
  const [newUniverseTickerError, setNewUniverseTickerError] = useState<string | null>(null)

  function getPreviousBusinessDay(date: Date = new Date()): Date {
    const dayOfWeek = date.getDay();
    // Map dayOfWeek to subtract 1, 2, or 3 days
    const daysToSubtract = {
      0: 2, // Sunday -> Subtract 2 days (to Friday)
      1: 3, // Monday -> Subtract 3 days (to Friday)
    }[dayOfWeek] || 1; // Default: Subtract 1 day

    const result = new Date(date);
    result.setDate(date.getDate() - daysToSubtract);
    return result;
  }

  /**
   * Load one or more experiment JSONs. `append` merges them into the current set
   * (keeping any edits made in the Lab); otherwise they replace it.
   */
  const handleUpload = async (e: any, append = false) => {
    const files: File[] = Array.from(e.target.files ?? [])
    e.target.value = ""
    if (!files.length) return
    setLoadError(null)

    let parsed
    try {
      parsed = await Promise.all(files.map(async f => {
        try { return { fileName: f.name, json: JSON.parse(await f.text()) } }
        catch { throw new Error(`${f.name} is not valid JSON`) }
      }))
    } catch (err: any) {
      setLoadError(err.message)
      return
    }

    const existing = append && strategySet
      ? {
          merged: { ...strategySet, strategies: editedStrategies },
          sources: loadInfo?.sources ?? [],
          warnings: loadInfo?.warnings ?? [],
        }
      : null

    let result: MergeResult
    try {
      result = mergeStrategySets(parsed, existing)
    } catch (err: any) {
      setLoadError(err.message)
      return
    }

    const { merged } = result
    setLoadInfo(result)
    setStrategySet(merged)
    setEditedStrategies(structuredClone(merged.strategies))
    if (!append) setSelectedIdx(0)

    // start/end dates in the JSON are for local Python runs; the UI's date fields win.
    const msc = merged.market_store_config
    if (typeof msc.benchmark === "string") setBenchmark(msc.benchmark)
    if (typeof msc.transaction_cost === "number") setTransactionCost(msc.transaction_cost)
    if (typeof msc.risk_free_rate === "number") setRiskFreeRate(msc.risk_free_rate)
  }

  const togglePersist = (value: boolean) => {
    setPersistRun(value)
    writePersistPref(value)
  }

  const resultsDatabase: string =
    strategySet?.results_database ?? strategySet?.database_name ?? "research.duckdb"


  const runExperiment = async () => {
    if (!strategySet) return

    // Pinned strategies are frozen — their existing result stays on the Results
    // page and they are excluded from this run.
    const pinned: Set<string> = pinnedNames ?? new Set()
    const candidates = editedStrategies.length ? editedStrategies : strategySet.strategies
    const strategiesToRun = candidates.filter((s: any) => !pinned.has(s.name))

    if (!strategiesToRun.length) {
      setRunError("Every loaded strategy is pinned — unpin one to run it again.")
      return
    }
    setRunCount(strategiesToRun.length)

    for (const s of strategiesToRun) {

      if (s.rebalance_problem?.strategy_type === "fwp_strategy") {
        const tickers = s.market_state_config?.investment_universe ?? []
        const w = s.rebalance_problem?.initial_weights
        const dict = Array.isArray(w)
          ? Object.fromEntries(tickers.map((t: string, i: number) => [t, w[i] ?? 0]))
          : (w ?? {})
        const total = Object.values(dict).reduce((a: number, b) => a + (b as number), 0)
        if (Math.abs(total - 1) > 0.0001) {
          alert(`Fixed weights for "${s.name}" must sum to 1. Current sum: ${total.toFixed(4)}`)
          return
        }
      }
    }

    const config = {
      ...strategySet,
      market_store_config: {
        ...strategySet.market_store_config,
        start_date: startDate,
        end_date: endDate,
        transaction_cost: transactionCost,
        risk_free_rate: riskFreeRate,
        benchmark: benchmark
      },
      strategies: strategiesToRun
    }

    setLoading(true)
    setRunError(null)
    setRunProgress(null)
    setLastSave(null)
    try {
      const { experiment: result, save } = await runExperimentWithProgress(
        config, setRunProgress, { persist: persistRun },
      )
      setRunProgress(null)
      setLastSave(save)
      setExperiment(result)
    } catch (err: any) {
      const detail = err?.response?.data?.detail ?? err?.message ?? "Unknown error"
      setRunError(detail)
    } finally {
      setLoading(false)
    }
  }

  const currentStrategy = editedStrategies[selectedIdx]

  const updateField = (path: string[], value: any) => {
    const updated = JSON.parse(JSON.stringify(editedStrategies))
    let node = updated[selectedIdx]
    for (let i = 0; i < path.length - 1; i++) {
      if (node[path[i]] == null || typeof node[path[i]] !== "object") {
        node[path[i]] = {}
      }
      node = node[path[i]]
    }
    node[path[path.length - 1]] = value
    setEditedStrategies(updated)
  }

  const updateUniverseTickers = (nextTickers: string[]) => {
    const updatedStrategies = JSON.parse(JSON.stringify(editedStrategies))
    if (!updatedStrategies[selectedIdx].market_state_config) {
      updatedStrategies[selectedIdx].market_state_config = {}
    }
    updatedStrategies[selectedIdx].market_state_config.investment_universe = nextTickers

    if (currentStrategy.rebalance_problem?.strategy_type === "fwp_strategy") {
      const rawWeights = currentStrategy.rebalance_problem?.initial_weights
      const currentWeights: Record<string, number> = Array.isArray(rawWeights)
        ? Object.fromEntries((currentStrategy.market_state_config?.investment_universe ?? []).map((t: string, i: number) => [t, rawWeights[i] ?? 0]))
        : (rawWeights ?? {})

      updatedStrategies[selectedIdx].rebalance_problem.initial_weights = Object.fromEntries(
        nextTickers.map((t: string) => [t, currentWeights[t] ?? 0])
      )
    }

    setEditedStrategies(updatedStrategies)
    setNewUniverseTickerError(null)
  }

  const availableUniverseTickers = ((strategySet?.market_store_config?.tickers ?? []) as string[]).filter(
    (ticker: string) => ticker !== strategySet?.market_store_config?.benchmark
  )

  const addUniverseTicker = (rawTicker: string) => {
    const ticker = rawTicker.trim().toUpperCase()
    if (!ticker) return

    const current = currentStrategy.market_state_config?.investment_universe ?? []
    if (current.includes(ticker)) {
      setNewUniverseTicker("")
      setNewUniverseTickerError(null)
      return
    }

    if (!availableUniverseTickers.includes(ticker)) {
      setStrategySet((prev: any) => ({
        ...prev,
        market_store_config: {
          ...prev.market_store_config,
          tickers: [...(prev.market_store_config?.tickers ?? []), ticker],
        },
      }))
    }    

    updateUniverseTickers([...current, ticker])
    setNewUniverseTicker("")
    setNewUniverseTickerError(null)
  }

  const SIGNAL_CONFIG_KEYS: Record<string, string[]> = {
    mean_reversion:      ["mean_reversion_window", "black_litterman"],
    momentum:            ["momentum_skip_periods", "black_litterman"],
    pairs_trading:       ["pairs_trading"],
    vix_basis:           ["vix_basis"],
    ml_cross_sectional:  ["ml_signals_config", "black_litterman"],
    risk_return:         ["black_litterman"],
    moving_average:      ["black_litterman"],
    volatility_forecast: ["black_litterman"],
  }

  /** Mutates `strat`: set its signal source and drop config blocks that belong to other sources. */
  const applySignalSource = (
    strat: { rebalance_problem?: Record<string, unknown>; signals_config?: Record<string, unknown> },
    newSource: string,
  ) => {
    if (!strat.rebalance_problem) strat.rebalance_problem = {}
    strat.rebalance_problem.signal_source = newSource

    const sc = strat.signals_config ?? {}
    const keep = new Set(SIGNAL_CONFIG_KEYS[newSource] ?? [])
    const allSignalKeys = new Set(Object.values(SIGNAL_CONFIG_KEYS).flat())
    for (const key of Object.keys(sc)) {
      if (allSignalKeys.has(key) && !keep.has(key)) delete sc[key]
    }
    strat.signals_config = sc
  }

  const changeSignalSource = (newSource: string) => {
    const updated = JSON.parse(JSON.stringify(editedStrategies))
    applySignalSource(updated[selectedIdx], newSource)
    setEditedStrategies(updated)
  }

  /** Switching strategy type also moves the signal onto one the new type accepts. */
  const changeStrategyType = (newType: string) => {
    const updated = JSON.parse(JSON.stringify(editedStrategies))
    const strat = updated[selectedIdx]
    if (!strat.rebalance_problem) strat.rebalance_problem = {}
    strat.rebalance_problem.strategy_type = newType

    const allowed = STRATEGY_SIGNALS[newType]
    const current = strat.rebalance_problem.signal_source
    if (allowed && allowed.length > 0 && !allowed.includes(current)) {
      applySignalSource(strat, allowed[0])
    }
    setEditedStrategies(updated)
  }

  const openJsonEditor = () => {
    setJsonText(JSON.stringify(currentStrategy, null, 2))
    setJsonError(null)
    setJsonMode(true)
  }

  const applyJson = () => {
    try {
      const parsed = JSON.parse(jsonText)
      const updated = JSON.parse(JSON.stringify(editedStrategies))
      updated[selectedIdx] = parsed
      setEditedStrategies(updated)
      setJsonMode(false)
      setJsonError(null)
    } catch (e: any) {
      setJsonError(e.message)
    }
  }

  const quickStats = (() => {
    if (!experiment?.strategy_runs?.length) return null
    const runs = experiment.strategy_runs
    const best = (key: string, higher = true) => {
      const sorted = [...runs].sort((a, b) => {
        const va = a.result.summary[key] ?? (higher ? -Infinity : Infinity)
        const vb = b.result.summary[key] ?? (higher ? -Infinity : Infinity)
        return higher ? vb - va : va - vb
      })
      return { name: formatName(sorted[0].strategy_name), value: sorted[0].result.summary[key] }
    }
    return {
      sharpe:   best("sharpe_ratio"),
      ret:      best("return"),
      drawdown: best("max_drawdown", false),
      vol:      best("volatility", false)
    }
  })()

  const rebalanceOptions = ["daily", "weekly", "monthly", "quarterly"]
  const currentStrategyType: string = currentStrategy?.rebalance_problem?.strategy_type ?? ""
  // Keep an unrecognised type from a loaded file selectable instead of silently showing another one.
  const strategyTypes = STRATEGY_TYPE_ORDER.includes(currentStrategyType) || !currentStrategyType
    ? STRATEGY_TYPE_ORDER
    : [...STRATEGY_TYPE_ORDER, currentStrategyType]
  const allowedSignals = STRATEGY_SIGNALS[currentStrategyType]   // undefined = unknown type, no restriction
  const signalAllowed = (source: string) => !allowedSignals || allowedSignals.includes(source)
  const signalSourceOptions = SIGNAL_SOURCE_OPTIONS.filter(([value]) => signalAllowed(value))

  const inferredSignalSource = (() => {
    const explicit = currentStrategy?.rebalance_problem?.signal_source
    if (explicit) return explicit
    if (currentStrategy?.signals_config?.ml_signals_config) return "ml_cross_sectional"
    if (currentStrategy?.signals_config?.pairs_trading) return "pairs_trading"
    if (currentStrategy?.signals_config?.vix_basis) return "vix_basis"
    if (currentStrategy?.signals_config?.mean_reversion_window !== undefined) return "mean_reversion"
    if (currentStrategy?.signals_config?.momentum_skip_periods !== undefined) return "momentum"
    if (currentStrategy?.signals_config?.black_litterman) return "black_litterman"
    return "risk_return"
  })()

  const hasMlSignals = !!currentStrategy?.signals_config?.ml_signals_config
  const mlModel: string = currentStrategy?.signals_config?.ml_signals_config?.signals_model ?? "ridge"
  const hasBlackLitterman = !!currentStrategy?.signals_config?.black_litterman
  const hasPairsTrading = !!currentStrategy?.signals_config?.pairs_trading
  const hasMeanReversionSignals = currentStrategy?.signals_config?.mean_reversion_window !== undefined
  const hasMomentumSignals = currentStrategy?.signals_config?.momentum_skip_periods !== undefined
  const hasConstraints = !!currentStrategy?.rebalance_problem?.constraints
  const mean_reversion_method = currentStrategy?.signals_config?.mean_reversion_method ?? "rank_reversal"
  const usesSignals = !allowedSignals || allowedSignals.length > 0
  const signalLocked = !!allowedSignals && allowedSignals.length === 1
  // Pairs and VIX signals don't go through the Signals base class, so winsorizing has no effect on them.
  const usesWinsorizing = !["pairs_trading", "vix_basis"].includes(inferredSignalSource)
    && currentStrategyType !== "inverse_vol_strategy"
  const showMeanReversion = signalAllowed("mean_reversion") && (inferredSignalSource === "mean_reversion" || hasMeanReversionSignals)
  const showMomentum = signalAllowed("momentum") && (inferredSignalSource === "momentum" || hasMomentumSignals)
  const showPairs = signalAllowed("pairs_trading") && (inferredSignalSource === "pairs_trading" || hasPairsTrading)
  const showMl = signalAllowed("ml_cross_sectional") && (inferredSignalSource === "ml_cross_sectional" || hasMlSignals)
  // The Black-Litterman overlay is applied by the systematic strategy's optimizer only.
  const blApplies = (currentStrategyType === "systematic_strategy" || !allowedSignals)
    && !!inferredSignalSource && !["pairs_trading", "vix_basis"].includes(inferredSignalSource)
  const currentExperimentLabel = currentStrategy?.name
    ? `${currentStrategy.name} (${selectedIdx + 1} of ${editedStrategies.length})`
    : null

  return (
    <div style={container}>
      <div style={tabBar}>
        <button style={tab === "experiment" ? activeTab : inactiveTab} onClick={() => setTab("experiment")}>
          Experiment
        </button>
        <button style={tab === "lab" ? activeTab : inactiveTab} onClick={() => setTab("lab")}>
          Strategy Lab
        </button>
      </div>

      {tab === "experiment" && (
        <>
        <Section title="Strategy Set">
          <input id="strategy-file-input" type="file" accept=".json" multiple onChange={(e) => handleUpload(e, false)} onClick={(e: any) => e.target.value = null} style={{ display: "none" }} />
          <input id="strategy-file-append" type="file" accept=".json" multiple onChange={(e) => handleUpload(e, true)} onClick={(e: any) => e.target.value = null} style={{ display: "none" }} />
          {strategySet
            ? <>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={pill}>{editedStrategies.length} strategies loaded</div>
                  <button style={changeLinkBtn} onClick={() => document.getElementById("strategy-file-append")?.click()}>add files</button>
                  <button style={changeLinkBtn} onClick={() => document.getElementById("strategy-file-input")?.click()}>replace</button>
                </div>
                {loadInfo && loadInfo.sources.length > 0 && (
                  <ul style={sourceList}>
                    {loadInfo.sources.map((s, i) => (
                      <li key={`${s.fileName}-${i}`} style={sourceItem}>
                        <span style={sourceName} title={s.fileName}>{s.fileName}</span>
                        <span style={sourceCount}>{s.strategies}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {loadInfo && loadInfo.warnings.length > 0 && (
                  <details style={warnBox}>
                    <summary style={warnSummary}>
                      {loadInfo.warnings.length} merge {loadInfo.warnings.length === 1 ? "note" : "notes"}
                    </summary>
                    <ul style={warnList}>
                      {loadInfo.warnings.map((w, i) => <li key={i}>{w}</li>)}
                    </ul>
                  </details>
                )}
              </>
            : null}
          {loadError && <div style={inlineError}>{loadError}</div>}
        </Section>

        <Section title="Saved Results">
          <input id="results-file-input" type="file" accept=".json" onChange={handleOpenResults} style={{ display: "none" }} />
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <button style={changeLinkBtn} onClick={() => document.getElementById("results-file-input")?.click()}>
              open results file…
            </button>
            {resultsFile && <span style={{ fontSize: 10, color: "#8b949e" }} title={resultsFile}>{resultsFile}</span>}
          </div>
          {resultsError && <div style={inlineError}>{resultsError}</div>}
        </Section>

          <Section title="Market Configuration">
            <Row label="Start">
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} style={inputStyle} />
            </Row>
            <Row label="End">
              <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} style={inputStyle} />
            </Row>
            <Row label="Benchmark">
              <input type="text" value={benchmark} onChange={(e) => setBenchmark(e.target.value)} style={inputStyle} />
            </Row>            
            <Row label="Txn Cost">
              <input type="number" value={transactionCost} step={0.001}
                onChange={(e) => setTransactionCost(Number(e.target.value))} style={inputStyle} />
            </Row>
            <Row label="Risk Free Rate">
              <input type="number" value={riskFreeRate} step={0.005}
                onChange={(e) => setRiskFreeRate(Number(e.target.value))} style={inputStyle} />
            </Row>            
          </Section>

          {strategySet && (
            <Switch
              checked={persistRun}
              onChange={togglePersist}
              disabled={loading}
              label="Save results to database"
              description={persistRun
                ? `Run will be written to ${baseName(resultsDatabase)}`
                : "Results stay in this session only"}
            />
          )}

          <button
            style={strategySet && !loading ? runButton : loadButton}
            disabled={loading}
            onClick={strategySet ? runExperiment : () => document.getElementById("strategy-file-input")?.click()}
          >
            {loading ? `Running ${runCount} ${runCount === 1 ? "strategy" : "strategies"}…` : strategySet ? "Run Experiment" : "Load a Strategy Set"}
          </button>
          {runProgress && <RunProgressPanel progress={runProgress} />}
          {runError && <div style={{ marginTop: 6, padding: "6px 10px", background: "#2d1215", border: "1px solid #f85149", borderRadius: 6, color: "#f85149", fontSize: 11 }}>{runError}</div>}
          <SaveNotice save={lastSave} />

          {quickStats && (
            <>
              <hr style={divider} />
              <div style={quickStatsTitle}>Last Run · Best</div>
              <div style={statsGrid}>
                <StatCard label="Sharpe"   value={quickStats.sharpe.value?.toFixed(2)}   name={quickStats.sharpe.name} />
                <StatCard label="Return"   value={(quickStats.ret.value != null ? (quickStats.ret.value * 100).toFixed(1) + "%" : "-")} name={quickStats.ret.name} positive />
                <StatCard label="Min DD"   value={(quickStats.drawdown.value != null ? (quickStats.drawdown.value * 100).toFixed(1) + "%" : "-")} name={quickStats.drawdown.name} negative />
                <StatCard label="Low Vol"  value={(quickStats.vol.value != null ? (quickStats.vol.value * 100).toFixed(1) + "%" : "-")} name={quickStats.vol.name} />
              </div>
            </>
          )}
        </>
      )}

      {tab === "lab" && (
        <>
          {!strategySet ? (
            <div style={emptyState}>Load a strategy set in the Experiment tab first.</div>
          ) : (
            <>
            <div style={strategyNav}>
              {editedStrategies.map((s: any, i: number) => {
                const isNew = !strategySet.strategies.find((orig: any) => orig.name === s.name)
                const isPinned = (pinnedNames as Set<string> | undefined)?.has(s.name) ?? false
                return (
                  <div key={i} style={{ display: "flex", gap: 4 }}>
                    <button
                      style={{ ...(i === selectedIdx ? activeStrategyBtn : strategyBtn), flex: 1 }}
                      onClick={() => { setSelectedIdx(i); setJsonMode(false) }}>
                      {s.name}
                      {isPinned && <span style={pinnedBadge}>pinned</span>}
                      {isNew && !isPinned && <span style={newBadge}>new</span>}
                    </button>
                    <button
                      style={{ ...removeStrategyBtn, opacity: editedStrategies.length <= 1 ? 0.5 : 1, cursor: editedStrategies.length <= 1 ? "not-allowed" : "pointer" }}
                      disabled={editedStrategies.length <= 1}
                      onClick={() => {
                        if (editedStrategies.length <= 1) return
                        const updated = editedStrategies.filter((_: any, idx: number) => idx !== i)
                        setEditedStrategies(updated)
                        setSelectedIdx(Math.min(i, updated.length - 1))
                        setJsonMode(false)
                      }}
                      title={editedStrategies.length <= 1 ? "At least one strategy is required" : "Delete strategy"}
                    >✕</button>
                    </div>
                )
              })}
              <button style={addStrategyBtn} onClick={() => {
                const template = JSON.parse(JSON.stringify(editedStrategies[0]))
                const nextNumber = Array.from(new Set(
                  editedStrategies
                    .map((s: any) => String(s?.name ?? ""))
                    .filter((name: string) => /^custom_strategy_\d+$/.test(name))
                    .map((name: string) => Number(name.replace(/^custom_strategy_/, "")))
                )).reduce((max, value) => Math.max(max, value), 0) + 1
                template.name = `custom_strategy_${nextNumber}`
                const updated = [...editedStrategies, template]
                setEditedStrategies(updated)
                setSelectedIdx(updated.length - 1)
                setJsonMode(false)
              }}>
                + Add Strategy
              </button>
            </div>

              {jsonMode ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <textarea value={jsonText} onChange={(e) => setJsonText(e.target.value)}
                    style={jsonEditor} spellCheck={false} />
                  {jsonError && <div style={errorMsg}>{jsonError}</div>}
                  <div style={{ display: "flex", gap: 6 }}>
                    <button style={applyBtn} onClick={applyJson}>Apply</button>
                    <button style={cancelBtn} onClick={() => { setJsonMode(false); setJsonError(null) }}>Cancel</button>
                  </div>
                </div>
              ) : currentStrategy ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  <Section title="Identity">
                    <Row label="Name" tooltip="A unique identifier for this strategy">
                      <input style={inputStyle} value={currentStrategy.name}
                        onChange={(e) => updateField(["name"], e.target.value)} />
                    </Row>
                  </Section>

                  <Section title="Market State">
                    <Row label="Lookback" tooltip="Lookback window key for market state calculations (e.g. '252d' = 1 year of daily data)">
                      <input style={inputStyle} value={currentStrategy.market_state_config?.lookback_window_key ?? ""}
                        onChange={(e) => updateField(["market_state_config", "lookback_window_key"], e.target.value)} />
                    </Row>
                    <Row label="Cash Alloc" tooltip="Fraction of the portfolio kept in cash; reduces capital allocated to securities (0 = fully invested, 0.05 = 5% cash)">
                      <input type="number" step={0.01} style={inputStyle}
                        value={currentStrategy.market_state_config?.cash_allocation ?? 0}
                        onChange={(e) => updateField(["market_state_config", "cash_allocation"], Number(e.target.value))} />
                    </Row>
                    <Switch
                      checked={!!currentStrategy.market_state_config?.include_sp500_members}
                      onChange={(value) => updateField(["market_state_config", "include_sp500_members"], value)}
                      label="Point-in-time S&P 500 members"
                      description={currentStrategy.market_state_config?.include_sp500_members
                        ? "Trades whoever was in the index on each date, plus the tickers selected below"
                        : "Trades only the tickers selected below"}
                    />
                    <label style={labelStyle}>
                      {currentStrategy.market_state_config?.include_sp500_members ? "Additional Tickers" : "Universe Tickers"}
                    </label>
                      <div style={{ display: "flex", gap: 6, marginBottom: 4, alignItems: "center" }}>
                        <button style={smallBtn} onClick={() => {
                          updateUniverseTickers(availableUniverseTickers)
                        }}>All</button>

                        <button style={smallBtn} onClick={() => {
                          updateUniverseTickers([])
                        }}>Clear</button>
                        <input
                          style={{ ...inputStyle, maxWidth: 140 }}
                          placeholder="Add ticker"
                          value={newUniverseTicker}
                          onChange={(e) => {
                            setNewUniverseTicker(e.target.value.toUpperCase())
                            if (newUniverseTickerError) setNewUniverseTickerError(null)
                          }}
                          onKeyDown={(e) => {
                            if (e.key !== "Enter") return
                            e.preventDefault()
                            addUniverseTicker(newUniverseTicker)
                          }}
                        />
                        <button style={smallBtn} onClick={() => {
                          addUniverseTicker(newUniverseTicker)
                        }}>Add</button>
                        <span style={{ fontSize: 10, color: "#8b949e" }}>
                          {(currentStrategy.market_state_config?.investment_universe ?? []).length} selected
                        </span>
                      </div>
                      {newUniverseTickerError && (
                        <div style={{ fontSize: 10, color: "#f85149", marginBottom: 4 }}>
                          {newUniverseTickerError}
                        </div>
                      )}
                      <div style={tickerGrid}>
                        {availableUniverseTickers.map((ticker: string) => {
                          const selected = (currentStrategy.market_state_config?.investment_universe ?? []).includes(ticker)
                          return (
                            <button
                              key={ticker}
                              style={selected ? tickerChipActive : tickerChip}
                              onClick={() => {
                                const current = currentStrategy.market_state_config?.investment_universe ?? []
                                const updated = selected
                                  ? current.filter((t: string) => t !== ticker)
                                  : [...current, ticker]

                                updateUniverseTickers(updated)
                              }}
                            >{ticker}</button>
                          )
                        })}
                      </div>
                    <Row label="Exogenous" tooltip="Optional external signal tickers included as market regime features (e.g. ^VIX for volatility, ^TNX for interest rates)">
                      <input
                        style={inputStyle}
                        placeholder="e.g. ^VIX, ^TNX"
                        value={(currentStrategy.market_state_config?.exogenous_tickers ?? []).join(", ")}
                        onChange={(e) => {
                          const tickers = e.target.value
                            .split(",")
                            .map((t: string) => t.trim())
                            .filter((t: string) => t.length > 0)
                          updateField(["market_state_config", "exogenous_tickers"], tickers)
                        }}
                      />
                    </Row>
                  </Section>
                  
                  <Section title="Strategy Type">
                    <Row label="Strategy" tooltip="Portfolio construction method. Systematic uses a signal and the optimizer; fixed and equal weight allocate without signals; pairs, VIX basis and mean reversion each require their own signal.">
                      <select style={inputStyle}
                        value={currentStrategyType}
                        onChange={(e) => changeStrategyType(e.target.value)}>
                        {strategyTypes.map(o => <option key={o} value={o}>{STRATEGY_TYPE_LABELS[o] ?? o}</option>)}
                      </select>
                    </Row>
                  </Section>

                  <Section title="Leverage">
                    <Row label="Leverage" tooltip="Scales the strategy's target weights as a multiple of NAV. 1.0 = unlevered; 1.5 borrows 50% of NAV. Applied after the strategy/optimizer, so optimizer constraints apply before scaling.">
                      <input type="number" step={0.1} min={0} style={inputStyle}
                        value={currentStrategy?.rebalance_problem?.leverage ?? 1.0}
                        onChange={(e) => updateField(["rebalance_problem", "leverage"], Number(e.target.value))} />
                    </Row>
                    <Row label="Fin Spread" tooltip="Annual spread over the risk-free rate paid on borrowed capital. Total financing rate = risk free rate + spread.">
                      <input type="number" step={0.001} min={0} style={inputStyle}
                        value={currentStrategy?.rebalance_problem?.financing_spread ?? 0.005}
                        onChange={(e) => updateField(["rebalance_problem", "financing_spread"], Number(e.target.value))} />
                    </Row>
                  </Section>

                  <Section title="Rebalance">
                    <Row label="Frequency" tooltip="How often the portfolio is rebalanced and positions updated">
                      <select style={inputStyle}
                        value={currentStrategy.rebalance_problem?.rebalance_frequency ?? "weekly"}
                        onChange={(e) => updateField(["rebalance_problem", "rebalance_frequency"], e.target.value)}>
                        {rebalanceOptions.map(o => <option key={o} value={o}>{o}</option>)}
                      </select>
                    </Row>
                  </Section>
                  <Section title="Signals">
                    {currentStrategy && !usesSignals ? (
                      <div style={signalNote}>
                        {STRATEGY_TYPE_LABELS[currentStrategyType] ?? currentStrategyType} strategies allocate
                        without a signal, so there is nothing to configure here.
                      </div>
                    ) : currentStrategy ? (
                    <>
                    <Row label="Signal" tooltip={signalLocked
                      ? "This strategy type only works with one signal, so it is fixed."
                      : "Alpha signal source driving stock selection and portfolio weighting"}>
                      {signalLocked ? (
                        <div style={lockedValue}>
                          <span>{signalLabel(allowedSignals![0])}</span>
                          <span style={lockedHint}>required</span>
                        </div>
                      ) : (
                        <select
                          style={inputStyle}
                          value={inferredSignalSource}
                          onChange={(e) => changeSignalSource(e.target.value)}
                        >
                          {!signalAllowed(inferredSignalSource) && (
                            <option value={inferredSignalSource} disabled>
                              {signalLabel(inferredSignalSource)} (not supported)
                            </option>
                          )}
                          {signalSourceOptions.map(([value, label]) => (
                            <option key={value} value={value}>{label}</option>
                          ))}
                        </select>
                      )}
                    </Row>

                    {currentStrategyType === "inverse_vol_strategy" && (
                      <div style={signalNote}>
                        Forecast type and window live in <code>signals_config.inverse_vol</code>; edit them with Raw JSON.
                      </div>
                    )}

                    {inferredSignalSource === "vix_basis" && (
                      <div style={signalNote}>
                        Thresholds and tickers live in <code>signals_config.vix_basis</code>; edit them with Raw JSON.
                      </div>
                    )}

                    {usesWinsorizing && (<>
                    <Row label="Winsorize" tooltip="Clip extreme signal values to reduce the influence of outliers before ranking">
                      <select
                        style={inputStyle}
                        value={currentStrategy.signals_config?.apply_winsorizing ? "true" : "false"}
                        onChange={(e) => updateField(["signals_config", "apply_winsorizing"], e.target.value === "true")}
                      >
                        <option value="false">Off</option>
                        <option value="true">On</option>
                      </select>
                    </Row>

                    {currentStrategy.signals_config?.apply_winsorizing && (
                      <>
                        <Row label="Lower %" tooltip="Signals below this percentile are clipped to this floor (e.g. 0.05 = bottom 5%)">
                          <input
                            type="number" step={0.01} min={0} max={1} style={inputStyle}
                            value={currentStrategy.signals_config?.windsor_percentiles?.lower ?? 0.05}
                            onChange={(e) => updateField(["signals_config", "windsor_percentiles", "lower"], Number(e.target.value))}
                          />
                        </Row>
                        <Row label="Upper %" tooltip="Signals above this percentile are clipped to this ceiling (e.g. 0.95 = top 95%)">
                          <input
                            type="number" step={0.01} min={0} max={1} style={inputStyle}
                            value={currentStrategy.signals_config?.windsor_percentiles?.upper ?? 0.95}
                            onChange={(e) => updateField(["signals_config", "windsor_percentiles", "upper"], Number(e.target.value))}
                          />
                        </Row>
                      </>
                    )}
                    </>)}

                    {showMeanReversion && (
                      <Row label="MR Method" tooltip="rank_reversal: cross-sectional rank of short-window returns (losers up, winners down). bollinger: negative rolling z-score, which keeps the size of the deviation.">
                        <select
                          style={inputStyle}
                          value={mean_reversion_method}
                          onChange={(e) => updateField(["signals_config", "mean_reversion_method"], e.target.value)}
                        >
                          <option value="rank_reversal">Rank reversal</option>
                          <option value="bollinger">Bollinger z-score</option>
                        </select>
                      </Row>
                    )}

                    {showMeanReversion && mean_reversion_method === "rank_reversal" && (
                      <Row label="MR Window" tooltip="Lookback window (in periods) for the short-term return that is ranked">

                        <input
                          type="number"
                          style={inputStyle}
                          value={currentStrategy.signals_config?.mean_reversion_window ?? 0}
                          onChange={(e) => updateField(["signals_config", "mean_reversion_window"], Number(e.target.value))}
                        />
                      </Row>
                    )}

                    {showMeanReversion && mean_reversion_method === "bollinger" && (
                      <div style={blBlock}>
                        <Row label="Bollinger Window" tooltip="Lookback window (in periods) for computing Bollinger bands">
                          <input
                            type="number"
                            style={inputStyle}
                            value={currentStrategy.signals_config?.bollinger_window ?? 0}
                            onChange={(e) => updateField(["signals_config", "bollinger_window"], Number(e.target.value))}
                          />
                        </Row>
                        <Row label="Bollinger Scale" tooltip="Scale factor for Bollinger bands">
                          <input
                            type="number"
                            style={inputStyle}
                            value={currentStrategy.signals_config?.bollinger_scale ?? 0}
                            onChange={(e) => updateField(["signals_config", "bollinger_scale"], Number(e.target.value))}
                          />
                        </Row>                              
                      </div>
                    )}                    

                    {showMomentum && (
                      <Row label="Mom Skip" tooltip="Periods to skip at the recent end when computing momentum, avoiding short-term reversal (e.g. 1 = skip last month)">
                        <input
                          type="number"
                          style={inputStyle}
                          value={currentStrategy.signals_config?.momentum_skip_periods ?? 0}
                          onChange={(e) => updateField(["signals_config", "momentum_skip_periods"], Number(e.target.value))}
                        />
                      </Row>
                    )}

                    {showPairs && (
                        <div style={blBlock}>
                          <Row label="Lookback Horizon" tooltip="Rolling window length (in periods) for estimating pair relationships and spread statistics">
                            <input type="number" step={0.1} style={inputStyle}
                              value={currentStrategy.signals_config?.pairs_trading?.pairs_lookback_horizon ?? 20}
                              onChange={(e) => updateField(["signals_config", "pairs_trading", "pairs_lookback_horizon"], Number(e.target.value))} />
                          </Row>                          
                          <Row label="Cointegration Threshold" tooltip="Maximum p-value for the cointegration test; lower = stricter pair selection (e.g. 0.05 = 5% significance)">
                            <input type="number" step={0.1} style={inputStyle}
                              value={currentStrategy.signals_config?.pairs_trading?.cointegration_threshold ?? 0.05}
                              onChange={(e) => updateField(["signals_config", "pairs_trading", "cointegration_threshold"], Number(e.target.value))} />
                          </Row>
                          <Row label="Correlation Filter" tooltip="Minimum correlation required between pair assets; higher = tighter, more stable pairs (e.g. 0.70 = 70%)">
                            <input type="number" step={0.1} style={inputStyle}
                              value={currentStrategy.signals_config?.pairs_trading?.correlation_filter ?? 0.70}
                              onChange={(e) => updateField(["signals_config", "pairs_trading", "correlation_filter"], Number(e.target.value))} />
                          </Row>
                          <Row label="Entry" tooltip="Z-score threshold to open a pair trade; higher = fewer but stronger signals (e.g. 1.25 = 1.25 standard deviations)">
                            <input type="number" step={0.1} style={inputStyle}
                              value={currentStrategy.signals_config?.pairs_trading?.pairs_entry ?? 1.25}
                              onChange={(e) => updateField(["signals_config", "pairs_trading", "pairs_entry"], Number(e.target.value))} />
                          </Row>
                          <Row label="Exit" tooltip="Z-score threshold to close a pair trade and take profit (e.g. 0.5 = close when spread reverts to 0.5 std devs)">
                            <input type="number" step={0.1} style={inputStyle}
                              value={currentStrategy.signals_config?.pairs_trading?.pairs_exit ?? 0.5}
                              onChange={(e) => updateField(["signals_config", "pairs_trading", "pairs_exit"], Number(e.target.value))} />
                          </Row>
                          <Row label="Stop Loss" tooltip="Z-score at which a losing position is forcibly closed to limit losses (e.g. 3.5 = exit if spread widens to 3.5 std devs)">
                            <input type="number" step={0.1} style={inputStyle}
                              value={currentStrategy.signals_config?.pairs_trading?.pairs_stop_loss ?? 3.5}
                              onChange={(e) => updateField(["signals_config", "pairs_trading", "pairs_stop_loss"], Number(e.target.value))} />
                          </Row>                          
                        </div>
                    )}

                    
                    {showMl && (
                      <>
                        <div style={blHeader}>
                          <span style={blLabel}>Machine Learning</span>
                          {hasMlSignals ? (
                            <button style={blRemoveBtn} onClick={() => {
                              const updated = JSON.parse(JSON.stringify(editedStrategies))
                              if (!updated[selectedIdx].rebalance_problem) {
                                updated[selectedIdx].rebalance_problem = {}
                              }
                              updated[selectedIdx].rebalance_problem.signal_source = "ml_cross_sectional"
                              delete updated[selectedIdx].signals_config.ml_signals_config
                              setEditedStrategies(updated)
                            }}>Remove ✕</button>
                          ) : (
                            <button
                              style={blAddBtn}
                              onClick={() => updateField(["signals_config", "ml_signals_config"], {
                                enabled: true,
                                features_model: "cross_sectional_model",
                                signals_model: "ridge",
                                training_window: "2y",
                                horizon: "1m",
                                alpha: 1.0,
                                rebal_cadence: "1m",
                                sample_stride: "1w"
                              })}
                            >
                              + Add
                            </button>
                          )}
                        </div>
                        {hasMlSignals && (
                          <div style={blBlock}>
                            <Row label="Training" tooltip="Length of historical data used to train the ML model">
                              <select style={inputStyle}
                                value={currentStrategy.signals_config?.ml_signals_config?.training_window ?? "2y"}
                                onChange={(e) => updateField(["signals_config", "ml_signals_config", "training_window"], e.target.value)}>
                                {["6m", "1y", "2y", "3y", "5y"].map(o => <option key={o} value={o}>{o}</option>)}
                              </select>
                            </Row>
                            <Row label="Horizon" tooltip="Forward return horizon the model is trained to predict (e.g. 1m = predict 1-month ahead returns)">
                              <select style={inputStyle}
                                value={currentStrategy.signals_config?.ml_signals_config?.horizon ?? "1m"}
                                onChange={(e) => updateField(["signals_config", "ml_signals_config", "horizon"], e.target.value)}>
                                {["1w", "2w", "1m", "3m"].map(o => <option key={o} value={o}>{o}</option>)}
                              </select>
                            </Row>
                            <Row label="Rebal Cadence" tooltip="How often the model is retrained and signals refreshed">
                              <select style={inputStyle}
                                value={currentStrategy.signals_config?.ml_signals_config?.rebal_cadence ?? "1m"}
                                onChange={(e) => updateField(["signals_config", "ml_signals_config", "rebal_cadence"], e.target.value)}>
                                {["1w", "2w", "1m", "3m"].map(o => <option key={o} value={o}>{o}</option>)}
                              </select>
                            </Row>
                            <Row label="Sample Stride" tooltip="Step size between training samples; larger = fewer samples and faster training (e.g. 1w = one sample per week)">
                              <select style={inputStyle}
                                value={currentStrategy.signals_config?.ml_signals_config?.sample_stride ?? "1w"}
                                onChange={(e) => updateField(["signals_config", "ml_signals_config", "sample_stride"], e.target.value)}>
                                {["1d", "1w", "2w", "1m"].map(o => <option key={o} value={o}>{o}</option>)}
                              </select>
                            </Row>
                            <Row label="Model" tooltip="Model that predicts returns: ridge = regularized linear regression, gradient boosting = boosted decision trees">
                              <select style={inputStyle}
                                value={mlModel}
                                onChange={(e) => updateField(["signals_config", "ml_signals_config"], {
                                  // Seed the chosen model's parameters; values already set are kept.
                                  ...ML_MODEL_DEFAULTS[e.target.value],
                                  ...currentStrategy.signals_config?.ml_signals_config,
                                  signals_model: e.target.value,
                                })}>
                                <option value="ridge">ridge</option>
                                <option value="gradientboostingregressor">gradient boosting</option>
                              </select>
                            </Row>
                            {(ML_MODEL_PARAMS[mlModel] ?? []).map(([labelText, key, step, tooltip]) => (
                              <Row key={key} label={labelText} tooltip={tooltip}>
                                <input type="number" step={step} style={inputStyle}
                                  value={currentStrategy.signals_config?.ml_signals_config?.[key] ?? ML_MODEL_DEFAULTS[mlModel][key]}
                                  onChange={(e) => updateField(["signals_config", "ml_signals_config", key], Number(e.target.value))} />
                              </Row>
                            ))}
                          </div>
                        )}
                      </>
                    )}

                    {blApplies && (
                      <>
                        <div style={blHeader}>
                          <span style={blLabel}>Black-Litterman Overlay</span>
                          {hasBlackLitterman ? (
                            <button style={blRemoveBtn} onClick={() => {
                              const updated = JSON.parse(JSON.stringify(editedStrategies))
                              delete updated[selectedIdx].signals_config.black_litterman
                              setEditedStrategies(updated)
                            }}>Remove ✕</button>
                          ) : (
                            <button style={blAddBtn} onClick={() => {
                              updateField(["signals_config", "black_litterman"],
                                { delta: 2.5, view_uncertainty: 1.0, reversion_view: 0.03, ml_view_spread: 0.03, view_direction: "momentum" })
                            }}>+ Add</button>
                          )}
                        </div>

                        {hasBlackLitterman && (
                          <div style={blBlock}>
                            {([
                              ["Delta", "delta", 0.1, "Risk aversion coefficient for implied equilibrium returns; higher = more conservative prior (typical range 1–4)"],
                              ["View Uncertainty", "view_uncertainty", 0.25, "How many times less certain the view is than the prior. The posterior moves 1 / (1 + value) of the way toward the view: 1 = halfway, 3 = a quarter, 0.25 = 80%. Noisy signals deserve 3–10"],
                              ["Reversion View", "reversion_view", 0.01, "Expected mean-reversion return magnitude used as the investor view when applying mean-reversion signals"],
                              ["ML View Spread", "ml_view_spread", 0.01, "Expected return spread used as the investor view when applying ML-based signals"],
                            ] as [string, string, number, string][]).map(([labelText, key, step, tooltip]) => (
                              <Row key={key} label={labelText} tooltip={tooltip}>
                                <input type="number" step={step} style={inputStyle}
                                  value={currentStrategy.signals_config?.black_litterman?.[key] ?? ""}
                                  onChange={(e) => updateField(["signals_config", "black_litterman", key], Number(e.target.value))} />
                              </Row>
                            ))}
                            <Row label="View Dir" tooltip="Direction of the investor view: momentum = expect trend continuation, mean_reversion = expect reversal toward the mean">
                              <select style={inputStyle}
                                value={currentStrategy.signals_config?.black_litterman?.view_direction ?? "momentum"}
                                onChange={(e) => updateField(["signals_config", "black_litterman", "view_direction"], e.target.value)}>
                                <option value="momentum">momentum</option>
                                <option value="mean_reversion">mean_reversion</option>
                              </select>
                            </Row>
                          </div>
                        )}
                      </>
                    )}
                    </>
                    ) : (
                      <div style={emptyState}>Load a strategy set to configure signals.</div>
                    )}
                  </Section>

                  {currentStrategy.rebalance_problem?.strategy_type === "fwp_strategy" && (() => {
                    const tickers: string[] = currentStrategy.market_state_config?.investment_universe ?? []
                    const rawWeights = currentStrategy.rebalance_problem?.initial_weights
                    
                    // Normalize to dict
                    const weightsDict: Record<string, number> = Array.isArray(rawWeights)
                      ? Object.fromEntries(tickers.map((t, i) => [t, rawWeights[i] ?? 0]))
                      : (rawWeights ?? {})

                    const total = Object.values(weightsDict).reduce((s, v) => s + v, 0)
                    const valid = Math.abs(total - 1) < 0.0001

                    const updateWeight = (ticker: string, val: number) => {
                      const updated = { ...weightsDict, [ticker]: val }
                      // Store as dict
                      updateField(["rebalance_problem", "initial_weights"], updated)
                    }

                    const equalise = () => {
                      if (tickers.length === 0) return
                      const base = 1 / tickers.length
                      const updated = Object.fromEntries(
                        tickers.map((t: string, i: number) => [
                          t,
                          i === tickers.length - 1
                            ? 1 - base * (tickers.length - 1)
                            : base
                        ])
                      )
                      updateField(["rebalance_problem", "initial_weights"], updated)
                    }

                    const clearWeights = () => {
                      updateField(
                        ["rebalance_problem", "initial_weights"],
                        Object.fromEntries(tickers.map((ticker: string) => [ticker, 0]))
                      )
                    }

                    return (
                      <Section title="Fixed Weights">
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                          <span style={{ fontSize: 10, color: valid ? "#3fb950" : "#f85149" }}>
                            Sum: {(total * 100).toFixed(1)}% {valid ? "✓" : "— must equal 100%"}
                          </span>
                          <div style={{ display: "flex", gap: 4 }}>
                            <button style={smallBtn} onClick={clearWeights}>Clear</button>
                            <button style={smallBtn} onClick={equalise}>Equalise</button>
                          </div>
                        </div>
                        {tickers.map(ticker => (
                          <Row key={ticker} label={ticker}>
                            <input
                              type="number" step={0.005} min={0} max={1} style={inputStyle}
                              value={+((weightsDict[ticker] ?? 0).toFixed(6))}
                              onChange={(e) => updateWeight(ticker, Number(e.target.value))}
                            />
                          </Row>
                        ))}
                      </Section>
                    )
                  })()}
                  <Section title="Constraints">
                    <div style={blHeader}>
                      <span style={blLabel}>Optimizer Constraints</span>
                      {hasConstraints ? (
                        <button style={blRemoveBtn} onClick={() => {
                          const updated = JSON.parse(JSON.stringify(editedStrategies))
                          delete updated[selectedIdx].rebalance_problem.constraints
                          setEditedStrategies(updated)
                        }}>Remove ✕</button>
                      ) : (
                        <button style={blAddBtn} onClick={() => {
                          updateField(["rebalance_problem", "constraints"], {})
                        }}>+ Add</button>
                      )}
                    </div>

                    {hasConstraints && ([
                      ["Max Long Exposure", "max_long", "Maximum long weight. Default to 1 for a long only portfolio (short must be 0)."],
                      ["Max Short Exposure", "max_short", "Maximum short weight. Default to 0 for a long only portfolio (long must be 1)."],
                      ["Max Pos", "max_position_size", "Maximum weight any single position can hold (e.g. 0.10 = 10% of portfolio)"],
                      ["Min Pos", "min_position_size", "Minimum weight for any held position; prevents trivially small allocations"],
                      ["Max #", "max_positions", "Maximum number of simultaneous positions in the portfolio"],
                      ["Turnover", "turnover_limit", "Maximum allowable portfolio turnover per rebalance period"],
                      ["Risk Aversion", "risk_aversion", "0.10 — barely penalizes risk, near pure return maximization\n1.0 — balanced, textbook mean-variance\n2.5 — moderately risk averse, common in institutional settings\n5.0+ — conservative, heavily penalizes variance"],
                      ["Vol Limit", "optimizer_vol_constraint", "Maximum annualized portfolio volatility the optimizer will target; leave blank for unconstrained"],
                    ] as [string, string, string][]).map(([labelText, key, tooltip]) => (
                      <Row key={key} label={labelText} tooltip={tooltip}>
                        <input type="number" step={0.01} style={inputStyle}
                          value={currentStrategy.rebalance_problem?.constraints?.[key] ?? ""}
                          onChange={(e) => updateField(["rebalance_problem", "constraints", key], Number(e.target.value))} />
                      </Row>
                    ))}

                    {(["asset_class_constraints", "sector_constraints"] as const).map((key) => {
                      const labelText = key === "asset_class_constraints" ? "Asset Class Constraints" : "Sector Constraints"
                      const tooltip = key === "asset_class_constraints"
                        ? "Optional per-asset-class bounds, e.g. Equity [-0.20, 0.20]"
                        : "Optional per-sector bounds, e.g. Information Technology [-0.12, 0.12]"
                      const entries = currentStrategy.rebalance_problem?.constraints?.[key] ?? {}

                      const addConstraint = () => {
                        const updated = JSON.parse(JSON.stringify(entries))
                        const nextKey = `Group ${Object.keys(updated).length + 1}`
                        updated[nextKey] = [-0.1, 0.1]
                        updateField(["rebalance_problem", "constraints", key], updated)
                      }

                      const updateConstraintKey = (oldKey: string, nextKey: string) => {
                        const updated = JSON.parse(JSON.stringify(entries))
                        const value = updated[oldKey]
                        delete updated[oldKey]
                        updated[nextKey] = value
                        updateField(["rebalance_problem", "constraints", key], updated)
                      }

                      const updateConstraintBound = (groupKey: string, boundIndex: number, value: string) => {
                        const updated = JSON.parse(JSON.stringify(entries))
                        const bounds = Array.isArray(updated[groupKey]) ? [...updated[groupKey]] : [0, 0]
                        bounds[boundIndex] = Number(value)
                        updated[groupKey] = bounds
                        updateField(["rebalance_problem", "constraints", key], updated)
                      }

                      const removeConstraint = (groupKey: string) => {
                        const updated = JSON.parse(JSON.stringify(entries))
                        delete updated[groupKey]
                        updateField(["rebalance_problem", "constraints", key], updated)
                      }

                      return (
                        <div key={key} style={{ marginTop: 10 }}>
                          <div style={blHeader}>
                            <span style={blLabel}>{labelText}</span>
                            <button style={blAddBtn} onClick={addConstraint}>+ Add</button>
                          </div>

                          {Object.keys(entries).length === 0 ? (
                            <div style={{ color: "#8b949e", fontSize: 12, marginTop: 6 }}>No entries</div>
                          ) : (
                            Object.entries(entries).map(([groupKey, bounds]) => (
                              <div key={groupKey} style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8 }}>
                                <input
                                  type="text"
                                  value={groupKey}
                                  style={{ ...inputStyle, width: 150 }}
                                  onChange={(e) => updateConstraintKey(groupKey, e.target.value)}
                                />
                                <input
                                  type="number"
                                  step={0.01}
                                  value={Array.isArray(bounds) ? bounds[0] ?? "" : ""}
                                  style={{ ...inputStyle, width: 90 }}
                                  onChange={(e) => updateConstraintBound(groupKey, 0, e.target.value)}
                                />
                                <span style={{ color: "#8b949e" }}>to</span>
                                <input
                                  type="number"
                                  step={0.01}
                                  value={Array.isArray(bounds) ? bounds[1] ?? "" : ""}
                                  style={{ ...inputStyle, width: 90 }}
                                  onChange={(e) => updateConstraintBound(groupKey, 1, e.target.value)}
                                />
                                <button style={blRemoveBtn} onClick={() => removeConstraint(groupKey)}>✕</button>
                              </div>
                            ))
                          )}
                        </div>
                      )
                    })}
                  </Section>

                  <button style={jsonToggleBtn} onClick={openJsonEditor}>Edit Raw JSON ↗</button>
                </div>
              ) : null}
            </>
          )}

          <hr style={divider} />
          <button style={loading ? loadButton : runButton} disabled={loading} onClick={runExperiment}>
            {loading ? "Running…" : currentExperimentLabel ? `Run ${currentExperimentLabel}` : "Run Experiment"}
          </button>
          {runProgress && <RunProgressPanel progress={runProgress} />}
          {runError && <div style={{ marginTop: 6, padding: "6px 10px", background: "#2d1215", border: "1px solid #f85149", borderRadius: 6, color: "#f85149", fontSize: 11 }}>{runError}</div>}
          {persistRun && !loading && !lastSave && (
            <div style={savedNotice}>Results will be saved to {baseName(resultsDatabase)}</div>
          )}
          <SaveNotice save={lastSave} />
        </>
      )}
    </div>
  )
}

function SaveNotice({ save }: { save: SaveStatus | null }) {
  if (!save) return null
  if (save.error) {
    return (
      <div style={inlineError} role="alert">
        <strong>Results not saved.</strong> The run finished and is shown, but writing
        to {baseName(save.database)} failed: {save.error}
      </div>
    )
  }
  return (
    <div style={savedNotice} title={save.database}>
      <span style={savedDot} aria-hidden /> Saved to {baseName(save.database)}
    </div>
  )
}

function StatCard({ label, name, value, positive, negative }: any) {
  const valueColor = positive ? "#3fb950" : negative ? "#f85149" : "#e6edf3"
  return (
    <div style={statCard}>
      <div style={statLabel}>{label}</div>
      <div style={{ ...statValue, color: valueColor }}>{value ?? "-"}</div>
      <div style={statName}>{name}</div>
    </div>
  )
}

function Section({ title, children }: any) {
  return (
    <div style={sectionStyle}>
      <h4 style={sectionTitle}>{title}</h4>
      {children}
    </div>
  )
}

// Inline label+input row to halve vertical space vs stacked label/input
function Row({ label, tooltip, children }: any) {
  return (
    <div style={rowStyle}>
      <span style={rowLabel}>
        {label}
        {tooltip && <span title={tooltip} style={{ marginLeft: 3, color: "#58a6ff", cursor: "help", fontSize: 11 }}>ⓘ</span>}
      </span>
      <div style={rowInput}>{children}</div>
    </div>
  )
}

function formatName(name: string) {
  return name.replace("_portfolio", "").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())
}

const container: CSSProperties = { display: "flex", flexDirection: "column", gap: 10, height: "100%", overflowY: "auto" }
const tabBar: CSSProperties = { display: "flex", borderBottom: "1px solid #2a2f3a", marginBottom: 2 }
const baseTab: CSSProperties = { flex: 1, padding: "6px 0", background: "none", border: "none", cursor: "pointer", fontSize: 12, fontWeight: 600, letterSpacing: "0.3px" }
const activeTab: CSSProperties = { ...baseTab, color: "#e6edf3", borderBottom: "2px solid #238636" }
const inactiveTab: CSSProperties = { ...baseTab, color: "#8b949e", borderBottom: "2px solid transparent" }
const sectionStyle: CSSProperties = { display: "flex", flexDirection: "column", gap: 4 }
const sectionTitle: CSSProperties = { fontSize: 10, textTransform: "uppercase", color: "#8b949e", letterSpacing: "0.6px", margin: 0, marginBottom: 1 }
const labelStyle: CSSProperties = { fontSize: 10, color: "#8b949e" }
const inputStyle: CSSProperties = { background: "#161b22", border: "1px solid #30363d", borderRadius: 4, color: "#e6edf3", padding: "3px 6px", fontSize: 11, width: "100%", boxSizing: "border-box" }
const fileInput: CSSProperties = { fontSize: 11, color: "#8b949e" }
const pill: CSSProperties = { fontSize: 10, color: "#3fb950", background: "#0f2b14", border: "1px solid #238636", borderRadius: 20, padding: "1px 8px", display: "inline-block" }
const runButton: CSSProperties = { padding: "8px 12px", background: "#238636", border: "none", color: "white", cursor: "pointer", borderRadius: 6, fontWeight: 600, fontSize: 12, width: "100%" }
const divider: CSSProperties = { borderColor: "#2a2f3a", margin: "2px 0" }
const quickStatsTitle: CSSProperties = { fontSize: 10, textTransform: "uppercase", letterSpacing: "0.6px", color: "#8b949e", fontWeight: 600 }
const statsGrid: CSSProperties = { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }
const statCard: CSSProperties = { background: "#0d1117", border: "1px solid #21262d", borderRadius: 6, padding: "6px 8px" }
const statLabel: CSSProperties = { fontSize: 9, color: "#8b949e", textTransform: "uppercase", letterSpacing: "0.4px", marginBottom: 1 }
const statValue: CSSProperties = { fontSize: 14, fontWeight: 700, lineHeight: 1.2 }
const statName: CSSProperties = { fontSize: 9, color: "#8b949e", marginTop: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }
const strategyNav: CSSProperties = { display: "flex", flexDirection: "column", gap: 3 }
const strategyBtn: CSSProperties = { background: "none", border: "1px solid #30363d", borderRadius: 4, color: "#8b949e", padding: "4px 8px", fontSize: 11, cursor: "pointer", textAlign: "left" }
const activeStrategyBtn: CSSProperties = { ...strategyBtn, background: "#161b22", border: "1px solid #388bfd", color: "#e6edf3" }
const jsonEditor: CSSProperties = { background: "#0d1117", border: "1px solid #30363d", borderRadius: 4, color: "#e6edf3", padding: 8, fontSize: 11, fontFamily: "monospace", height: 320, resize: "vertical", width: "100%", boxSizing: "border-box" }
const jsonToggleBtn: CSSProperties = { background: "none", border: "1px solid #30363d", borderRadius: 4, color: "#8b949e", padding: "4px 8px", fontSize: 11, cursor: "pointer", textAlign: "left" }
const applyBtn: CSSProperties = { flex: 1, padding: "5px 0", background: "#238636", border: "none", borderRadius: 4, color: "white", fontSize: 11, cursor: "pointer" }
const cancelBtn: CSSProperties = { flex: 1, padding: "5px 0", background: "#21262d", border: "1px solid #30363d", borderRadius: 4, color: "#e6edf3", fontSize: 11, cursor: "pointer" }
const errorMsg: CSSProperties = { color: "#f85149", fontSize: 10, fontFamily: "monospace" }
const emptyState: CSSProperties = { color: "#8b949e", fontSize: 12, lineHeight: 1.6 }
const rowStyle: CSSProperties = { display: "flex", alignItems: "center", gap: 6 }
const rowLabel: CSSProperties = { fontSize: 10, color: "#8b949e", width: 68, flexShrink: 0 }
const rowInput: CSSProperties = { flex: 1, minWidth: 0 }
const blHeader: CSSProperties = { display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 6 }
const blLabel: CSSProperties = { fontSize: 10, color: "#8b949e", textTransform: "uppercase", letterSpacing: "0.4px" }
const blAddBtn: CSSProperties = { background: "none", border: "1px solid #238636", borderRadius: 3, color: "#3fb950", fontSize: 10, cursor: "pointer", padding: "1px 6px" }
const blRemoveBtn: CSSProperties = { background: "none", border: "1px solid #6e3535", borderRadius: 3, color: "#f85149", fontSize: 10, cursor: "pointer", padding: "1px 6px" }
const blBlock: CSSProperties = { display: "flex", flexDirection: "column", gap: 4, paddingLeft: 8, borderLeft: "2px solid #21262d", marginTop: 4 }
const tickerGrid: CSSProperties = { display: "flex", flexWrap: "wrap", gap: 4 }
const tickerChip: CSSProperties = { background: "none", border: "1px solid #30363d", borderRadius: 3, color: "#8b949e", fontSize: 10, cursor: "pointer", padding: "2px 5px" }
const tickerChipActive: CSSProperties = { ...tickerChip, background: "#0f2b14", border: "1px solid #238636", color: "#3fb950" }
const smallBtn: CSSProperties = { background: "none", border: "1px solid #30363d", borderRadius: 3, color: "#8b949e", fontSize: 10, cursor: "pointer", padding: "2px 6px" }
const loadButton: CSSProperties = { padding: "8px 12px", background: "#1f6feb", border: "none", color: "white", cursor: "pointer", borderRadius: 6, fontWeight: 600, fontSize: 12, width: "100%" }
const exportButton: CSSProperties = { padding: "8px 12px", background: "none", border: "1px solid #238636", color: "#3fb950", cursor: "pointer", borderRadius: 6, fontWeight: 600, fontSize: 12, width: "100%" }
const signalNote: CSSProperties = { fontSize: 10.5, color: "#8b949e", lineHeight: 1.5, padding: "2px 0" }
const lockedValue: CSSProperties = {
  display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8,
  padding: "3px 6px", fontSize: 11, color: "#e6edf3",
  border: "1px solid #21262d", borderRadius: 4, background: "#0d1117",
}
const lockedHint: CSSProperties = { fontSize: 9.5, color: "#6e7681", textTransform: "uppercase", letterSpacing: "0.4px" }
const sourceList: CSSProperties ={ listStyle: "none", margin: "6px 0 0", padding: 0, display: "flex", flexDirection: "column", gap: 2 }
const sourceItem: CSSProperties = { display: "flex", justifyContent: "space-between", gap: 8, fontSize: 10.5, color: "#8b949e" }
const sourceName: CSSProperties = { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }
const sourceCount: CSSProperties = { fontVariantNumeric: "tabular-nums", color: "#6e7681", flexShrink: 0 }
const warnBox: CSSProperties = { marginTop: 6, fontSize: 10.5, color: "#d29922" }
const warnSummary: CSSProperties = { cursor: "pointer", userSelect: "none" }
const warnList: CSSProperties = { margin: "4px 0 0", paddingLeft: 16, color: "#8b949e", lineHeight: 1.5 }
const inlineError: CSSProperties = { marginTop: 6, padding: "6px 10px", background: "#2d1215", border: "1px solid #f85149", borderRadius: 6, color: "#f85149", fontSize: 11, lineHeight: 1.45 }
const savedNotice: CSSProperties = { display: "flex", alignItems: "center", gap: 6, marginTop: 6, fontSize: 11, color: "#8b949e" }
const savedDot: CSSProperties = { width: 6, height: 6, borderRadius: "50%", background: "#3fb950", flexShrink: 0 }
const changeLinkBtn: CSSProperties ={ background: "none", border: "none", color: "#8b949e", fontSize: 10, cursor: "pointer", padding: 0, textDecoration: "underline" }
const addStrategyBtn: CSSProperties = {
  background: "none", border: "1px dashed #30363d", borderRadius: 4,
  color: "#8b949e", padding: "4px 8px", fontSize: 11, cursor: "pointer",
  textAlign: "left", marginTop: 2
}
const newBadge: CSSProperties = {
  fontSize: 9, color: "#3fb950", border: "1px solid #238636",
  borderRadius: 3, padding: "0 4px", marginLeft: 6
}
const pinnedBadge: CSSProperties = {
  fontSize: 9, color: "#58a6ff", border: "1px solid #1f6feb",
  borderRadius: 3, padding: "0 4px", marginLeft: 6
}
const removeStrategyBtn: CSSProperties = {
  background: "none", border: "1px solid #30363d", borderRadius: 4,
  color: "#8b949e", fontSize: 10, cursor: "pointer", padding: "2px 6px"
}