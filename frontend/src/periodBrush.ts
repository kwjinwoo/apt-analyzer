export interface PreviewMetric {
  status: "available" | "unavailable";
  value: string | null;
  display: string;
  unit: "%";
  evidence: string | null;
  reason: string | null;
  method?: string;
}

export interface AnalysisPreview {
  selection: {
    start: string;
    end: string;
    label: string;
    months: number;
  };
  volume: {
    value: number;
    display: string;
    unit: "건";
    evidence: string;
  };
  turnover: PreviewMetric;
  retention: PreviewMetric;
  mdd: PreviewMetric;
}

export function normalizeIndexRange(
  first: number,
  second: number,
): [number, number] {
  return first <= second ? [first, second] : [second, first];
}

export function inclusiveMonthCount(first: string, second: string): number {
  const [start, end] = first <= second ? [first, second] : [second, first];
  const [startYear, startMonth] = start.split("-").map(Number);
  const [endYear, endMonth] = end.split("-").map(Number);
  return (
    ((endYear ?? 0) - (startYear ?? 0)) * 12 +
    (endMonth ?? 1) -
    (startMonth ?? 1) +
    1
  );
}

export function monthRangeDates(
  first: string,
  second: string,
): { start: string; end: string } {
  const [start, end] = first <= second ? [first, second] : [second, first];
  const [year, month] = end.split("-").map(Number);
  const lastDay = new Date(Date.UTC(year ?? 0, month ?? 1, 0)).getUTCDate();
  return {
    start: `${start}-01`,
    end: `${end}-${String(lastDay).padStart(2, "0")}`,
  };
}

export function selectionLabel(first: string, second: string): string {
  const [start, end] = first <= second ? [first, second] : [second, first];
  return `${start.replace("-", ".")} ~ ${end.replace("-", ".")} · ${inclusiveMonthCount(start, end)}개월`;
}
