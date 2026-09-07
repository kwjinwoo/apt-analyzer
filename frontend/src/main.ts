import Chart from "chart.js/auto";
import "htmx.org";
import "./styles.css";

import {
  priceChartConfiguration,
  volumeChartConfiguration,
} from "./chartConfig";
import { type ChartSeriesPoint, chartPointsFromResult } from "./chartSeries";
import {
  type AnalysisPreview,
  monthRangeDates,
  normalizeIndexRange,
  selectionLabel,
} from "./periodBrush";

type SelectableChart = Chart<"bar" | "line"> & {
  $selection?: [number, number];
};

interface VolumePoint {
  period: string;
  value: number | null;
}

let activePriceChart: Chart<"line"> | undefined;
let activeVolumeChart: SelectableChart | undefined;
let cleanupPreviewInteractions: (() => void) | undefined;

const selectionPlugin = {
  id: "period-selection-band",
  afterDraw(chart: Chart) {
    const range = (chart as SelectableChart).$selection;
    const scale = chart.scales.x;
    if (!range || !scale) return;
    const center = (index: number) => scale.getPixelForValue(index);
    const fallbackGap =
      range[0] > 0
        ? center(range[0]) - center(range[0] - 1)
        : center(range[0] + 1) - center(range[0]);
    const gap = Number.isFinite(fallbackGap) ? Math.abs(fallbackGap) : 12;
    const left = center(range[0]) - gap / 2;
    const right = center(range[1]) + gap / 2;
    chart.ctx.save();
    chart.ctx.fillStyle = "rgba(29, 95, 170, 0.16)";
    chart.ctx.fillRect(left, scale.top, right - left, scale.bottom - scale.top);
    chart.ctx.restore();
  },
};
Chart.register(selectionPlugin);

/** Create a chart only when a server-rendered page supplies a canvas. */
export function createPriceChart(
  canvas: HTMLCanvasElement,
  points: readonly ChartSeriesPoint[],
): Chart<"line"> {
  return new Chart(canvas, priceChartConfiguration(points));
}

function element<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  text?: string,
  className?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className !== undefined) node.className = className;
  return node;
}

function renderMetric(
  list: HTMLDListElement,
  label: string,
  metric: AnalysisPreview["turnover"] | AnalysisPreview["volume"],
): void {
  const group = element("div", undefined, "preview-metric");
  group.append(element("dt", label));
  const result = element("dd", metric.display);
  const detail =
    "status" in metric && metric.status === "unavailable"
      ? metric.reason
      : metric.evidence;
  const methodLabel =
    "method" in metric && metric.method === "preview-calendar-month-average"
      ? "연환산 평균"
      : "method" in metric &&
          metric.method === "preview-cumulative-month-turnover"
        ? "누적(비연환산)"
        : undefined;
  if (methodLabel) result.append(element("small", methodLabel));
  if (detail) result.append(element("small", detail));
  group.append(result);
  list.append(group);
}

function renderPreview(card: HTMLElement, payload: AnalysisPreview): void {
  const heading = element("h3", "선택 기간 참고 미리보기");
  const period = element(
    "p",
    `${payload.selection.label} · ${payload.selection.months}개월`,
    "preview-period",
  );
  const metrics = element("dl", undefined, "preview-metrics");
  renderMetric(metrics, "유효 거래량", payload.volume);
  renderMetric(metrics, "거래회전율", payload.turnover);
  renderMetric(metrics, "거래유지율", payload.retention);
  renderMetric(metrics, "최대 낙폭(MDD)", payload.mdd);
  card.replaceChildren(heading, period, metrics);
  card.dataset.state = "ready";
}

function bindPreviewInteractions(
  canvas: HTMLCanvasElement,
  points: readonly VolumePoint[],
  card: HTMLElement,
  status: HTMLElement,
): () => void {
  let dragStart: number | undefined;
  let requestGeneration = 0;
  let controller: AbortController | undefined;
  const initialStatus =
    "차트에서 월 범위를 드래그하면 참고 미리보기가 표시됩니다.";

  const monthAt = (event: PointerEvent): number => {
    const rect = canvas.getBoundingClientRect();
    const scale = activeVolumeChart?.scales.x;
    if (!scale || points.length === 0) return 0;
    const value = scale.getValueForPixel(event.clientX - rect.left) ?? 0;
    return Math.max(0, Math.min(points.length - 1, Math.round(Number(value))));
  };

  const paintRange = (range: [number, number]): void => {
    if (!activeVolumeChart) return;
    const first = points[range[0]];
    const last = points[range[1]];
    if (!first || !last) return;
    activeVolumeChart.$selection = range;
    activeVolumeChart.update("none");
    canvas.dataset.selectedRange = `${range[0]}:${range[1]}`;
    status.textContent = selectionLabel(first.period, last.period);
  };

  const clearPreview = (): void => {
    requestGeneration += 1;
    controller?.abort();
    controller = undefined;
    dragStart = undefined;
    card.hidden = true;
    card.replaceChildren();
    delete card.dataset.state;
    delete canvas.dataset.selectedRange;
    if (activeVolumeChart) {
      delete activeVolumeChart.$selection;
      activeVolumeChart.update("none");
    }
    status.textContent = initialStatus;
  };

  const beginPreview = (): void => {
    requestGeneration += 1;
    controller?.abort();
    controller = undefined;
    card.hidden = true;
    card.replaceChildren();
    delete card.dataset.state;
  };

  const requestPreview = async (range: [number, number]): Promise<void> => {
    const generation = ++requestGeneration;
    controller?.abort();
    controller = new AbortController();
    const first = points[range[0]];
    const last = points[range[1]];
    if (!first || !last) return;
    const dates = monthRangeDates(first.period, last.period);
    card.hidden = false;
    card.dataset.state = "loading";
    card.replaceChildren(element("p", "선택 기간 지표를 계산하는 중입니다…"));
    try {
      const response = await fetch("/analysis/preview", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams(dates),
        signal: controller.signal,
      });
      const payload = (await response.json()) as AnalysisPreview & {
        error?: string;
      };
      if (generation !== requestGeneration) return;
      if (!response.ok)
        throw new Error(payload.error ?? "미리보기를 계산하지 못했습니다.");
      renderPreview(card, payload);
    } catch (error) {
      if (
        generation !== requestGeneration ||
        (error instanceof DOMException && error.name === "AbortError")
      )
        return;
      card.hidden = false;
      card.dataset.state = "error";
      card.replaceChildren(
        element(
          "p",
          error instanceof Error
            ? error.message
            : "미리보기를 계산하지 못했습니다.",
        ),
      );
    }
  };

  const onPointerDown = (event: PointerEvent): void => {
    beginPreview();
    dragStart = monthAt(event);
    paintRange([dragStart, dragStart]);
    canvas.setPointerCapture(event.pointerId);
    if (event.pointerType === "mouse") event.preventDefault();
  };
  const onPointerMove = (event: PointerEvent): void => {
    if (dragStart === undefined) return;
    paintRange(normalizeIndexRange(dragStart, monthAt(event)));
    if (event.pointerType === "mouse") event.preventDefault();
  };
  const onPointerUp = (event: PointerEvent): void => {
    if (dragStart === undefined) return;
    const range = normalizeIndexRange(dragStart, monthAt(event));
    dragStart = undefined;
    if (canvas.hasPointerCapture(event.pointerId))
      canvas.releasePointerCapture(event.pointerId);
    paintRange(range);
    void requestPreview(range);
  };
  const onPointerCancel = (): void => clearPreview();
  const onKeyDown = (event: KeyboardEvent): void => {
    if (event.key === "Escape" && !card.hidden) clearPreview();
  };
  const onOutsidePointerDown = (event: PointerEvent): void => {
    const target = event.target;
    if (
      !card.hidden &&
      target instanceof Node &&
      !canvas.contains(target) &&
      !card.contains(target)
    ) {
      clearPreview();
    }
  };

  canvas.addEventListener("pointerdown", onPointerDown);
  canvas.addEventListener("pointermove", onPointerMove);
  canvas.addEventListener("pointerup", onPointerUp);
  canvas.addEventListener("pointercancel", onPointerCancel);
  document.addEventListener("keydown", onKeyDown);
  document.addEventListener("pointerdown", onOutsidePointerDown);
  return () => {
    requestGeneration += 1;
    controller?.abort();
    canvas.removeEventListener("pointerdown", onPointerDown);
    canvas.removeEventListener("pointermove", onPointerMove);
    canvas.removeEventListener("pointerup", onPointerUp);
    canvas.removeEventListener("pointercancel", onPointerCancel);
    document.removeEventListener("keydown", onKeyDown);
    document.removeEventListener("pointerdown", onOutsidePointerDown);
  };
}

/** Hydrate server-rendered charts and direct non-mutating preview interactions. */
export function hydrateCharts(): void {
  cleanupPreviewInteractions?.();
  cleanupPreviewInteractions = undefined;
  const priceCanvas = document.querySelector<HTMLCanvasElement>("#price-chart");
  const volumeCanvas =
    document.querySelector<HTMLCanvasElement>("#volume-chart");
  const data = document.querySelector<HTMLPreElement>("#analysis-data");
  if (!priceCanvas || !data) return;
  const result = JSON.parse(data.textContent ?? "{}") as {
    monthly_series?: { period: string; value: string | null }[];
    mdd?: { peak?: { month?: string }; trough?: { month?: string } };
    volume_series?: VolumePoint[];
    trend_series?: { period: string; value: string | null }[];
  };
  activePriceChart?.destroy();
  activeVolumeChart?.destroy();
  activePriceChart = createPriceChart(
    priceCanvas,
    chartPointsFromResult(result),
  );

  if (volumeCanvas) {
    const volume = result.volume_series ?? [];
    const trend = (result.trend_series ?? []).map((item) => ({
      period: item.period,
      value: item.value === null ? null : Number(item.value),
    }));
    activeVolumeChart = new Chart(
      volumeCanvas,
      volumeChartConfiguration(volume, trend),
    ) as SelectableChart;
    const xScale = activeVolumeChart.scales.x;
    volumeCanvas.dataset.periodLabels = JSON.stringify(
      volume.map((point) => point.period),
    );
    volumeCanvas.dataset.periodCenters = JSON.stringify(
      volume.map((_point, index) => xScale?.getPixelForValue(index) ?? 0),
    );
    const card = document.querySelector<HTMLElement>("#analysis-preview");
    const status = document.querySelector<HTMLElement>("#brush-status");
    if (card && status && volume.length > 0) {
      cleanupPreviewInteractions = bindPreviewInteractions(
        volumeCanvas,
        volume,
        card,
        status,
      );
    }
    volumeCanvas.dataset.chartReady = "true";
  }
  priceCanvas.dataset.chartReady = "true";
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", hydrateCharts);
  document.addEventListener("htmx:afterSwap", hydrateCharts);
  if (document.readyState !== "loading") hydrateCharts();
}
