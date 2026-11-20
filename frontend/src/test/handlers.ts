import { http, HttpResponse } from "msw";
import { auditEntry, preview, proposal, targets, transforms } from "./fixtures";

export const happyPath = [
  http.post("/api/files/:id/suggest", () => HttpResponse.json(proposal)),
  http.get("/api/schema", () => HttpResponse.json(targets)),
  http.get("/api/transforms", () => HttpResponse.json(transforms)),
  http.post("/api/files/:id/preview", () => HttpResponse.json(preview)),
  http.get("/api/audit", () => HttpResponse.json([auditEntry])),
];
