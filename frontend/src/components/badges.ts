import type { FieldMapping } from "../api/schemas";

export const REVIEW_THRESHOLD = 0.7;

export type Badge = { label: string; tone: "ok" | "review" | "empty" };

export function confidenceBadge(field: FieldMapping): Badge {
  if (field.origin === "user") {
    return { label: "set by you", tone: "ok" };
  }
  if (field.source === null) {
    return { label: "no column", tone: "empty" };
  }
  const percent = `${Math.round(field.confidence * 100)}%`;
  if (field.confidence >= REVIEW_THRESHOLD) {
    return { label: percent, tone: "ok" };
  }
  return { label: `${percent} · review`, tone: "review" };
}

export function originLabel(origin: FieldMapping["origin"]): string {
  const labels = { llm: "AI", heuristic: "heuristic", user: "you", none: "—" };
  return labels[origin];
}
