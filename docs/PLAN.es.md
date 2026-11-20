# smart-csv-mapper · Plan de desarrollo y decisiones de arquitectura (ADR)

> Estado: **aceptado** · Fecha: 2026-11-20
> Documento vivo: cada decisión tiene su ADR. Si una decisión cambia, el ADR antiguo pasa a *Sustituido* y se añade uno nuevo; no se borra.

## 1. Contexto

Al integrar clientes nuevos, cada uno envía sus ficheros CSV con columnas distintas: nombres, orden, formatos de fecha y de número, y a veces columnas que hay que transformar, como un nombre completo que hay que separar en nombre y apellidos. Configurar cada integración a mano lleva días de trabajo de ingeniería.

**smart-csv-mapper** es una versión abierta y simplificada de un sistema que construí en producción. Un LLM **propone** cómo encajan las columnas del fichero en un esquema destino fijo, la persona **revisa y corrige**, y las transformaciones son **deterministas** siempre que se puede. La IA solo se usa en los casos que el código no resuelve, enviando **valores únicos** y **cacheando** los resultados.

Es un proyecto de práctica y de portfolio. Usa **solo datos inventados** y no contiene código de ninguna empresa.

### Entorno de desarrollo
- MacBook con Apple M2 y **8 GB de RAM**. Condiciona el tamaño del modelo local y la decisión sobre Docker.
- Ya instalados: Python 3.13, uv, Node 23, npm, git, gh.
- Por instalar: **Ollama** (`brew install ollama`), y Redis y Docker de forma opcional.

## 2. Objetivos

1. Subir un CSV y obtener en segundos una propuesta de mapeo al esquema destino, con un nivel de confianza por campo.
2. Revisar y editar el mapeo en una interfaz web, y ver una vista previa con los errores marcados antes de exportar.
3. Transformaciones deterministas para lo común; IA solo como último recurso, por valores únicos, en lotes y con caché.
4. Medir la calidad con **evals** reproducibles en lugar de "parece que funciona".
5. Coste cero: desarrollar, probar y ejecutar el CI sin pagar nada.
6. Código simple que se pueda explicar línea por línea.

## 3. No-objetivos (fuera de alcance, a propósito)

- Autenticación y multiusuario. Se explica en el README, en la sección de producción.
- Persistir los datos importados. Solo se guarda el log de auditoría.
- Ficheros enormes y procesamiento asíncrono con colas o Kafka.
- Esquemas destino configurables por el usuario. El esquema es fijo, aunque está definido en un solo sitio para que cambiarlo sea fácil.
- Despliegue en Kubernetes u OpenShift. Eso es el proyecto mini-onemesh.

## 4. Esquema destino

| Campo | Tipo | Obligatorio | Validación |
|---|---|---|---|
| `first_name` | string | sí | no vacío |
| `last_name` | string | sí | no vacío |
| `email` | string | no | formato email |
| `phone` | string | no | E.164 (`+34612345678`) |
| `amount_due` | decimal | sí | ≥ 0, dos decimales |
| `due_date` | date | no | ISO 8601 (`2026-11-20`) |
| `external_id` | string | sí | único dentro del fichero |

---

## 5. Decisiones (ADR)

### ADR-001 · Monorepo con backend y frontend
- **Estado:** Aceptado
- **Contexto:** Una sola persona, un solo producto y cambios que suelen tocar las dos partes a la vez (por ejemplo, un campo nuevo en la API).
- **Decisión:** Un repositorio con `backend/`, `frontend/`, `evals/` y `docs/`, y un `Makefile` en la raíz con los comandos comunes (`make dev`, `make test`, `make eval`).
- **Alternativas:** dos repositorios separados. Se descarta porque obliga a coordinar versiones y PRs sin aportar nada a esta escala.
- **Consecuencias:** El CI usa filtros por ruta para no ejecutar los tests del frontend si solo cambia el backend.

### ADR-002 · Backend en Python con FastAPI, Pydantic v2 y uv
- **Estado:** Aceptado
- **Contexto:** La oferta pide FastAPI. Pydantic sirve a la vez para validar la API y la salida del LLM.
- **Decisión:** Python 3.12+, FastAPI, Pydantic v2 y pydantic-settings para la configuración, gestionado con **uv**. Lectura de CSV con la librería estándar `csv` más `charset-normalizer` para detectar la codificación (**sin pandas**).
- **Alternativas:** pandas, que es más cómodo pero es una dependencia pesada que infiere tipos de forma silenciosa, justo lo contrario de lo que queremos; Node para todo el stack, descartado porque la oferta pide FastAPI.
- **Consecuencias:** Más control sobre los tipos (todo se lee como texto y se transforma de forma explícita). Calidad con ruff, mypy en modo estricto y pytest.

### ADR-003 · Frontend en React, TypeScript, Vite, TanStack Query y Zod
- **Estado:** Aceptado
- **Contexto:** La oferta pide React y TypeScript, y es una herramienta interna con formularios y tablas.
- **Decisión:**
  - Vite + React + TypeScript en modo estricto.
  - TanStack Query para el estado del servidor.
  - Tipos generados desde el OpenAPI del backend (`openapi-typescript`), más Zod para validar en tiempo de ejecución.
  - CSS sencillo con un componente de tabla propio, sin librerías de UI pesadas.
- **Alternativas:** Next.js, innecesario porque no hay SSR ni SEO; Redux, innecesario porque el estado del servidor lo gestiona TanStack Query.
- **Consecuencias:** Si cambia la API, los tipos del frontend se regeneran y `tsc` falla allí donde se rompa el contrato.

### ADR-004 · Proveedor de LLM intercambiable, con Ollama por defecto
- **Estado:** Aceptado
- **Contexto:** El objetivo es coste cero. La máquina tiene 8 GB de RAM. Queremos poder comparar modelos con las evals.
- **Decisión:**
  - Una interfaz `LLMProvider` con un solo método: `complete_json(prompt, schema) -> dict`.
  - Tres implementaciones:
    - `OllamaProvider` (por defecto): usa la API local `http://localhost:11434` con **structured outputs** (parámetro `format` con el JSON Schema de Pydantic) y `temperature=0`.
    - `ClaudeProvider` (opcional): solo si existe `ANTHROPIC_API_KEY`.
    - `FakeProvider`: para los tests, devuelve respuestas grabadas.
  - Se elige con la variable `LLM_PROVIDER`.
  - **Modelo por defecto:** `qwen2.5:3b` (~2 GB), con buen JSON para su tamaño y apto para 8 GB. Alternativa: `llama3.2:3b`. El modelo es configurable (`LLM_MODEL`).
- **Alternativas:** solo Claude (cuesta dinero y necesita clave); modelos de 7–8B (no caben bien con 8 GB de RAM junto al resto).
- **Consecuencias:** Un modelo de 3B se equivoca más. Lo compensamos con validación estricta, reintento, heurísticas de respaldo y revisión humana, y lo medimos con las evals. El sistema está diseñado para funcionar bien con un modelo débil.

### ADR-005 · Propuesta de mapeo: LLM + validación + respaldo heurístico
- **Estado:** Aceptado
- **Contexto:** El LLM puede devolver JSON inválido, columnas que no existen o transformaciones inventadas.
- **Decisión:**
  1. Se perfila cada columna: nombre, 5 valores de muestra, número de valores únicos y porcentaje de vacíos. **Nunca se envía el fichero completo.**
  2. El prompt incluye el esquema destino, el **catálogo cerrado de transformaciones** y el perfil de las columnas.
  3. La respuesta se valida con Pydantic (`MappingProposal`): la columna origen debe existir, la transformación debe estar en el catálogo y la confianza debe estar entre 0 y 1.
  4. Si falla la validación, **un reintento** que incluye el error. Si vuelve a fallar, se usa el **respaldo heurístico**: similitud de nombres (`difflib`) más diccionario de sinónimos (`correo → email`, `importe → amount_due`…).
  5. El prompt está versionado (`PROMPT_VERSION`) y la versión se guarda en el log y en la clave de caché.
- **Alternativas:** dejar que el LLM escriba código de transformación libre. Se descarta: no es determinista, es inseguro y no se puede revisar.
- **Consecuencias:** El usuario siempre recibe una propuesta, aunque el modelo falle. Cada campo indica su origen (`llm` o `heuristic`) y su confianza.

### ADR-006 · Transformaciones deterministas como catálogo de funciones con nombre
- **Estado:** Aceptado
- **Contexto:** En el sistema original se usaba JSONata. Aquí prima que el proyecto se entienda y se pruebe fácilmente.
- **Decisión:**
  - Un registro de funciones Python puras con nombre: `trim`, `lowercase_trim`, `parse_eu_number`, `parse_us_number`, `parse_date(format)`, `normalize_phone(default_country)`, `split_name_first/last` (con IA), `constant(value)` y `map_values(dict)`.
  - Cada una devuelve un valor o un error de validación, nunca lanza excepciones sin controlar.
  - Las reglas *if/else* sencillas se expresan con `map_values`.
- **Alternativas:** JSONata con `jsonata-python`. Es más potente y se parece más a la historia original, pero añade un lenguaje que hay que explicar. Queda anotado como mejora futura en el README.
- **Consecuencias:** Tests unitarios por función. El catálogo es la "lista blanca" que ve el LLM.

### ADR-007 · Transformaciones con IA: valores únicos, lotes y caché
- **Estado:** Aceptado
- **Contexto:** Llamar al modelo una vez por fila es lento, caro e inconsistente: el mismo valor puede transformarse distinto en dos filas.
- **Decisión:**
  1. Se extraen los **valores únicos** de la columna.
  2. Se buscan en la **caché**. La clave es `sha256(transform, prompt_version, model, valor_normalizado)`.
  3. Los que faltan van al modelo **en lotes de 20**, con salida estructurada `{valor: resultado}`.
  4. Los resultados se guardan en caché con un TTL de 30 días.
  5. Se aplican a todas las filas con un diccionario.
  - Caché detrás de una interfaz `Cache` con dos implementaciones: `RedisCache` (si existe `REDIS_URL`) e `InMemoryCache` (por defecto). Así el proyecto funciona sin instalar Redis.
  - La respuesta incluye estadísticas: filas, valores únicos, aciertos de caché, llamadas al modelo y tiempo.
- **Alternativas:** caché semántica por similitud. Se descarta porque añade complejidad y aquí basta la coincidencia exacta.
- **Consecuencias:** Consistencia garantizada dentro del fichero y entre ficheros. Las estadísticas son la cifra que se enseña en la demo.

### ADR-008 · Almacenamiento mínimo: ficheros en memoria y log de auditoría en SQLite
- **Estado:** Aceptado
- **Contexto:** Sin multiusuario ni persistencia de datos, una base de datos completa sería excesiva.
- **Decisión:**
  - El CSV subido se guarda en memoria con un id (TTL de 1 h) y unos límites: **10 MB y 50.000 filas**.
  - Log de auditoría en **SQLite**: quién (usuario fijo `demo`), qué fichero (hash, no contenido), mapeo final, versión del prompt, modelo, estadísticas y fecha. Solo se añaden registros, no hay endpoints de borrado.
- **Alternativas:** PostgreSQL. Se pospone a la sección de producción.
- **Consecuencias:** Si se reinicia el backend, se pierden las subidas en curso. Es aceptable en una demo.

### ADR-009 · Evals reproducibles y gratis, también en CI
- **Estado:** Aceptado
- **Contexto:** Hay que poder responder "¿cómo sabes que funciona?" con números.
- **Decisión:**
  - `evals/datasets/`: unos 15 CSV inventados con estilos distintos (español, inglés, separador `;`, decimales con coma, columnas extra, cabeceras crípticas), cada uno con su `expected_mapping.json`.
  - `evals/name_split.jsonl`: unos 60 nombres con su separación correcta (compuestos, dos apellidos, partículas como "de la").
  - Métricas: **precisión del mapeo por campo**, **precisión de las transformaciones con IA**, **% de respaldo heurístico**, y latencia media.
  - `make eval` lo ejecuta en local con Ollama y guarda el informe en `evals/results/<fecha>-<modelo>.md`.
  - **CI:** un job instala Ollama en el runner de GitHub (gratis en repos públicos), descarga el modelo y ejecuta las evals cuando cambian `prompts/`, `mapping/` o `evals/`, o a mano. Falla si la precisión del mapeo baja del umbral (inicialmente **85 %**, se ajusta tras la primera medición).
- **Alternativas:** evals solo en local. Más simple, pero el PR no queda protegido.
- **Riesgos:** si el job tarda demasiado en CPU (más de unos 15 min), pasa a ejecución manual o nocturna con un modelo de 1,5B.
- **Consecuencias:** Los tests unitarios **nunca** llaman a un modelo real (siempre `FakeProvider`). Solo las evals usan un modelo real.

### ADR-010 · Estrategia de tests
- **Estado:** Aceptado
- **Decisión:**
  - **Backend:** pytest. Tests unitarios por transformación, tests del mapeador con `FakeProvider` (incluidos JSON inválido, columna inexistente, reintento y respaldo heurístico) y tests de la API con `TestClient` y `dependency_overrides`. Cobertura del **100 %** (`--cov-fail-under=100`).
  - **Frontend:** Vitest + Testing Library para la tabla de mapeo y los estados de carga y error. La API se simula con MSW.
  - Frontend también al **100 %** de cobertura (umbrales de Vitest).
  - Sin e2e con navegador en esta versión (se menciona como mejora).
- **Consecuencias:** El CI es rápido, determinista y sin claves.

### ADR-011 · Seguridad y privacidad
- **Estado:** Aceptado
- **Decisión:**
  - Solo datos inventados en el repositorio. Las claves van en `.env`, que está en `.gitignore`; existe `.env.example` sin valores. Escaneo de secretos con **gitleaks** en pre-commit y en CI.
  - Límites de tamaño y de tipo de fichero en la subida.
  - **Protección contra CSV injection** al exportar: si una celda empieza por `=`, `+`, `-` o `@`, se le antepone `'`.
  - Al modelo solo le llegan muestras de 5 valores por columna y, en las transformaciones con IA, solo la columna afectada.
  - Con Ollama, los datos **no salen de la máquina**.
- **Consecuencias:** Se documentan en el README los riesgos de producción: PII, prompt injection en los valores de las celdas y retención de datos.

### ADR-012 · Ejecución: nativa por defecto y Docker opcional
- **Estado:** Aceptado
- **Contexto:** Con 8 GB de RAM, Docker Desktop y Ollama a la vez van justos. Además, Ollama en Docker sobre Mac no usa la GPU.
- **Decisión:**
  - Desarrollo **nativo**: `make dev` arranca el backend (uvicorn) y el frontend (Vite); Ollama corre en el Mac.
  - Se incluyen `Dockerfile`s (**usuario no root, puerto alto**, listos para OpenShift) y un `docker-compose.yml` con backend, frontend y Redis, que se conecta a Ollama del host vía `host.docker.internal`. Se pueden probar con Colima, más ligero que Docker Desktop, o directamente en el CI (build de las imágenes).
- **Consecuencias:** Las imágenes se construyen y escanean (Trivy) en CI aunque no se usen a diario en local. Se reutilizan en mini-onemesh.

### ADR-013 · Observabilidad mínima
- **Estado:** Aceptado
- **Decisión:**
  - Logs estructurados en JSON con `request_id`.
  - Cada llamada al modelo registra el proveedor, el modelo, la versión del prompt, la latencia, los tokens (si los hay) y si vino de caché.
  - Endpoints `/healthz` (proceso vivo) y `/readyz` (Ollama accesible y caché disponible).
- **Alternativas:** OpenTelemetry completo. Se pospone a mini-onemesh.

### ADR-014 · Calidad de código y flujo de trabajo
- **Estado:** Aceptado
- **Decisión:**
  - Rama `main` protegida; cada cambio entra por PR con CI en verde y squash merge.
  - Conventional Commits (`feat:`, `fix:`, `chore:`…).
  - pre-commit con ruff, ruff-format, mypy, eslint, prettier y gitleaks.
  - **Sin operadores ternarios** (ni `a if c else b` en Python ni `c ? a : b` en TypeScript): se prefieren `if` explícitos por legibilidad. ESLint `no-ternary` en el frontend.
- **Consecuencias:** El historial del repositorio cuenta la historia del proyecto PR a PR.

---

## 6. Arquitectura

```
┌──────────────────────┐   REST/JSON   ┌───────────────────────────────────────┐
│ frontend (React/TS)  │ ────────────▶ │ backend (FastAPI)                     │
│ 1. Subir CSV         │               │ POST /files            → perfil       │
│ 2. Revisar mapeo     │ ◀──────────── │ POST /files/{id}/suggest → propuesta  │
│ 3. Vista previa      │               │ POST /files/{id}/preview → filas+errores
│ 4. Exportar          │               │ POST /files/{id}/export  → CSV + audit│
└──────────────────────┘               │                                       │
                                       │ ingest/  mapping/  transforms/        │
                                       │ ai_transforms/  llm/  cache/  audit/  │
                                       └──────┬───────────────┬────────────────┘
                                              │               │
                                   ┌──────────▼───┐   ┌───────▼────────────┐
                                   │ Cache        │   │ LLMProvider        │
                                   │ memoria|Redis│   │ Ollama|Claude|Fake │
                                   └──────────────┘   └────────────────────┘
                                                      SQLite (audit log)
```

## 7. Riesgos

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| El modelo de 3B mapea mal | Media | Validación, reintento, respaldo heurístico, revisión humana y evals para medirlo |
| Ollama va lento o se queda sin memoria con 8 GB | Media | Modelo de 3B (o 1,5B), cerrar apps, lotes pequeños |
| El job de evals en CI es demasiado lento | Media | Ejecución manual o nocturna, modelo más pequeño |
| Falta de tiempo | Alta | Orden de PRs pensado para tener una demo útil tras el PR 7; el resto se puede dejar como mejora |
| Código difícil de explicar | Media | PRs pequeños, revisión de tests en cada PR y notas privadas |

## 8. Definición de terminado

- `make dev` funciona en un Mac limpio siguiendo el README.
- CI en verde: lint, tipos, tests, cobertura del 100 %, gitleaks y build de imágenes.
- Informe de evals con Ollama publicado en `evals/results/`.
- README en inglés con diagrama, GIF de la demo, resultados de las evals y la sección *"What I'd change for production"*.
- Cada módulo y cada decisión de este documento se pueden explicar sin mirar el código.
