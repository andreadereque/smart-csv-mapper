# smart-csv-mapper

Upload a CSV with messy, client-specific columns and get clean rows in a fixed target schema.
An LLM **proposes** the column mapping, a person **reviews** it, and transformations are
**deterministic** wherever possible. AI is only a fallback, called on **distinct values** and **cached**.

> Work in progress. See [docs/PLAN.md](docs/PLAN.md) for the design decisions (ADRs)
> and [docs/PRS.md](docs/PRS.md) for the delivery plan.

- Runs **free and local** with [Ollama](https://ollama.com) (`qwen2.5:3b`); data never leaves the machine.
- Fake data only.

## Design decisions

- **App factory + settings from the environment** (`create_app`, pydantic-settings): each test builds its own app; no global state.
- **JSON logs with a request id** (`X-Request-ID`), kept in a `ContextVar` and reset after each request so it can't leak.
- **Everything is read as text; no pandas.** Types are decided later by explicit transforms, never guessed silently.
- **Encoding and delimiter detection:** UTF-8 (with BOM) first, then charset-normalizer; `csv.Sniffer` with a counting fallback.
- **Stable error codes** (`duplicate_header`, `too_many_rows`, `malformed_csv`…) returned as 422, so the UI can explain each problem.
- **Only a profile leaves the parser:** 5 distinct samples, distinct count and empty ratio per column. The LLM never sees the whole file.
- **A closed catalog of named, pure transforms** (`trim`, `parse_eu_number`, `normalize_phone`, `map_values`…). Each returns `Ok(value)` or `Err(reason)` and never raises; the LLM may only pick from this list.
- **Transforms and validation are separate steps:** a transform reshapes the text, then the target schema validates it (required, E.164, ≥ 0, ISO date). Empty stays empty until the schema decides.
- **Uploads live in memory with a 1 h TTL** (10 MB / 50k rows limits); persistence is out of scope.

## License

MIT
