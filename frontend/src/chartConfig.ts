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
          pointBackgroundColor: points.map((point) =>
            point.marker === "peak"
              ? "#b42318"
              : point.marker === "trough"
                ? "#175cd3"
                : "#344054",
          ),
        },
      ],
    },
  };
}

export function volumeChartConfiguration(
  points: readonly ChartSeriesPoint[],
): ChartConfiguration<"bar"> {
  const series = toChartSeries(points);
  return {
    type: "bar",
    data: {
      labels: series.labels,
      datasets: [{ label: "Eligible transactions", data: series.data }],
    },
    options: {
      plugins: { title: { display: true, text: "Monthly transaction volume" } },
    },
  };
}
