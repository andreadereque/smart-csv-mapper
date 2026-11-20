import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { auditEntry, proposal } from "../test/fixtures";
import { renderWithQuery } from "../test/render";
import { server } from "../test/server";
import { AuditHistory } from "./AuditHistory";
import { download, ExportPanel } from "./ExportPanel";

const csvResponse = () =>
  new HttpResponse("external_id\nCL-1\n", {
    headers: {
      "content-disposition": 'attachment; filename="clientes_clean.csv"',
      "x-rows-exported": "1",
      "x-rows-skipped": "1",
    },
  });

let clicks: string[] = [];

beforeEach(() => {
  clicks = [];
  URL.createObjectURL = vi.fn(() => "blob:fake");
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    clicks.push(this.download);
  });
});

afterEach(() => vi.restoreAllMocks());

describe("download", () => {
  it("clicks a temporary link to the blob and frees it", () => {
    download({ csv: new Blob(["x"]), filename: "a.csv", exported: 1, skipped: 0 });
    expect(clicks).toEqual(["a.csv"]);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:fake");
  });
});

describe("ExportPanel", () => {
  it("offers to skip invalid rows, then downloads and reports the counts", async () => {
    const skipFlags: boolean[] = [];
    server.use(
      http.post("/api/files/f1/export", async ({ request }) => {
        const body = (await request.json()) as { skip_invalid: boolean };
        skipFlags.push(body.skip_invalid);
        if (!body.skip_invalid) {
          return HttpResponse.json(
            {
              detail: {
                code: "invalid_rows",
                invalid_row_count: 1,
                errors: [{ row: 2, field: "email", value: "x", reason: "invalid email" }],
              },
            },
            { status: 422 },
          );
        }
        return csvResponse();
      }),
      http.get("/api/audit", () => HttpResponse.json([])),
    );
    renderWithQuery(<ExportPanel fileId="f1" fields={proposal.fields} />);
    await userEvent.click(screen.getByRole("button", { name: "Export clean CSV" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("1 row has errors.");
    expect(alert).toHaveTextContent("Row 2, email: invalid email");
    await userEvent.click(
      screen.getByRole("button", { name: "Skip 1 row with errors and export" }),
    );
    expect(
      await screen.findByText("1 row exported to clientes_clean.csv, 1 skipped."),
    ).toBeInTheDocument();
    expect(skipFlags).toEqual([false, true]);
    expect(clicks).toEqual(["clientes_clean.csv"]);
  });

  it("shows other errors as plain messages and progress while exporting", async () => {
    server.use(
      http.post("/api/files/f1/export", async () => {
        await delay(30);
        return HttpResponse.json({ detail: "File not found or expired." }, { status: 404 });
      }),
    );
    renderWithQuery(<ExportPanel fileId="f1" fields={proposal.fields} />);
    await userEvent.click(screen.getByRole("button", { name: "Export clean CSV" }));
    expect(screen.getByRole("status")).toHaveTextContent("Transforming the whole file…");
    expect(await screen.findByRole("alert")).toHaveTextContent("File not found or expired.");
    expect(
      screen.queryByRole("button", { name: /with errors and export/ }),
    ).not.toBeInTheDocument();
  });
});

it("refreshes the export history after a successful export", async () => {
  let exported = false;
  server.use(
    http.post("/api/files/f1/export", () => {
      exported = true;
      return csvResponse();
    }),
    http.get("/api/audit", () => {
      if (exported) {
        return HttpResponse.json([auditEntry]);
      }
      return HttpResponse.json([]);
    }),
  );
  renderWithQuery(
    <>
      <ExportPanel fileId="f1" fields={proposal.fields} />
      <AuditHistory />
    </>,
  );
  expect(await screen.findByText("Nothing exported yet.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Export clean CSV" }));
  expect(await screen.findByRole("row", { name: /clientes.csv/ })).toBeInTheDocument();
});
