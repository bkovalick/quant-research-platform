/**
 * Merge several experiment JSON files into one strategy set.
 *
 * Rules (first file wins, nothing silently dropped):
 *  - strategies are concatenated in file order; a name that is already taken gets
 *    a numeric suffix ("momentum" -> "momentum_2") because runs, pins and progress
 *    are keyed by strategy name
 *  - market_store_config.tickers is the union across files (first-seen order)
 *  - every other market_store_config field and top-level field comes from the
 *    first file that defines it; a different value in a later file is reported
 *    as a warning so the user can see which value is in effect
 */

type Json = Record<string, unknown>

export interface StrategySet extends Json {
  strategies: Json[]
  market_store_config: Json & { tickers?: string[] }
}

export interface StrategySetFile {
  fileName: string
  json: unknown
}

export interface MergeResult {
  merged: StrategySet
  sources: { fileName: string; strategies: number }[]
  warnings: string[]
}

const IGNORED_TOP_LEVEL = new Set(["strategies", "market_store_config", "_description"])
// The UI's date fields override these, so a conflict between files isn't worth a note.
const SILENT_MARKET_FIELDS = new Set(["start_date", "end_date"])

export function mergeStrategySets(
  files: StrategySetFile[],
  existing?: { merged: unknown; sources: MergeResult["sources"]; warnings: string[] } | null,
): MergeResult {
  const all: StrategySetFile[] = existing
    ? [{ fileName: "__existing__", json: existing.merged }, ...files]
    : files

  const warnings: string[] = existing ? [...existing.warnings] : []
  const sources = existing ? [...existing.sources] : []
  const merged: StrategySet = { market_store_config: {}, strategies: [] }
  const fieldOrigin: Record<string, string> = {}
  const tickers: string[] = []
  const names = new Set<string>()

  for (const { fileName, json: raw } of all) {
    const label = fileName === "__existing__" ? "the loaded set" : fileName
    const json = raw as Partial<StrategySet> | null
    if (!json || typeof json !== "object" || !Array.isArray(json.strategies)) {
      throw new Error(`${fileName} has no "strategies" array — is it an experiment config?`)
    }

    for (const [key, value] of Object.entries(json)) {
      if (IGNORED_TOP_LEVEL.has(key)) continue
      takeFirst(merged, key, value, `top-level "${key}"`, label, fieldOrigin, warnings)
    }
    if (json._description && merged._description === undefined) merged._description = json._description

    const msc: StrategySet["market_store_config"] = json.market_store_config ?? {}
    for (const [key, value] of Object.entries(msc)) {
      if (key === "tickers") continue
      takeFirst(merged.market_store_config, key, value, key, label, fieldOrigin,
                SILENT_MARKET_FIELDS.has(key) ? [] : warnings, "msc.")
    }
    for (const t of msc.tickers ?? []) {
      if (!tickers.includes(t)) tickers.push(t)
    }

    let added = 0
    for (const strategy of json.strategies) {
      const copy = structuredClone(strategy)
      const base = typeof copy.name === "string" ? copy.name : "strategy"
      let name = base
      for (let i = 2; names.has(name); i++) name = `${base}_${i}`
      if (name !== base && fileName !== "__existing__") {
        warnings.push(`Renamed "${base}" from ${fileName} to "${name}" (name already loaded).`)
      }
      copy.name = name
      names.add(name)
      merged.strategies.push(copy)
      added++
    }
    if (fileName !== "__existing__") sources.push({ fileName, strategies: added })
  }

  merged.market_store_config.tickers = tickers
  return { merged, sources, warnings }
}

function takeFirst(
  target: Json, key: string, value: unknown, label: string, fileLabel: string,
  origin: Record<string, string>, warnings: string[], prefix = "",
) {
  const originKey = prefix + key
  if (target[key] === undefined) {
    target[key] = structuredClone(value)
    origin[originKey] = fileLabel
  } else if (JSON.stringify(target[key]) !== JSON.stringify(value)) {
    warnings.push(
      `${fileLabel} sets ${label} to ${short(value)}; keeping ${short(target[key])} from ${origin[originKey]}.`,
    )
  }
}

function short(v: unknown) {
  const s = JSON.stringify(v)
  return s.length > 40 ? s.slice(0, 37) + "…" : s
}
