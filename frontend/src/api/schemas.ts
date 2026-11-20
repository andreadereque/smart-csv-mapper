// Runtime validation of API responses. Types disappear at runtime, so data coming from the
// network is checked with Zod; each schema is tied to the generated OpenAPI type, so `tsc`
// fails if the backend contract changes and these drift.
import { z } from "zod";
import type { components } from "./schema";

type Schemas = components["schemas"];

export const columnProfileSchema = z.object({
  name: z.string(),
  samples: z.array(z.string()),
  distinct_count: z.number().int(),
  empty_ratio: z.number(),
}) satisfies z.ZodType<Schemas["ColumnProfile"]>;

export const fileProfileSchema = z.object({
  file_id: z.string(),
  filename: z.string(),
  encoding: z.string(),
  delimiter: z.string(),
  row_count: z.number().int(),
  columns: z.array(columnProfileSchema),
}) satisfies z.ZodType<Schemas["FileProfile"]>;

export const apiErrorSchema = z.object({
  code: z.string().optional(),
  detail: z.unknown(),
});

export type ColumnProfile = z.infer<typeof columnProfileSchema>;
export type FileProfile = z.infer<typeof fileProfileSchema>;

export const originSchema = z.enum(["llm", "heuristic", "user", "none"]);

export const fieldMappingSchema = z.object({
  target: z.string(),
  source: z.string().nullable(),
  transform: z.string(),
  params: z.record(z.string(), z.string()),
  confidence: z.number(),
  origin: originSchema,
});

export const mappingProposalSchema = z.object({
  file_id: z.string(),
  fields: z.array(fieldMappingSchema),
  warnings: z.array(z.string()),
  prompt_version: z.string(),
  model: z.string(),
  attempts: z.number().int(),
});

export const targetFieldSchema = z.object({
  name: z.string(),
  type: z.string(),
  required: z.boolean(),
  description: z.string(),
}) satisfies z.ZodType<Schemas["FieldOut"]>;

export const transformInfoSchema = z.object({
  name: z.string(),
  description: z.string(),
  required_params: z.array(z.string()),
  optional_params: z.array(z.string()),
  free_params: z.boolean(),
  llm_allowed: z.boolean(),
  kind: z.string(),
}) satisfies z.ZodType<Schemas["TransformOut"]>;

export const cellErrorSchema = z.object({
  row: z.number().int(),
  field: z.string(),
  value: z.string(),
  reason: z.string(),
}) satisfies z.ZodType<Schemas["CellError"]>;

export const aiStatsSchema = z.object({
  transform: z.string(),
  source: z.string(),
  rows: z.number().int(),
  distinct: z.number().int(),
  cache_hits: z.number().int(),
  llm_calls: z.number().int(),
  failed: z.number().int(),
  ms: z.number().int(),
}) satisfies z.ZodType<Schemas["AIStats"]>;

export const previewSchema = z.object({
  rows: z.array(z.record(z.string(), z.string())),
  errors: z.array(cellErrorSchema),
  error_count_by_field: z.record(z.string(), z.number().int()),
  rows_checked: z.number().int(),
  ai_stats: z.array(aiStatsSchema),
}) satisfies z.ZodType<Schemas["PreviewResponse"]>;

export const auditEntrySchema = z.object({
  id: z.number().int().nullable(),
  at: z.string(),
  user: z.string(),
  filename: z.string(),
  file_sha256: z.string(),
  rows_total: z.number().int(),
  rows_exported: z.number().int(),
  rows_skipped: z.number().int(),
  model: z.string(),
});

// Type-level checks against the generated OpenAPI types (inputs and outputs differ slightly
// because of defaults, so these compare the parsed shapes).
type Assert<T extends true> = T;
type Same<A, B> = [A] extends [B] ? ([B] extends [A] ? true : false) : false;
export type _MappingMatches = Assert<
  Same<z.infer<typeof fieldMappingSchema>, Required<Schemas["FieldMapping"]>>
>;

export type FieldMapping = z.infer<typeof fieldMappingSchema>;
export type MappingProposal = z.infer<typeof mappingProposalSchema>;
export type TargetField = z.infer<typeof targetFieldSchema>;
export type TransformInfo = z.infer<typeof transformInfoSchema>;
export type CellError = z.infer<typeof cellErrorSchema>;
export type AIStats = z.infer<typeof aiStatsSchema>;
export type Preview = z.infer<typeof previewSchema>;
export type AuditEntry = z.infer<typeof auditEntrySchema>;
