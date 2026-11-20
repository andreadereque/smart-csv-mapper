import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { auditEntry } from "../test/fixtures";
import { renderWithQuery } from "../test/render";
import { server } from "../test/server";
import { AuditHistory } from "./AuditHistory";

describe("AuditHistory", () => {
  it("lists recent exports", async () => {
    server.use(http.get("/api/audit", () => HttpResponse.json([auditEntry])));
    renderWithQuery(<AuditHistory />);
    const row = await screen.findByRole("row", { name: /clientes.csv/ });
    expect(row).toHaveTextContent("2026-11-20 10:00:00");
    expect(row).toHaveTextContent("qwen2.5:3b");
  });

  it("says when nothing was exported", async () => {
    server.use(http.get("/api/audit", () => HttpResponse.json([])));
    renderWithQuery(<AuditHistory />);
    expect(await screen.findByText("Nothing exported yet.")).toBeInTheDocument();
  });

  it("shows a load error", async () => {
    server.use(
      http.get("/api/audit", () => HttpResponse.json({ detail: "nope" }, { status: 500 })),
    );
    renderWithQuery(<AuditHistory />);
    expect(await screen.findByText("nope")).toBeInTheDocument();
  });
});
