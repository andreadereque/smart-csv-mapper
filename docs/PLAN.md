# smart-csv-mapper · Development plan and architecture decisions (ADRs)

> Status: **accepted** · Started: 2026-11-20 · Spanish version: [PLAN.es.md](PLAN.es.md)
> A living document: every decision has an ADR. When a decision changes, the old ADR is marked
> *Superseded* and a new one is added; nothing is deleted.

## 1. Context

When onboarding a new client, each one sends CSV files with different columns: names, order, date and
number formats, and sometimes columns that need transforming, such as a full name that must be split into
first and last name. Setting up each integration by hand takes days of engineering work.

**smart-csv-mapper** is an open, simplified version of a system I built in production. An LLM **proposes**
how the file's columns fit a fixed target schema, a person **reviews and corrects** it, and transforms are
**deterministic** wherever possible. AI is only used where code can't do the job, on **distinct values**,
with a **cache**.

It is a practice and portfolio project. It uses **fake data only** and contains no company code.

### Development machine
- Apple M2 with **8 GB of RAM**: this drives the size of the local model and the Docker decision.
- Python 3.13, uv, Node, npm, git, gh; Ollama installed with Homebrew.

## 2. Goals

1. Upload a CSV and get, in seconds, a mapping proposal to the target schema with a confidence per field.
2. Review and edit the mapping in a web UI, and see a preview with errors before exporting.
3. Deterministic transforms for the common cases; AI only as a last resort, on distinct values, batched and cached.
4. Measure quality with reproducible **evals** instead of "it seems to work".
5. Zero cost: develop, test and run CI without paying anything.
6. Simple code that can be explained line by line.

## 3. Non-goals (out of scope on purpose)

- Authentication and multi-user support (covered in the README's production section).
- Persisting the imported data. Only the audit log is stored.
- Very large files and asynchronous processing with queues or Kafka.
- User-configurable target schemas. The schema is fixed, but defined in one place so changing it is easy.
- Deployment to Kubernetes or OpenShift (a separate project).

## 4. Target schema

| Field | Type | Required | Validation | Transforms the model may choose |
|---|---|---|---|---|
| `external_id` | string | yes | non-empty, unique in the file | `trim` |
| `first_name` | string | yes | non-empty | `trim`, `split_name_first` |
| `last_name` | string | yes | non-empty | `trim`, `split_name_last` |
| `email` | email | no | email format | `lowercase_trim`, `trim` |
| `phone` | phone | no | E.164 (`+34612345678`) | `normalize_phone` |
| `amount_due` | decimal | yes | ≥ 0, two decimals | `parse_eu_number`, `parse_us_number` |
| `due_date` | date | no | ISO 8601 (`2026-11-20`) | `parse_date` |

---

## 5. Decisions (ADRs)

### ADR-001 · Monorepo with backend and frontend
- **Status:** Accepted
- **Context:** One person, one product, and changes that often touch both sides (a new API field, say).
- **Decision:** One repository with `backend/`, `frontend/`, `evals/` and `docs/`, and a root `Makefile` with the common commands.
- **Alternatives:** two repositories. Rejected: it forces coordinating versions and PRs for no gain at this size.
- **Consequences:** CI uses path filters so frontend tests don't run when only the backend changes.

### ADR-002 · Python backend with FastAPI, Pydantic v2 and uv
- **Status:** Accepted
- **Context:** The target role asks for FastAPI. Pydantic validates both the API and the model's output.
- **Decision:** Python 3.12+, FastAPI, Pydantic v2, pydantic-settings, managed with **uv**. CSV parsing with the standard `csv` module plus `charset-normalizer` (**no pandas**).
- **Alternatives:** pandas (convenient, but heavy, and it infers types silently: the opposite of what we want); Node for everything.
- **Consequences:** Full control over types (everything is read as text and transformed explicitly). ruff, mypy `--strict`, pytest.

### ADR-003 · React, TypeScript, Vite, TanStack Query and Zod frontend
- **Status:** Accepted
- **Decision:** Vite + React + strict TypeScript; TanStack Query for server state; types generated from the backend's OpenAPI, plus Zod for runtime validation; plain CSS.
- **Alternatives:** Next.js (no SSR or SEO needed); Redux (server state belongs to TanStack Query).
- **Consequences:** If the API changes, the types are regenerated and `tsc` fails where the contract breaks; a CI job fails if they drift.
- **Notes:** TypeScript 6 (typescript-eslint doesn't support 7 yet); npm ≥ 11 (npm 10.9 crashes resolving peers); Vitest 5 (Vitest 3 pulled critical advisories).

### ADR-004 · Pluggable model provider, Ollama by default
- **Status:** Accepted
- **Context:** Zero cost; 8 GB of RAM; we want to compare models with evals.
- **Decision:** An `LLMProvider` interface (`complete_json(prompt, schema)`, `is_ready()`). `OllamaProvider` (default, local API, **structured outputs** via `format` + JSON Schema, `temperature: 0`) and `FakeProvider` for tests; an optional Claude provider later. Default model **`qwen2.5:3b`** (~2 GB).
- **Alternatives:** Claude only (costs money, needs a key); 7–8B models (don't fit well in 8 GB next to everything else).
- **Consequences:** A 3B model makes more mistakes. We compensate with strict checks, a retry, heuristic fallbacks and human review, and we measure it with evals.

### ADR-005 · Mapping proposal: model + validation + heuristic fallback
- **Status:** Accepted (extended by ADR-015)
- **Decision:**
  1. Profile each column: name, 5 distinct samples, distinct count, empty ratio. **The whole file is never sent.**
  2. The prompt lists the target schema, the **closed catalog of transforms** and the column profiles; samples are marked as data.
  3. The answer is validated with Pydantic (`LLMMappingAnswer`) and against reality: the column exists, the transform is allowed, params are right.
  4. On failure, **one retry** with the errors in the prompt; then **header heuristics** (synonyms in several languages, whole-word and fuzzy matching, sample-based format detection).
  5. The prompt is versioned (`PROMPT_VERSION`) and the version goes into logs and cache keys.
- **Alternatives:** letting the model write transform code (non-deterministic, unsafe, unreviewable).
- **Consequences:** The user always gets a proposal, and each field says where it came from (`llm`, `heuristic`, `user`) and how far to trust it.

### ADR-006 · Deterministic transforms as a catalog of named functions
- **Status:** Accepted
- **Decision:** Pure Python functions with names (`trim`, `lowercase_trim`, `parse_eu_number`, `parse_us_number`, `parse_date(format)`, `normalize_phone(default_country)`, `constant(value)`, `map_values(table)`), each returning `Ok(value)` or `Err(reason)`, never raising. `constant` and `map_values` are **for people only**: in a live run the model picked `constant` for the id column.
- **Alternatives:** JSONata (more powerful, closer to the original system, but another language to explain; listed as a future improvement).
- **Consequences:** One test per function, plus property-based tests; the catalog is the model's whitelist.

### ADR-007 · AI transforms: distinct values, batches and cache
- **Status:** Accepted
- **Decision:** For `split_name_first` / `split_name_last`: distinct values → cache lookup (key = `sha256(transform | prompt_version | model | value)`) → misses to the model in **batches of 20** → accept only answers where first + last rebuild the input **letter by letter** → retry the failures once → cache for 30 days → apply to every row. `InMemoryCache` by default, `RedisCache` when `REDIS_URL` is set.
- **Alternatives:** one call per row (slow, costly, inconsistent); semantic cache (exact repeats are enough here).
- **Consequences:** Consistent results within and across files; stats (rows, distinct, cache hits, model calls) shown in the UI.

### ADR-008 · Minimal storage: uploads in memory, audit log in SQLite
- **Status:** Accepted
- **Decision:** Uploads in memory with an id, a 1 h TTL and limits (**10 MB, 50,000 rows**). Audit log in **SQLite**, append-only (triggers reject UPDATE and DELETE): user, file name, **SHA-256 of the file (never its content)**, final mapping, model, AI stats.
- **Alternatives:** PostgreSQL (deferred to the production section).
- **Consequences:** Restarting the backend loses in-flight uploads: acceptable for a demo.

### ADR-009 · Reproducible, free evals, also in CI
- **Status:** Accepted
- **Decision:** 15 fake CSVs in different styles with hand-labelled `*.expected.json`, and 60 names with their correct split. Metrics: **column right**, **column + transform + params right** (the threshold uses this one), name split exact match, latency. `make eval` writes a report to `evals/results/`; CI runs it on Ollama (CPU) when prompts, transforms or the eval set change, and fails below **90 %**.
- **Alternatives:** an LLM judge (there is an exact answer here; a judge adds noise and cost); local-only evals.
- **Consequences:** Unit tests **never** call a real model; only the evals do. The CI job takes ~20–30 min on CPU.

### ADR-010 · Testing strategy
- **Status:** Accepted
- **Decision:** pytest (unit tests per transform, mapping tests with `FakeProvider`, API tests with `TestClient`), Vitest + Testing Library + MSW for the UI. **100 % branch coverage** on both sides. A **mutation spot-check** on every PR. No browser end-to-end tests yet (listed as an improvement).

### ADR-011 · Security and privacy
- **Status:** Accepted
- **Decision:** fake data only; secrets in `.env` (ignored) with a value-less `.env.example`; **gitleaks** in pre-commit and CI; upload size and type limits; **CSV injection protection** on export; the model only sees 5 samples per column, and only the affected column for AI transforms; with Ollama, data never leaves the machine.

### ADR-012 · Native development, optional Docker
- **Status:** Accepted
- **Context:** With 8 GB of RAM, Docker Desktop plus Ollama is tight, and Ollama in Docker on a Mac can't use the GPU.
- **Decision:** Native development (`make dev`); Dockerfiles (non-root, high port, OpenShift-friendly) and a compose file are a separate step.

### ADR-013 · Minimal observability
- **Status:** Accepted
- **Decision:** JSON logs with a `request_id`; every model call logs provider, model, latency and tokens; `/healthz` (process up) and `/readyz` (model reachable).
- **Alternatives:** full OpenTelemetry (production section).

### ADR-014 · Code quality and workflow
- **Status:** Accepted
- **Decision:** every change through a PR with green CI and squash merge; Conventional Commits; pre-commit (ruff, mypy, gitleaks); **no ternary operators** (explicit `if` for readability; ESLint `no-ternary` and a CI grep for Python).

### ADR-015 · Type-check the model's answer against the data
- **Status:** Accepted (added after the first eval run)
- **Context:** The first eval run scored 94 % on columns but only **65 % on column + transform**: the model lowercased ids, split columns that were already split, misread number formats, and the heuristic took "Amount Due" for the due date.
- **Decision:** Before accepting the model's choice for a field:
  - the transform must be one of the field's **fitting transforms** (§4);
  - the transform (and the field's validation) is **dry-run on the column's samples**; if half or more fail, the answer is sent back with the reason;
  - `split_name_*` only on columns where most samples hold two or more words;
  - heuristics never reuse a column the model already assigned (except the full-name pair).
  The name check became case-sensitive. Prompts moved to `mapping_v2` and `split_name_v2`.
- **Alternatives:** prompt wording only (helps, but doesn't guarantee anything); a bigger model (doesn't fit the zero-cost, 8 GB constraint).
- **Consequences:** Mapping accuracy **64.8 % → 97.1 %**, name split **93.3 % → 96.7 %**; latency per proposal **13 s → 23 s** because of retries. `maría lópez` now fails visibly instead of silently becoming `López`.

---

## 6. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| The 3B model maps badly | Medium | Answer checks, a retry, heuristics, human review, evals to measure it |
| Ollama slow or out of memory on 8 GB | Medium | 3B model, small batches |
| The evals CI job is too slow | Medium | Path filters, model cache; manual or nightly runs if needed |
| Code hard to explain | Medium | Small PRs, test reviews on every PR |

## 7. Definition of done

- `make dev` works on a clean Mac following the README.
- Green CI: lint, types, tests, 100 % coverage, gitleaks, generated types in sync, evals ≥ 90 %.
- Eval reports committed in `evals/results/`.
- English README with screenshots, eval results and a production section.
