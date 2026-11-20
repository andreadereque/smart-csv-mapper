# smart-csv-mapper · Plan de PRs

Cada PR es pequeño, se puede revisar en 10–20 minutos y deja `main` funcionando con el CI en verde. Las decisiones de fondo están en [PLAN.es.md](PLAN.es.md); aquí se indica qué ADR aplica cada PR.

**Cómo trabajamos cada PR**
1. Rama desde `main` con el nombre indicado.
2. Yo escribo el código y los tests; tú lo revisas y te explico cada fichero.
3. CI en verde → squash merge (lo apruebas tú).
4. Revisión de la calidad de los tests (skill `test-quality-review`) y chuleta del PR (skill `cheatsheet`) en `NOTES.md`, que es privado y no se sube.

**Hitos**
- **Hito A, demo de backend (PR 0–7):** la API completa funciona con Ollama, probada con `curl` o desde `/docs`.
- **Hito B, demo completa (PR 8–9):** interfaz web de punta a punta.
- **Hito C, portfolio (PR 10–13):** evals en CI, Docker, Claude opcional y README final.

| # | Rama | Título | Tamaño | Hito |
|---|---|---|---|---|
| 0 | `chore/scaffold` | Estructura del repo, tooling y docs | S | A |
| 1 | `feat/backend-skeleton` | Esqueleto FastAPI, config, logs, health y CI de backend | S | A |
| 2 | `feat/csv-ingest` | Subida y perfilado de CSV | M | A |
| 3 | `feat/transforms` | Catálogo de transformaciones deterministas y esquema destino | M | A |
| 4 | `feat/llm-provider` | Interfaz LLMProvider con Ollama y Fake | S | A |
| 5 | `feat/mapping-suggest` | Propuesta de mapeo con LLM, validación y respaldo | M | A |
| 6 | `feat/ai-transforms` | Transformaciones con IA: valores únicos, lotes y caché | M | A |
| 7 | `feat/preview-export-audit` | Vista previa, exportación y log de auditoría | M | A |
| 8 | `feat/frontend-skeleton` | Frontend Vite/React/TS, cliente tipado y subida | M | B |
| 9 | `feat/frontend-mapping` | Tabla de mapeo, vista previa, exportación y estadísticas | L | B |
| 10 | `feat/evals` | Dataset, runner de evals e informe; job de CI con Ollama | M | C |
| 11 | `chore/docker` | Dockerfiles no-root, compose y build + Trivy en CI | S | C |
| 12 | `feat/claude-provider` | Proveedor Claude opcional y comparativa en evals | S | C |
| 13 | `docs/readme` | README en inglés, diagrama, GIF y producción; docs en inglés | S | C |

---

## PR 0 · `chore/scaffold` — Estructura del repo, tooling y docs
**ADR:** 001, 011, 014
- **Incluye:**
  - `git init` y repo público en GitHub (`gh repo create`, lo confirmas tú).
  - Carpetas `backend/`, `frontend/`, `evals/`, `docs/` (con PLAN.md y PRS.md). `NOTES.md` y `CLAUDE.md` quedan fuera de git.
  - `.gitignore` (Python, Node, `.env`, `*.sqlite`), `.env.example`, licencia MIT y un README mínimo.
  - `Makefile` con objetivos vacíos (`dev`, `test`, `lint`, `eval`).
  - `.pre-commit-config.yaml` con gitleaks (el resto de hooks llega en cada PR).
  - Repositorio **privado** al principio; se hace público al final (PR 13), cuando lo hayas revisado.
- **Criterios de aceptación:** `pre-commit run --all-files` pasa; gitleaks detecta una clave falsa de prueba si se añade.

## PR 1 · `feat/backend-skeleton` — Esqueleto FastAPI, config, logs, health y CI de backend
**ADR:** 002, 010, 013
- **Incluye:**
  - Proyecto uv en `backend/` (`pyproject.toml`), app FastAPI con *app factory*.
  - `Settings` con pydantic-settings (`LLM_PROVIDER`, `LLM_MODEL`, `OLLAMA_URL`, `REDIS_URL`, límites).
  - Logs JSON con `request_id` (middleware).
  - `/healthz`; `/readyz` de momento solo devuelve ok.
  - Configuración de ruff, mypy estricto y pytest + cobertura.
  - Workflow `.github/workflows/backend.yml`: lint, tipos y tests en PRs que tocan `backend/`.
- **Criterios de aceptación:** `make dev-backend` sirve `/docs`; tests de health; CI en verde.

## PR 2 · `feat/csv-ingest` — Subida y perfilado de CSV
**ADR:** 002, 008, 011
- **Incluye:**
  - `POST /files`: valida el tipo y el tamaño (≤ 10 MB, ≤ 50.000 filas), detecta la codificación (charset-normalizer) y el delimitador (`csv.Sniffer`, con respaldo `,` `;` `\t`), y lee todo como texto.
  - Almacén en memoria con id y TTL de 1 h (interfaz `FileStore`).
  - Perfil por columna: nombre, 5 muestras, número de valores únicos y % de vacíos. Respuesta `FileProfile`.
  - Errores claros: fichero vacío, cabeceras duplicadas, codificación ilegible.
  - Primeros 4 CSV de ejemplo en `backend/tests/fixtures/`.
- **Criterios de aceptación:** tests con UTF-8, Latin-1, `;`, comillas y saltos de línea dentro de celda; límites de tamaño probados.

## PR 3 · `feat/transforms` — Catálogo de transformaciones deterministas y esquema destino
**ADR:** 006
- **Incluye:**
  - `schema.py`: el esquema destino (sección 4 del PLAN) en un solo sitio, con validadores por campo.
  - `transforms/`: registro de funciones puras (`trim`, `lowercase_trim`, `parse_eu_number`, `parse_us_number`, `parse_date`, `normalize_phone`, `constant`, `map_values`). Cada función devuelve `Ok(valor) | Err(motivo)`.
  - Endpoint `GET /transforms`, que lista el catálogo (lo usarán el frontend y el prompt).
- **Criterios de aceptación:** tests por función con casos límite (`"1.250,50"`, `"1,250.50"`, `"-0"`, fechas imposibles, teléfonos con prefijo o sin él). Tests de propiedades con **hypothesis** para los parsers de números.

## PR 4 · `feat/llm-provider` — Interfaz LLMProvider con Ollama y Fake
**ADR:** 004, 013
- **Incluye:**
  - `LLMProvider` (Protocol) con `complete_json(prompt, schema, *, timeout)`.
  - `OllamaProvider` con httpx, `format=<JSON Schema>`, `temperature=0`, timeout y reintentos con backoff ante errores de red.
  - `FakeProvider` con respuestas grabadas.
  - Log de cada llamada: modelo, latencia y tokens.
  - `/readyz` comprueba que Ollama responde.
  - `make ollama-setup`: `ollama pull qwen2.5:3b`.
- **Criterios de aceptación:** tests con `FakeProvider` y con `respx` simulando la API de Ollama (timeout, 500, JSON roto); prueba manual documentada con Ollama real.

## PR 5 · `feat/mapping-suggest` — Propuesta de mapeo con LLM, validación y respaldo
**ADR:** 005
- **Incluye:**
  - `prompts/mapping_v1.md` con `PROMPT_VERSION`.
  - `POST /files/{id}/suggest`, que devuelve `MappingProposal`: por campo destino, la columna origen, la transformación con sus parámetros, la confianza y el origen (`llm` o `heuristic`).
  - Validación semántica: la columna existe, la transformación está en el catálogo y no hay campos obligatorios sin cubrir sin aviso.
  - Un reintento con el error incluido en el prompt; después, respaldo heurístico (`difflib` + sinónimos en español e inglés).
- **Criterios de aceptación:** tests con el Fake para el caso correcto, JSON inválido, columna inventada, transformación inventada, el reintento que funciona y el respaldo total.

## PR 6 · `feat/ai-transforms` — Transformaciones con IA: valores únicos, lotes y caché
**ADR:** 007
- **Incluye:**
  - Transformaciones con IA `split_name_first` y `split_name_last` (comparten una llamada que devuelve las dos partes).
  - Interfaz `Cache` con `InMemoryCache` y `RedisCache` (activa si existe `REDIS_URL`). Clave `sha256(transform|prompt_version|model|valor)` y TTL de 30 días.
  - Flujo: valores únicos → caché → lotes de 20 al modelo → validar → guardar.
  - `TransformStats` (filas, únicos, aciertos de caché, llamadas y ms).
- **Criterios de aceptación:**
  - Un test demuestra que 10.000 filas con 50 nombres únicos hacen como máximo 3 llamadas, y que una segunda ejecución hace 0.
  - Tests de lote parcialmente inválido (se reintentan solo los que fallan).

## PR 7 · `feat/preview-export-audit` — Vista previa, exportación y log de auditoría
**ADR:** 008, 011
- **Incluye:**
  - `POST /files/{id}/preview` (mapeo editado por el usuario → primeras 20 filas transformadas + errores por celda + resumen de errores).
  - `POST /files/{id}/export` (fichero completo → CSV descargable con protección contra CSV injection, o un informe de errores si los hay y no se ha pedido `skip_invalid`).
  - Detección de `external_id` duplicados.
  - Log de auditoría en SQLite, solo de inserción.
  - `GET /audit` (últimas 50 entradas).
- **Criterios de aceptación:** tests de punta a punta de la API con el Fake: subir → sugerir → vista previa → exportar; celda `=SUM(A1)` exportada como `'=SUM(A1)`.
- **Hito A completado:** demo por `curl` documentada en el README.

## PR 8 · `feat/frontend-skeleton` — Frontend Vite/React/TS, cliente tipado y subida
**ADR:** 003, 010
- **Incluye:**
  - Vite + React + TS estricto, ESLint y Prettier.
  - Tipos generados desde `/openapi.json` (`npm run gen:api`) y cliente fetch con validación Zod.
  - TanStack Query.
  - Página de subida con *drag and drop*, que muestra el perfil de columnas y los estados de carga, vacío y error.
  - Proxy de Vite al backend.
  - Workflow `frontend.yml`: lint, `tsc`, Vitest y build.
- **Criterios de aceptación:** tests de la subida con MSW; CI en verde.

## PR 9 · `feat/frontend-mapping` — Tabla de mapeo, vista previa, exportación y estadísticas
**ADR:** 003
- **Incluye:**
  - Pantalla de revisión: una fila por campo destino, con desplegable de columna origen, desplegable de transformación con sus parámetros, insignia de confianza (amarillo si < 0,7) y etiqueta `IA` o `heurística`.
  - Botón "Vista previa", con una tabla con los errores resaltados por celda.
  - Panel de estadísticas de las transformaciones con IA ("10.000 filas · 3.000 únicos · 2.600 de caché · 400 llamadas").
  - Botón "Exportar" y página de historial (audit log).
  - Accesibilidad básica (labels, foco y contraste).
- **Criterios de aceptación:** tests de la tabla (editar un mapeo cambia la petición de vista previa) y de los estados de error; demo manual completa con Ollama.
- **Hito B completado: demo completa.**

## PR 10 · `feat/evals` — Dataset, runner de evals e informe; job de CI con Ollama
**ADR:** 009
- **Incluye:**
  - `evals/datasets/`: 15 CSV inventados + `expected_mapping.json` cada uno.
  - `evals/name_split.jsonl` con unos 60 casos.
  - `evals/run.py`, que calcula la precisión del mapeo por campo, la precisión de la separación de nombres, el % de respaldo y la latencia, y genera un informe en Markdown en `evals/results/`.
  - `make eval`.
  - Workflow `evals.yml`: instala Ollama en el runner, descarga el modelo y ejecuta las evals cuando cambian prompts, mapeo o evals (o manualmente); falla por debajo del umbral.
- **Criterios de aceptación:** primer informe real publicado; umbral fijado en función de él; el CI ha fallado al menos una vez a propósito en un PR de prueba con un prompt roto (y se documenta).

## PR 11 · `chore/docker` — Dockerfiles no-root, compose y build + Trivy en CI
**ADR:** 012
- **Incluye:**
  - `backend/Dockerfile` multi-stage con uv, usuario no root, puerto 8080 y permisos de grupo 0 (compatible con OpenShift).
  - `frontend/Dockerfile` (build + nginx sin privilegios en el puerto 8080).
  - `docker-compose.yml` con backend, frontend y Redis; Ollama en el host vía `host.docker.internal`.
  - Workflow con build de las imágenes y escaneo con Trivy.
- **Criterios de aceptación:** las imágenes se construyen en CI sin vulnerabilidades críticas; prueba local opcional con Colima.

## PR 12 · `feat/claude-provider` — Proveedor Claude opcional y comparativa en evals
**ADR:** 004, 009
- **Incluye:**
  - `ClaudeProvider` con el SDK oficial y tool use / JSON estructurado, activo solo con `ANTHROPIC_API_KEY`.
  - `make eval MODEL=...` para comparar proveedores.
  - Si no hay clave, el PR se queda en código + tests con mock, y la comparativa se marca como pendiente.
- **Criterios de aceptación:** tests con mock; sin clave el proyecto funciona exactamente igual.

## PR 13 · `docs/readme` — README en inglés, diagrama, GIF y producción; docs en inglés
**ADR:** 014
- **Incluye:**
  - README en inglés: problema, demo en GIF, arquitectura (diagrama Mermaid), cómo ejecutarlo, resultados de las evals y *"Design decisions"* (resumen de los ADR).
  - Sección *"What I'd change for production"*: auth/SSO, PostgreSQL, colas o Kafka para ficheros grandes, importación idempotente, OpenTelemetry, PII y prompt injection, despliegue en OpenShift con GitOps.
  - Traducción de `docs/PLAN.md` al inglés (se mantiene la versión en español como `PLAN.es.md`).
- **Criterios de aceptación:** alguien que no conoce el proyecto puede ejecutarlo en 10 minutos siguiendo el README.

---
