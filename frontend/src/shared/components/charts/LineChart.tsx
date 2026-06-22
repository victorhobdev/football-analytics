"use client";

import { useMemo } from "react";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart as RechartsLineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatChartValue } from "@/shared/components/charts/chart-formatters";

type LineSeriesDefinition = {
  dataKey: string;
  label?: string;
  color?: string;
  metricKey?: string;
};

type LineChartProps<TData extends Record<string, unknown>> = {
  data: TData[];
  xKey: keyof TData & string;
  lines: LineSeriesDefinition[];
  className?: string;
  height?: number;
  showLegend?: boolean;
  yAxisMetricKey?: string;
};

const DEFAULT_LINE_COLORS = ["#003526", "#0b6a56", "#16a34a", "#3b82f6", "#dc2626"];

export function LineChart<TData extends Record<string, unknown>>({
  data,
  xKey,
  lines,
  className,
  height = 280,
  showLegend = true,
  yAxisMetricKey,
}: LineChartProps<TData>) {
  const classes = ["w-full rounded-lg border border-slate-200 bg-white p-3", className].filter(Boolean).join(" ");
  const seriesMap = useMemo(
    () =>
      new Map(
        lines.map((series, index) => [
          series.dataKey,
          {
            ...series,
            color: series.color ?? DEFAULT_LINE_COLORS[index % DEFAULT_LINE_COLORS.length],
          },
        ]),
      ),
    [lines],
  );

  if (data.length === 0) {
    return (
      <section className={classes}>
        <p className="text-sm text-slate-500">Sem dados para gráfico.</p>
      </section>
    );
  }

  return (
    <section className={classes}>
      <div style={{ height }}>
        <ResponsiveContainer height="100%" width="100%">
          <RechartsLineChart data={data}>
            <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
            <XAxis dataKey={xKey} tick={{ fontSize: 12 }} />
            <YAxis
              tick={{ fontSize: 12 }}
              tickFormatter={(value: number) => {
                return formatChartValue(value, yAxisMetricKey);
              }}
            />
            <Tooltip
              formatter={(value: unknown, name: string | undefined) => {
                const safeName = name ?? "";
                const series = seriesMap.get(safeName);
                const metricKey = series?.metricKey ?? yAxisMetricKey;
                return [formatChartValue(value, metricKey), series?.label ?? safeName];
              }}
            />
            {showLegend ? <Legend /> : null}
            {Array.from(seriesMap.values()).map((series) => (
              <Line
                dataKey={series.dataKey}
                dot={false}
                key={series.dataKey}
                name={series.label ?? series.dataKey}
                stroke={series.color}
                strokeWidth={2}
                type="monotone"
              />
            ))}
          </RechartsLineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
