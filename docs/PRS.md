# smart-csv-mapper · Delivery plan (PRs)

Small PRs, each reviewable in 10–20 minutes, each leaving `main` working with green CI.
Decisions live in [PLAN.md](PLAN.md). Spanish version: [PRS.es.md](PRS.es.md).

**Every PR:** branch from `main` → code + tests → green CI → mutation spot-check of the tests → squash merge.

| # | Branch | Title | Status |
|---|---|---|---|
| 0 | `chore/scaffold` | Repo structure, tooling, secret scanning | ✅ merged |
| 1 | `feat/backend-skeleton` | FastAPI skeleton, settings, JSON logs, health probes, backend CI | ✅ merged |
| 2 | `feat/csv-ingest` | Upload and column profiling | ✅ merged |
| 3 | `feat/transforms` | Deterministic transform catalog and target schema | ✅ merged |
| 4 | `feat/llm-provider` | `LLMProvider` with Ollama and a fake | ✅ merged |
| 5 | `feat/mapping-suggest` | Mapping proposal with validation, retry and heuristic fallback | ✅ merged |
| 6 | `feat/ai-transforms` | AI name splitting: distinct values, batches, verification, cache | ✅ merged |
| 7 | `feat/preview-export-audit` | Preview, export, append-only audit log | ✅ merged |
| 8 | `feat/frontend-skeleton` | Vite/React/TS app, typed client, upload | ✅ merged |
| 9 | `feat/frontend-mapping` | Review table, preview, export, history | ✅ merged |
| 10 | `feat/evals` | Eval set, runner, CI job; answer checks (ADR-015) | ✅ merged |
| 11 | `chore/docker` | Non-root Dockerfiles, compose, image build + Trivy in CI | ⏳ next |
| 12 | `feat/claude-provider` | Optional Claude provider and model comparison in evals | ⏳ later |
| 13 | `docs/readme` | English README with screenshots and production section; English docs | ✅ this PR |

## What each PR delivered

- **0 · Scaffold:** `.gitignore`, `.env.example`, MIT license, `Makefile`, pre-commit with gitleaks, a `secrets` workflow. A fake GitHub token is blocked by the hook.
- **1 · Backend skeleton:** app factory, pydantic-settings, JSON logs with a request id (reset after each request), `/healthz` and `/readyz`, ruff + mypy `--strict` + pytest with 100 % coverage in CI.
- **2 · Ingest:** encoding and delimiter detection, everything read as text, stable 422 error codes, column profiles, in-memory store with TTL. Found and fixed a 500 on a huge single field.
- **3 · Transforms:** closed catalog of pure functions returning `Ok`/`Err`; target schema validation; property-based tests (EU and US formats parse to the same number).
- **4 · LLM provider:** Ollama with structured outputs and `temperature: 0`, retries with backoff only for 5xx/timeouts/network, fake provider, readiness probe checks the model.
- **5 · Mapping proposal:** versioned prompt, answer validation, one retry with errors, heuristics, calibrated confidence. A live run showed the model choosing `constant` for ids → `constant` and `map_values` became user-only.
- **6 · AI transforms:** column-level name splitting with cache and letter-by-letter verification; 10,000 rows with 50 names take 3 calls, then 0.
- **7 · Preview, export, audit:** per-cell errors, duplicate ids, CSV-injection protection, append-only SQLite audit log. Milestone A: backend demo.
- **8 · Frontend skeleton:** OpenAPI-generated types + Zod at runtime, upload with drag and drop, MSW tests, CI that fails if the types drift.
- **9 · Frontend mapping:** review table with confidence badges and "set by you", preview with highlighted cells, export with "skip invalid rows", history. Milestone B: full web demo.
- **10 · Evals:** 15 labelled CSVs and 60 names; v1 scored 65 % on column + transform; answer checks and v2 prompts reached 97 %; runs in CI on Ollama.
- **13 · Docs:** this README, screenshots, production section, English docs.

## Next

- **11 · Docker:** multi-stage backend image with uv, non-root user, port 8080, group-0 write permissions (OpenShift); unprivileged nginx for the frontend; compose with Redis and host Ollama; build + Trivy scan in CI.
- **12 · Claude provider:** `ClaudeProvider` behind the same interface, active only with `ANTHROPIC_API_KEY`; `make eval` to compare models on cost, quality and latency.
