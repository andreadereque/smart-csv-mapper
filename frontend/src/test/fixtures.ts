import type {
  AuditEntry,
  FileProfile,
  MappingProposal,
  Preview,
  TargetField,
  TransformInfo,
} from "../api/schemas";

export const profile: FileProfile = {
  file_id: "f1",
  filename: "clientes.csv",
  encoding: "utf-8",
  delimiter: ";",
  row_count: 300,
  columns: [
    { name: "Referencia", samples: ["CL-0001", "CL-0002"], distinct_count: 300, empty_ratio: 0 },
    { name: "Correo", samples: ["ana@example.com"], distinct_count: 299, empty_ratio: 0.25 },
  ],
};

export const targets: TargetField[] = [
  { name: "external_id", type: "string", required: true, description: "id" },
  { name: "email", type: "email", required: false, description: "email" },
];

export const transforms: TransformInfo[] = [
  {
    name: "trim",
    description: "Trim",
    required_params: [],
    optional_params: [],
    free_params: false,
    llm_allowed: true,
    kind: "deterministic",
  },
  {
    name: "parse_date",
    description: "Date",
    required_params: ["format"],
    optional_params: [],
    free_params: false,
    llm_allowed: true,
    kind: "deterministic",
  },
  {
    name: "map_values",
    description: "Lookup",
    required_params: [],
    optional_params: [],
    free_params: true,
    llm_allowed: false,
    kind: "deterministic",
  },
  {
    name: "split_name_first",
    description: "AI split",
    required_params: [],
    optional_params: [],
    free_params: false,
    llm_allowed: true,
    kind: "ai",
  },
];

export const proposal: MappingProposal = {
  file_id: "f1",
  fields: [
    {
      target: "external_id",
      source: "Referencia",
      transform: "trim",
      params: {},
      confidence: 0.9,
      origin: "llm",
    },
    {
      target: "email",
      source: "Correo",
      transform: "trim",
      params: {},
      confidence: 0.6,
      origin: "heuristic",
    },
  ],
  warnings: ["The model is not available (timeout); used heuristics."],
  prompt_version: "mapping_v1",
  model: "qwen2.5:3b",
  attempts: 1,
};

export const preview: Preview = {
  rows: [
    { external_id: "CL-1", email: "ana@example.com" },
    { external_id: "CL-2", email: "" },
  ],
  errors: [{ row: 2, field: "email", value: "nope", reason: "invalid email: 'nope'" }],
  error_count_by_field: { email: 1 },
  rows_checked: 2,
  ai_stats: [
    {
      transform: "split_name",
      source: "Nombre",
      rows: 2,
      distinct: 2,
      cache_hits: 0,
      llm_calls: 1,
      failed: 0,
      ms: 1500,
    },
  ],
};

export const auditEntry: AuditEntry = {
  id: 1,
  at: "2026-11-20T10:00:00+00:00",
  user: "demo",
  filename: "clientes.csv",
  file_sha256: "ab".repeat(32),
  rows_total: 3,
  rows_exported: 2,
  rows_skipped: 1,
  model: "qwen2.5:3b",
};
