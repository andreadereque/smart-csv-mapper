import type { AIStats } from "../api/schemas";

export function AIStatsLine({ stats }: { stats: AIStats[] }) {
  return (
    <>
      {stats.map((s) => (
        <p key={`${s.transform}-${s.source}`} className="stats">
          AI {s.transform} on “{s.source}”: {s.rows} rows · {s.distinct} distinct · {s.cache_hits}{" "}
          from cache · {s.llm_calls} model calls · {s.failed} failed · {(s.ms / 1000).toFixed(1)} s
        </p>
      ))}
    </>
  );
}
