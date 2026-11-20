import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { preview, profile, proposal } from "../test/fixtures";
import { happyPath } from "../test/handlers";
import { renderWithQuery } from "../test/render";
import { server } from "../test/server";
import { replaceField, Workspace } from "./Workspace";

describe("Workspace", () => {
  it("waits for the model, then shows the editable proposal with its warnings", async () => {
    server.use(
      http.post("/api/files/:id/suggest", async () => {
        await delay(30);
        return HttpResponse.json(proposal);
      }),
      ...happyPath,
    );
    renderWithQuery(<Workspace profile={profile} />);
    expect(screen.getByRole("status")).toHaveTextContent("The model is reading your columns");
    expect(
      await screen.findByText(/Proposed by qwen2.5:3b \(prompt mapping_v1, 1/),
    ).toBeInTheDocument();
    expect(screen.getByText(proposal.warnings[0])).toHaveClass("warning");
  });

  it("previews with the mapping as edited by the user", async () => {
    let sent: { fields: { target: string; source: string | null; origin: string }[] } | null = null;
    server.use(
      http.post("/api/files/:id/preview", async ({ request }) => {
        sent = (await request.json()) as typeof sent;
        return HttpResponse.json(preview);
      }),
      ...happyPath,
    );
    renderWithQuery(<Workspace profile={profile} />);
    await userEvent.selectOptions(await screen.findByLabelText("email column"), "— no column —");
    await userEvent.click(screen.getByRole("button", { name: "Preview the first 20 rows" }));
    await screen.findByText(/Errors in the first/);
    expect(sent!.fields[1]).toMatchObject({ target: "email", source: null, origin: "user" });
    expect(sent!.fields[0]).toMatchObject({ target: "external_id", origin: "llm" });
  });

  it("shows when the suggestion fails", async () => {
    server.use(
      http.post("/api/files/:id/suggest", () =>
        HttpResponse.json({ detail: "File not found or expired." }, { status: 404 }),
      ),
    );
    renderWithQuery(<Workspace profile={profile} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("File not found or expired.");
  });

  it("waits for the schema before showing the table", async () => {
    server.use(
      http.get("/api/schema", async () => {
        await delay(50);
        return HttpResponse.json([]);
      }),
      ...happyPath,
    );
    renderWithQuery(<Workspace profile={profile} />);
    expect(await screen.findByText("Loading the schema…")).toBeInTheDocument();
  });
});

describe("replaceField", () => {
  it("replaces only the field with the same target", () => {
    const changed = { ...proposal.fields[1], source: null };
    expect(replaceField(proposal.fields, changed)).toEqual([proposal.fields[0], changed]);
  });
});
