"use client";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";

export interface Series {
  key: string;
  label: string;
  color: string;
}

export function TimeSeriesChart({
  data,
  series,
  xKey = "step",
  height = 260,
  yFormatter,
}: {
  data: Record<string, unknown>[];
  series: Series[];
  xKey?: string;
  height?: number;
  yFormatter?: (v: number) => string;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="#1E2833" strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey={xKey}
          stroke="#5B6B7A"
          tick={{ fill: "#5B6B7A", fontSize: 11, fontFamily: "var(--font-mono)" }}
          tickLine={false}
          axisLine={{ stroke: "#1E2833" }}
        />
        <YAxis
          stroke="#5B6B7A"
          tick={{ fill: "#5B6B7A", fontSize: 11, fontFamily: "var(--font-mono)" }}
          tickLine={false}
          axisLine={false}
          tickFormatter={yFormatter}
          width={44}
        />
        <Tooltip
          contentStyle={{
            background: "#131B24",
            border: "1px solid #29343F",
            borderRadius: 8,
            fontSize: 12,
            fontFamily: "var(--font-mono)",
          }}
          labelStyle={{ color: "#94A3B3" }}
        />
        <Legend wrapperStyle={{ fontSize: 12, fontFamily: "var(--font-body)", color: "#94A3B3" }} />
        {series.map((s) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.label}
            stroke={s.color}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
