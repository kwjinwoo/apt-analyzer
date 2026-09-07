import { describe, expect, it } from "vitest";

import {
  priceChartConfiguration,
  volumeChartConfiguration,
} from "./chartConfig";
import { chartPointsFromResult } from "./chartSeries";
import {
  inclusiveMonthCount,
  monthRangeDates,
  normalizeIndexRange,
  selectionLabel,
} from "./periodBrush";

describe("local web foundation", () => {
  it("normalizes reverse drag indices and derives whole-month request dates", () => {
    expect(normalizeIndexRange(11, 2)).toEqual([2, 11]);
    expect(monthRangeDates("2022-08", "2021-09")).toEqual({
      start: "2021-09-01",
      end: "2022-08-31",
    });
    expect(monthRangeDates("2024-02", "2024-02")).toEqual({
      start: "2024-02-01",
      end: "2024-02-29",
    });
  });

  it("formats an inclusive direct-preview range", () => {
    expect(inclusiveMonthCount("2021-09", "2022-08")).toBe(12);
    expect(selectionLabel("2022-08", "2021-09")).toBe(
      "2021.09 ~ 2022.08 · 12개월",
    );
  });
  it("preserves expanded monthly null gaps", () => {
    expect(
      chartPointsFromResult({
        monthly_series: [
          { period: "2024-01", value: "100" },
          { period: "2024-02", value: null },
        ],
      }),
    ).toEqual([
      { period: "2024-01", value: 100 },
      { period: "2024-02", value: null },
    ]);
  });
  it("preserves zero observations separately from unavailable values", () => {
    const configuration = priceChartConfiguration([
      { period: "2024-01", value: 0 },
      { period: "2024-02", value: null },
    ]);

    expect(configuration.type).toBe("line");
    expect(configuration.data.labels).toEqual(["2024-01", "2024-02"]);
    expect(configuration.data.datasets[0]?.data).toEqual([0, null]);
    expect(configuration.data.datasets[0]?.spanGaps).toBe(false);
    expect(configuration.data.datasets[0]?.label).toContain("관측 가격");
  });

  it("marks MDD peak and trough on the same observed series", () => {
    const configuration = priceChartConfiguration([
      { period: "2024-01", value: 100, marker: "peak" },
      { period: "2024-02", value: 80, marker: "trough" },
    ]);
    expect(configuration.data.datasets[0]?.pointBackgroundColor).toEqual([
      "#b42318",
      "#175cd3",
    ]);
  });

  it("provides an accessible volume chart with valid-empty and unavailable gaps", () => {
    const configuration = volumeChartConfiguration([
      { period: "2024-01", value: 0 },
      { period: "2024-02", value: null },
    ]);
    expect(configuration.type).toBe("bar");
    expect(configuration.data.datasets[0]?.data).toEqual([0, null]);
    expect(configuration.data.datasets[0]?.label).toBe("유효 거래량");
    expect(configuration.options?.plugins?.title?.text).toBe(
      "월별 유효 거래량",
    );
  });

  it("renders the supporting three-month series as a labeled line with null gaps", () => {
    const configuration = volumeChartConfiguration(
      [
        { period: "2024-01", value: 1 },
        { period: "2024-02", value: 2 },
      ],
      [
        { period: "2024-01", value: null },
        { period: "2024-02", value: 1.5 },
      ],
    );
    expect(configuration.data.datasets[1]?.label).toContain("3개월");
    expect(configuration.data.datasets[1]?.type).toBe("line");
    expect(configuration.data.datasets[1]?.data).toEqual([null, 1.5]);
  });
});
