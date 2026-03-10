import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { PricePoint } from "../api/client";

type PriceChartProps = {
  history: PricePoint[];
};

type ChartPoint = {
  timestamp: number;
  label: string;
  yesPrice: number;
  noPrice: number;
};

function toChartPoints(history: PricePoint[]): ChartPoint[] {
  return history.map((point) => {
    const date = new Date(point.timestamp * 1000);
    return {
      timestamp: point.timestamp,
      label: date.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
      yesPrice: point.price,
      noPrice: 1 - point.price,
    };
  });
}

function probabilityTick(value: number) {
  return `${(value * 100).toFixed(0)}%`;
}

export function PriceChart({ history }: PriceChartProps) {
  const data = toChartPoints(history);

  return (
    <div className="price-chart">
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data} margin={{ top: 14, right: 16, left: 8, bottom: 6 }}>
          <CartesianGrid strokeDasharray="4 6" stroke="#d6ccc1" />
          <XAxis dataKey="label" tickMargin={8} minTickGap={30} stroke="#6a6159" />
          <YAxis
            domain={[0, 1]}
            ticks={[0, 0.25, 0.5, 0.75, 1]}
            tickFormatter={probabilityTick}
            width={52}
            stroke="#6a6159"
          />
          <Tooltip
            formatter={(value: number, name: string) => [probabilityTick(value), name === "yesPrice" ? "Yes" : "No"]}
            labelFormatter={(_, payload) => {
              if (!payload || payload.length === 0) {
                return "";
              }
              const ts = payload[0].payload.timestamp;
              return new Date(ts * 1000).toLocaleString();
            }}
          />
          <Legend formatter={(value) => (value === "yesPrice" ? "Yes" : "No")} />
          <Line
            type="monotone"
            dataKey="yesPrice"
            stroke="#d96d2f"
            strokeWidth={3}
            dot={false}
            activeDot={{ r: 5 }}
          />
          <Line
            type="monotone"
            dataKey="noPrice"
            stroke="#3f7f93"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
