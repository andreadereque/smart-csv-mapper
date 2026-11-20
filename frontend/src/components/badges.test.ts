import { describe, expect, it } from "vitest";
import { proposal } from "../test/fixtures";
import { confidenceBadge, originLabel } from "./badges";

const base = proposal.fields[0];

describe("confidenceBadge", () => {
  it.each([
    [
      { origin: "user" as const, confidence: 0.1 },
      { label: "set by you", tone: "ok" },
    ],
    [
      { source: null, confidence: 0 },
      { label: "no column", tone: "empty" },
    ],
    [{ confidence: 0.7 }, { label: "70%", tone: "ok" }],
    [{ confidence: 0.69 }, { label: "69% · review", tone: "review" }],
  ])("%o → %o", (changes, expected) => {
    expect(confidenceBadge({ ...base, ...changes })).toEqual(expected);
  });
});

it("labels every origin", () => {
  expect(["llm", "heuristic", "user", "none"].map((o) => originLabel(o as never))).toEqual([
    "AI",
    "heuristic",
    "you",
    "—",
  ]);
});
