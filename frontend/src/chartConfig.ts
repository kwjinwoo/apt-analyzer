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
          label: "관측 가격 (월별 중간값)",
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
  trend: readonly ChartSeriesPoint[] = [],
): ChartConfiguration<"bar" | "line"> {
  const series = toChartSeries(points);
  const trendSeries = toChartSeries(trend);
  return {
    type: "bar",
    data: {
      labels: series.labels,
      datasets: [
        { label: "유효 거래량", data: series.data },
        ...(trend.length
          ? [
              {
                type: "line" as const,
                label: "3개월 이동 평균 (참고)",
                data: trendSeries.data,
                spanGaps: false,
              },
            ]
          : []),
      ],
    },
    options: {
      plugins: { title: { display: true, text: "월별 유효 거래량" } },
    },
  };
}
