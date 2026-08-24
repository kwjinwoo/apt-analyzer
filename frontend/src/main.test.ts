import { describe, expect, it } from "vitest";

import { priceChartConfiguration } from "./chartConfig";

describe("local web foundation", () => {
  it("preserves zero observations separately from unavailable values", () => {
    const configuration = priceChartConfiguration([
      { period: "2024-01", value: 0 },
      { period: "2024-02", value: null },
    ]);

    expect(configuration.type).toBe("line");
    expect(configuration.data.labels).toEqual(["2024-01", "2024-02"]);
    expect(configuration.data.datasets[0]?.data).toEqual([0, null]);
    expect(configuration.data.datasets[0]?.spanGaps).toBe(false);
  });
});
