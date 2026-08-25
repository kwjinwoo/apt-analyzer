import Chart from "chart.js/auto";
import "htmx.org";
import "./styles.css";

import {
  priceChartConfiguration,
  volumeChartConfiguration,
} from "./chartConfig";
import { type ChartSeriesPoint, chartPointsFromResult } from "./chartSeries";

let activePriceChart: Chart<"line"> | undefined;
let activeVolumeChart: Chart<"bar"> | undefined;

/** Create a chart only when a future server-rendered page supplies a canvas. */
export function createPriceChart(
  canvas: HTMLCanvasElement,
  points: readonly ChartSeriesPoint[],
): Chart<"line"> {
  return new Chart(canvas, priceChartConfiguration(points));
}

/** Convert expanded server values while preserving null gaps. */
/** Hydrate the server-rendered result without moving credentials or policy client-side. */
export function hydrateCharts(): void {
  const canvas = document.querySelector<HTMLCanvasElement>("#price-chart");
  const volumeCanvas =
    document.querySelector<HTMLCanvasElement>("#volume-chart");
  const data = document.querySelector<HTMLPreElement>("#analysis-data");
  if (!canvas || !data) return;
  const result = JSON.parse(data.textContent ?? "{}");
  const points = chartPointsFromResult(result);
  activePriceChart?.destroy();
  activeVolumeChart?.destroy();
  activePriceChart = createPriceChart(canvas, points);
  if (volumeCanvas) {
    const volume = (result.volume_series ?? []).map(
      (item: { period: string; value: number | null }) => ({
        period: item.period,
        value: item.value,
      }),
    );
    activeVolumeChart = new Chart(
      volumeCanvas,
      volumeChartConfiguration(volume),
    );
  }
  canvas.dataset.chartReady = "true";
  if (volumeCanvas) volumeCanvas.dataset.chartReady = "true";
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", hydrateCharts);
  document.addEventListener("htmx:afterSwap", hydrateCharts);
  if (document.readyState !== "loading") hydrateCharts();
}
