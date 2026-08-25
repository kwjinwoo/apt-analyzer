export interface ChartSeriesPoint {
  period: string;
  value: number | null;
  marker?: "peak" | "trough";
}

export interface ChartSeriesData {
  labels: string[];
  data: Array<number | null>;
}

export function chartPointsFromResult(result: {
  monthly_series?: readonly { period: string; value: string | null }[];
  mdd?: { peak?: { month?: string }; trough?: { month?: string } };
}): ChartSeriesPoint[] {
  const peak = result.mdd?.peak?.month;
  const trough = result.mdd?.trough?.month;
  return (result.monthly_series ?? []).map((item) => ({
    period: item.period,
    value: item.value === null ? null : Number(item.value),
    ...(item.period === peak
      ? { marker: "peak" as const }
      : item.period === trough
        ? { marker: "trough" as const }
        : {}),
  }));
}

/** Preserve observed zeroes and unavailable values for a future chart adapter. */
export function toChartSeries(
  points: readonly ChartSeriesPoint[],
): ChartSeriesData {
  return {
    labels: points.map(({ period }) => period),
    data: points.map(({ value }) => value),
  };
}
