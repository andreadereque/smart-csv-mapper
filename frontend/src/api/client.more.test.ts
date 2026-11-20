import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { auditEntry, preview, proposal, targets, transforms } from "../test/fixtures";
import { server } from "../test/server";
import {
  exportCsv,
  getAudit,
  getTargetSchema,
  getTransforms,
  previewRows,
  suggestMapping,
} from "./client";

describe("endpoints", () => {
  it("reads the catalog, suggests, previews and reads the audit log", async () => {
    let previewBody: unknown = null;
    server.use(
      http.get("/api/schema", () => HttpResponse.json(targets)),
      http.get("/api/transforms", () => HttpResponse.json(transforms)),
      http.post("/api/files/f1/suggest", () => HttpResponse.json(proposal)),
      http.post("/api/files/f1/preview", async ({ request }) => {
        previewBody = await request.json();
        return HttpResponse.json(preview);
      }),
      http.get("/api/audit", () => HttpResponse.json([auditEntry])),
    );
    await expect(getTargetSchema()).resolves.toEqual(targets);
    await expect(getTransforms()).resolves.toEqual(transforms);
    await expect(suggestMapping("f1")).resolves.toEqual(proposal);
    await expect(previewRows("f1", proposal.fields, 5)).resolves.toEqual(preview);
    expect(previewBody).toEqual({ fields: proposal.fields, rows: 5 });
    await expect(getAudit()).resolves.toEqual([auditEntry]);
  });
});

describe("exportCsv", () => {
  it("returns the CSV, the server's file name and the row counts", async () => {
    let body: unknown = null;
    server.use(
      http.post("/api/files/f1/export", async ({ request }) => {
        body = await request.json();
        return new HttpResponse("a,b\n", {
          headers: {
            "content-type": "text/csv",
            "content-disposition": 'attachment; filename="clientes_clean.csv"',
            "x-rows-exported": "2",
            "x-rows-skipped": "1",
          },
        });
      }),
    );
    const result = await exportCsv("f1", proposal.fields, true);
    expect(body).toEqual({ fields: proposal.fields, skip_invalid: true });
    expect(result).toMatchObject({ filename: "clientes_clean.csv", exported: 2, skipped: 1 });
    // jsdom's Blob lacks .text() on Node 24, so check the size of "a,b\n" instead.
    expect(result.csv.size).toBe(4);
  });

  it("falls back to a default file name", async () => {
    server.use(http.post("/api/files/f1/export", () => new HttpResponse("x")));
    await expect(exportCsv("f1", [], false)).resolves.toMatchObject({ filename: "clean.csv" });
  });

  it("explains invalid rows with the failing cells", async () => {
    const errors = [{ row: 2, field: "email", value: "x", reason: "invalid email" }];
    server.use(
      http.post("/api/files/f1/export", () =>
        HttpResponse.json(
          { detail: { code: "invalid_rows", invalid_row_count: 1, errors } },
          { status: 422 },
        ),
      ),
    );
    await expect(exportCsv("f1", [], false)).rejects.toMatchObject({
      code: "invalid_rows",
      message: "1 row has errors.",
      invalidRowCount: 1,
      cellErrors: errors,
    });
  });

  it("uses the plural for several invalid rows", async () => {
    server.use(
      http.post("/api/files/f1/export", () =>
        HttpResponse.json(
          { detail: { code: "invalid_rows", invalid_row_count: 2 } },
          { status: 422 },
        ),
      ),
    );
    await expect(exportCsv("f1", [], false)).rejects.toMatchObject({
      message: "2 rows have errors.",
    });
  });

  it("lists the problems of an invalid mapping", async () => {
    server.use(
      http.post("/api/files/f1/export", () =>
        HttpResponse.json(
          { detail: { code: "invalid_mapping", problems: ["a: bad", "b: worse"] } },
          { status: 422 },
        ),
      ),
    );
    await expect(exportCsv("f1", [], false)).rejects.toMatchObject({
      code: "invalid_mapping",
      message: "a: bad; b: worse",
      invalidRowCount: 0,
      cellErrors: [],
    });
  });

  it("falls back to the code when a structured detail has no message", async () => {
    server.use(
      http.post("/api/files/f1/export", () =>
        HttpResponse.json({ detail: { code: "something_new" } }, { status: 409 }),
      ),
    );
    await expect(exportCsv("f1", [], false)).rejects.toMatchObject({
      code: "something_new",
      message: "something_new",
    });
  });
});
