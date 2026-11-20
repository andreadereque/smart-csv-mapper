import { z } from "zod";
import { rows } from "./plural";
import {
  apiErrorSchema,
  auditEntrySchema,
  fileProfileSchema,
  mappingProposalSchema,
  previewSchema,
  targetFieldSchema,
  transformInfoSchema,
  type CellError,
  type FieldMapping,
  type FileProfile,
} from "./schemas";

export const API_BASE = "/api";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | undefined;
  readonly cellErrors: CellError[];
  readonly invalidRowCount: number;

  constructor(
    status: number,
    message: string,
    code?: string,
    extra: { cellErrors?: CellError[]; invalidRowCount?: number } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.cellErrors = extra.cellErrors ?? [];
    this.invalidRowCount = extra.invalidRowCount ?? 0;
  }
}

// Structured details sent by the export/preview endpoints inside "detail".
const structuredDetailSchema = z.object({
  code: z.string(),
  problems: z.array(z.string()).optional(),
  invalid_row_count: z.number().int().optional(),
  errors: z
    .array(z.object({ row: z.number(), field: z.string(), value: z.string(), reason: z.string() }))
    .optional(),
});

function fromDetail(status: number, detail: unknown, code: string | undefined): ApiError {
  if (typeof detail === "string") {
    return new ApiError(status, detail, code);
  }
  const structured = structuredDetailSchema.safeParse(detail);
  if (!structured.success) {
    return new ApiError(status, `Request failed (${status})`, code);
  }
  const data = structured.data;
  let message = data.code;
  if (data.problems) {
    message = data.problems.join("; ");
  }
  if (data.invalid_row_count !== undefined) {
    let verb = "have";
    if (data.invalid_row_count === 1) {
      verb = "has";
    }
    message = `${rows(data.invalid_row_count)} ${verb} errors.`;
  }
  return new ApiError(status, message, data.code, {
    cellErrors: data.errors,
    invalidRowCount: data.invalid_row_count,
  });
}

async function toApiError(response: Response): Promise<ApiError> {
  const parsed = apiErrorSchema.safeParse(await response.json().catch(() => ({})));
  if (!parsed.success) {
    return new ApiError(response.status, `Request failed (${response.status})`);
  }
  return fromDetail(response.status, parsed.data.detail, parsed.data.code);
}

async function send(path: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError(0, "Cannot reach the server. Is the backend running?");
  }
  if (!response.ok) {
    throw await toApiError(response);
  }
  return response;
}

export async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  const response = await send(path, init);
  const parsed = schema.safeParse(await response.json());
  if (!parsed.success) {
    throw new ApiError(response.status, "The server sent an unexpected response.");
  }
  return parsed.data;
}

export function uploadFile(file: File): Promise<FileProfile> {
  const body = new FormData();
  body.append("file", file);
  return request("/files", fileProfileSchema, { method: "POST", body });
}

function postJson(body: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  };
}

export function getTargetSchema() {
  return request("/schema", z.array(targetFieldSchema));
}

export function getTransforms() {
  return request("/transforms", z.array(transformInfoSchema));
}

export function suggestMapping(fileId: string) {
  return request(`/files/${fileId}/suggest`, mappingProposalSchema, { method: "POST" });
}

export function previewRows(fileId: string, fields: FieldMapping[], rows = 20) {
  return request(`/files/${fileId}/preview`, previewSchema, postJson({ fields, rows }));
}

export type ExportResult = { csv: Blob; filename: string; exported: number; skipped: number };

export async function exportCsv(
  fileId: string,
  fields: FieldMapping[],
  skipInvalid: boolean,
): Promise<ExportResult> {
  const response = await send(
    `/files/${fileId}/export`,
    postJson({ fields, skip_invalid: skipInvalid }),
  );
  const disposition = response.headers.get("content-disposition") ?? "";
  const match = /filename="([^"]+)"/.exec(disposition);
  let filename = "clean.csv";
  if (match) {
    filename = match[1];
  }
  return {
    csv: await response.blob(),
    filename,
    exported: Number(response.headers.get("x-rows-exported")),
    skipped: Number(response.headers.get("x-rows-skipped")),
  };
}

export function getAudit() {
  return request("/audit", z.array(auditEntrySchema));
}
