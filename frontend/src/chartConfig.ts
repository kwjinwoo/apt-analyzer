import type { ChartConfiguration } from "chart.js";

import { type ChartSeriesPoint, toChartSeries } from "./chartSeries";

export function priceChartConfiguration(
  points: readonly ChartSeriesPoint[],
): ChartConfiguration<"line"> {
  const series = toChartSeries(points);
  return {
    type: "line",
    data: {
      labels: series.labels,
      datasets: [
        {
          label: "Observed price",
          data: series.data,
          spanGaps: false,
        },
      ],
    },
  };
}
