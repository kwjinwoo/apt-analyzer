import Chart from "chart.js/auto";
import "htmx.org";

import { priceChartConfiguration } from "./chartConfig";
import type { ChartSeriesPoint } from "./chartSeries";

/** Create a chart only when a future server-rendered page supplies a canvas. */
export function createPriceChart(
  canvas: HTMLCanvasElement,
  points: readonly ChartSeriesPoint[],
): Chart<"line"> {
  return new Chart(canvas, priceChartConfiguration(points));
}
