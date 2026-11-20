import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { App } from "./App";
import { profile } from "./test/fixtures";
import { happyPath } from "./test/handlers";
import { renderWithQuery } from "./test/render";
import { server } from "./test/server";

describe("App", () => {
  it("goes from upload to the column profile and back", async () => {
    server.use(
      http.post("/api/files", () => HttpResponse.json(profile, { status: 201 })),
      ...happyPath,
    );
    renderWithQuery(<App />);
    await userEvent.upload(
      screen.getByLabelText("CSV file"),
      new File(["x"], "clientes.csv", { type: "text/csv" }),
    );
    expect(await screen.findByRole("heading", { name: "clientes.csv" })).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "2. Review the mapping" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Recent exports" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Upload another file" }));
    expect(screen.getByRole("heading", { name: "1. Upload a CSV" })).toBeInTheDocument();
  });
});
