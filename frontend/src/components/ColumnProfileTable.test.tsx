import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { profile } from "../test/fixtures";
import { ColumnProfileTable } from "./ColumnProfileTable";

describe("ColumnProfileTable", () => {
  it("shows the file summary and one row per column", () => {
    render(<ColumnProfileTable profile={profile} />);
    expect(screen.getByRole("heading", { name: "clientes.csv" })).toBeInTheDocument();
    expect(screen.getByText(/300 rows · 2 columns · utf-8/)).toHaveTextContent('delimiter ";"');
    const row = screen.getByRole("row", { name: /Correo/ });
    expect(within(row).getByText("ana@example.com")).toBeInTheDocument();
    expect(within(row).getByText("25%")).toBeInTheDocument();
  });

  it("names the tab delimiter instead of printing an invisible character", () => {
    render(<ColumnProfileTable profile={{ ...profile, delimiter: "\t" }} />);
    expect(screen.getByText(/delimiter tab/)).toBeInTheDocument();
  });
});
