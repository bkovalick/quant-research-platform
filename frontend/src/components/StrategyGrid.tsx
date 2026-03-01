import type { CSSProperties } from "react"

export default function StrategyGrid({ runs, onSelect }: any) {
  return (
    <table style={table}>
      <thead>
        <tr>
          <th>Strategy</th>
          <th>Return</th>
          <th>Vol</th>
          <th>Sharpe</th>
          <th>Max DD</th>
          <th>Turnover</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((run: any) => (
          <tr
            key={run.run_id}
            onClick={() => onSelect(run)}
            style={{ cursor: "pointer" }}
          >
            <td>{run.rebalance_problem.strategy_type}</td>
            <td>{run.result.summary.return?.toFixed(3)}</td>
            <td>{run.result.summary.volatility?.toFixed(3)}</td>
            <td>{run.result.summary.sharpe_ratio?.toFixed(2)}</td>
            <td>{run.result.summary.max_drawdown?.toFixed(2)}</td>
            <td>{run.result.summary.turnover?.toFixed(2)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

const table: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  marginBottom: 30
}