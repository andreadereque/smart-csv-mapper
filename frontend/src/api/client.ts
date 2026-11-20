import type { z } from "zod";
import { apiErrorSchema, fileProfileSchema, type FileProfile } from "./schemas";

export const API_BASE = "/api";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | undefined;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

function describe(detail: unknown, status: number): string {
  if (typeof detail === "string") {
    return detail;
  }
  return `Request failed (${status})`;
}

async function toApiError(response: Response): Promise<ApiError> {
  const parsed = apiErrorSchema.safeParse(await response.json().catch(() => ({})));
  if (!parsed.success) {
    return new ApiError(response.status, describe(undefined, response.status));
  }
  return new ApiError(
    response.status,
    describe(parsed.data.detail, response.status),
    parsed.data.code,
  );
}

export async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError(0, "Cannot reach the server. Is the backend running?");
  }
  if (!response.ok) {
    throw await toApiError(response);
  }
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
