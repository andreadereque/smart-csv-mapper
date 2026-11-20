# smart-csv-mapper

Upload a CSV with messy, client-specific columns and get clean rows in a fixed target schema.
An LLM **proposes** the column mapping, a person **reviews** it, and transformations are
**deterministic** wherever possible. AI is only a fallback, called on **distinct values** and **cached**.

> Work in progress. See [docs/PLAN.md](docs/PLAN.md) for the design decisions (ADRs)
> and [docs/PRS.md](docs/PRS.md) for the delivery plan.

- Runs **free and local** with [Ollama](https://ollama.com) (`qwen2.5:3b`); data never leaves the machine.
- Fake data only.

## Run it

```bash
make ollama-setup          # once: start Ollama and pull qwen2.5:3b
make install               # backend (uv) and frontend (npm 11) dependencies
make dev                   # UI on http://localhost:5173, API on http://localhost:8000/docs
```

Upload `examples/clientes_demo.csv`, review the proposed mapping (yellow rows need a look), preview the
first 20 rows with per-cell errors, then export. Invalid rows are explained, and you can export without them.

### Or drive the API with curl

```bash
FID=$(curl -s -F file=@examples/clientes_demo.csv localhost:8000/files | jq -r .file_id)
curl -s -X POST localhost:8000/files/$FID/suggest > proposal.json      # the model's proposal
jq '{fields, rows: 5}' proposal.json | curl -s -X POST -H 'content-type: application/json' \
  -d @- localhost:8000/files/$FID/preview                               # first rows + errors
jq '{fields, skip_invalid: true}' proposal.json | curl -s -X POST -H 'content-type: application/json' \
  -d @- localhost:8000/files/$FID/export -o clean.csv                   # full file
curl -s localhost:8000/audit                                            # who exported what
```

Live run on an M2 with 8 GB (`examples/clientes_demo.csv`, 300 rows, fake data): proposal in 13 s with the
full-name column mapped to `split_name_first` / `split_name_last`; export in 32 s with **33 distinct names →
3 model calls** (5 already cached by the preview); 299 rows exported, 1 skipped (invalid email on row 150).
The model proposed `lowercase_trim` for the id column, which a person fixes in review: that is the point.

## Design decisions

- **App factory + settings from the environment** (`create_app`, pydantic-settings): each test builds its own app; no global state.
- **JSON logs with a request id** (`X-Request-ID`), kept in a `ContextVar` and reset after each request so it can't leak.
- **Everything is read as text; no pandas.** Types are decided later by explicit transforms, never guessed silently.
- **Encoding and delimiter detection:** UTF-8 (with BOM) first, then charset-normalizer; `csv.Sniffer` with a counting fallback.
- **Stable error codes** (`duplicate_header`, `too_many_rows`, `malformed_csv`…) returned as 422, so the UI can explain each problem.
- **Only a profile leaves the parser:** 5 distinct samples, distinct count and empty ratio per column. The LLM never sees the whole file.
- **A closed catalog of named, pure transforms** (`trim`, `parse_eu_number`, `normalize_phone`, `map_values`…). Each returns `Ok(value)` or `Err(reason)` and never raises; the LLM may only pick from this list.
- **Transforms and validation are separate steps:** a transform reshapes the text, then the target schema validates it (required, E.164, ≥ 0, ISO date). Empty stays empty until the schema decides.
- **One `LLMProvider` interface** (`complete_json(prompt, schema)`, `is_ready()`), with Ollama by default and a scripted `FakeProvider` for tests. Ollama gets the JSON Schema as `format` (structured outputs) and `temperature: 0`.
- **Retries only where they help:** network errors, timeouts and 5xx are retried with exponential backoff; 4xx (e.g. model not pulled) fails fast.
- **`/readyz` checks the model, `/healthz` never does:** a stopped model should take the API out of rotation, not restart it.
- **Mapping = model proposal, checked against reality.** The prompt (versioned, `mapping_v1`) lists the schema, the allowed transforms and the column profiles; samples are marked as data, not instructions. The answer schema uses enums for targets and transforms.
- **Semantic validation + one retry:** unknown columns, disallowed transforms, missing params and duplicate targets are sent back to the model once; then the system falls back to header heuristics (synonyms in Spanish and English, whole-word and fuzzy matching, sample-based number and date format detection).
- **Some transforms are for people only** (`constant`, `map_values`): in a live test the 3B model chose `constant` for the id column, which would have given every row the same id.
- **Self-reported confidence isn't trusted:** the 3B model says 1.0 for everything, so a score above 0.6 is kept only when the header heuristic points to the same column.
- **AI transforms run on the column, not on the cell** (`split_name_first` / `split_name_last`): distinct values only → cache lookup → misses in batches of 20 → results applied to every row. Live run: 1,000 rows, 10 distinct names → 1 model call (13 s); second run → 0 calls.
- **The model may choose where to cut a name, never what it says:** an answer is accepted only if first + last rebuilds the input letter by letter (ignoring spaces, case and a "Surname, First" comma). Failed values are retried once, alone; then they become per-cell errors and are never cached.
- **Cache key = transform + prompt version + model + value**, so changing the prompt or the model never serves stale results. In memory by default, Redis when `REDIS_URL` is set.
- **Preview processes the first rows only** (20 by default), so it stays fast even with AI transforms; export processes the whole file and reuses whatever the preview cached.
- **Export refuses invalid rows unless asked** (`skip_invalid`), and says which cell failed and why. Duplicate `external_id`s are errors.
- **CSV injection protection:** cells starting with `=`, `@`, tab or CR get a leading `'`; `+`/`-` only when the cell is not a plain number or an E.164 phone, so `+34612345678` survives.
- **Append-only audit log in SQLite** (triggers reject UPDATE and DELETE): user, file name and SHA-256 (never the content), mapping, model and AI stats.
- **Frontend types come from the backend's OpenAPI** (`npm run gen:api`), and every response is also checked at runtime with Zod schemas that `satisfies` those types: if the contract drifts, `tsc` fails; if a response is wrong anyway, the UI says so instead of crashing. CI regenerates the types and fails if they changed.
- **The UI never trusts the proposal silently:** low-confidence rows are yellow, every edit is marked "set by you" (and sent as `origin: user`), changing a transform clears its old params, and AI transforms are labelled.
- **Server state with TanStack Query**, no global store; tests mock only the network, with MSW.
- **Uploads live in memory with a 1 h TTL** (10 MB / 50k rows limits); persistence is out of scope.

## License

MIT
