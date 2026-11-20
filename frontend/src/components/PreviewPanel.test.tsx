import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { preview, proposal } from "../test/fixtures";
import { renderWithQuery } from "../test/render";
import { server } from "../test/server";
import { PreviewPanel } from "./PreviewPanel";

function setup() {
  renderWithQuery(
    <PreviewPanel fileId="f1" fields={proposal.fields} targets={["external_id", "email"]} />,
  );
  return screen.getByRole("button", { name: "Preview the first 20 rows" });
}

describe("PreviewPanel", () => {
  it("shows rows, highlights the failing cell with its reason and the AI stats", async () => {
    server.use(http.post("/api/files/f1/preview", () => HttpResponse.json(preview)));
    await userEvent.click(setup());
    expect(await screen.findByText("Errors in the first 2 rows: email (1)")).toBeInTheDocument();
    const cell = screen.getByText("⚠ invalid email: 'nope'");
    expect(cell).toHaveClass("cell-error");
    expect(cell).toHaveAttribute("title", "invalid email: 'nope'");
    const firstRow = screen.getByRole("row", { name: /CL-1/ });
    expect(within(firstRow).getByText("ana@example.com")).toBeInTheDocument();
    expect(
      screen.getByText(
        "AI split_name on “Nombre”: 2 rows · 2 distinct · 0 from cache · 1 model calls · 0 failed · 1.5 s",
      ),
    ).toBeInTheDocument();
  });

  it("says so when there are no errors", async () => {
    server.use(
      http.post("/api/files/f1/preview", () =>
        HttpResponse.json({ ...preview, errors: [], error_count_by_field: {}, ai_stats: [] }),
      ),
    );
    await userEvent.click(setup());
    expect(await screen.findByText("No errors in the first 2 rows.")).toBeInTheDocument();
  });

  it("shows progress and then the error", async () => {
    server.use(
      http.post("/api/files/f1/preview", async () => {
        await delay(30);
        return HttpResponse.json({ code: "x", detail: "Model down" }, { status: 503 });
      }),
    );
    const button = setup();
    await userEvent.click(button);
    expect(screen.getByRole("status")).toHaveTextContent("Transforming…");
    expect(button).toBeDisabled();
    expect(await screen.findByRole("alert")).toHaveTextContent("Model down");
  });
});
