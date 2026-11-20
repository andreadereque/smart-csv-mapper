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
