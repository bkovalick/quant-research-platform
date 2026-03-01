import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer
} from "recharts"

export default function StrategyDetails({ run }: any) {
  const series = run.result.series.cumulative_returns

  const data = series.index.map((date: string, i: number) => ({
    date,
    value: series.values[i]
  }))

  return (
    <div>
      <h3>Equity Curve</h3>
      <div style={{ height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <XAxis dataKey="date" hide />
            <YAxis />
            <Tooltip />
            <Line
              type="monotone"
              dataKey="value"
              stroke="#1f6feb"
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}