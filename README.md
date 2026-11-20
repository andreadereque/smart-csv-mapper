# smart-csv-mapper

Upload a CSV with messy, client-specific columns and get clean rows in a fixed target schema.
An LLM **proposes** the column mapping, a person **reviews** it, and transformations are
**deterministic** wherever possible. AI is only a fallback, called on **distinct values** and **cached**.

> Work in progress. See [docs/PLAN.md](docs/PLAN.md) for the design decisions (ADRs)
> and [docs/PRS.md](docs/PRS.md) for the delivery plan.

- Runs **free and local** with [Ollama](https://ollama.com) (`qwen2.5:3b`); data never leaves the machine.
- Fake data only.

## Design decisions

_Filled in as each PR lands._

## License

MIT
