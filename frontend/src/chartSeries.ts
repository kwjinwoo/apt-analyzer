export interface ChartSeriesPoint {
  period: string;
  value: number | null;
}

export interface ChartSeriesData {
  labels: string[];
  data: Array<number | null>;
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
