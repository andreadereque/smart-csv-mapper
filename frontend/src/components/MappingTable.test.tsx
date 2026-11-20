import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { proposal, targets, transforms } from "../test/fixtures";
import { MappingTable } from "./MappingTable";

function setup() {
  const onChange = vi.fn();
  render(
    <MappingTable
      fields={proposal.fields}
      columns={["Referencia", "Correo"]}
      targets={targets}
      transforms={transforms}
      onChange={onChange}
    />,
  );
  return onChange;
}

describe("MappingTable", () => {
  it("shows each target with its column, transform, origin and confidence", () => {
    setup();
    const idRow = screen.getByRole("row", { name: /external_id/ });
    expect(within(idRow).getByText("*")).toBeInTheDocument();
    expect(within(idRow).getByLabelText("external_id column")).toHaveValue("Referencia");
    expect(within(idRow).getByText("AI")).toBeInTheDocument();
    expect(within(idRow).getByText("90%")).toBeInTheDocument();
    const emailRow = screen.getByRole("row", { name: /email/ });
    expect(emailRow).toHaveClass("tone-review");
    expect(within(emailRow).queryByText("*")).not.toBeInTheDocument();
    expect(within(emailRow).getByText("60% · review")).toBeInTheDocument();
    expect(screen.getAllByRole("option", { name: "split_name_first (AI)" })).toHaveLength(2);
  });

  it("marks a changed column as set by the user", async () => {
    const onChange = setup();
    await userEvent.selectOptions(screen.getByLabelText("email column"), "Referencia");
    expect(onChange).toHaveBeenCalledWith({
      ...proposal.fields[1],
      source: "Referencia",
      origin: "user",
      confidence: 1,
    });
  });

  it("can leave a field without a column", async () => {
    const onChange = setup();
    await userEvent.selectOptions(screen.getByLabelText("email column"), "— no column —");
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ source: null }));
  });

  it("resets params when the transform changes, then edits them", async () => {
    const onChange = setup();
    await userEvent.selectOptions(screen.getByLabelText("email transform"), "parse_date");
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ transform: "parse_date", params: {}, origin: "user" }),
    );
  });

  it("passes param edits up as user changes", async () => {
    const onChange = vi.fn();
    render(
      <MappingTable
        fields={[{ ...proposal.fields[1], transform: "parse_date" }]}
        columns={["Correo"]}
        targets={targets}
        transforms={transforms}
        onChange={onChange}
      />,
    );
    await userEvent.type(screen.getByLabelText("email format"), "%");
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ params: { format: "%" }, origin: "user" }),
    );
  });
});

it("drops the old params when the transform changes", async () => {
  const onChange = vi.fn();
  render(
    <MappingTable
      fields={[{ ...proposal.fields[1], transform: "parse_date", params: { format: "%d" } }]}
      columns={["Correo"]}
      targets={targets}
      transforms={transforms}
      onChange={onChange}
    />,
  );
  await userEvent.selectOptions(screen.getByLabelText("email transform"), "trim");
  expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ transform: "trim", params: {} }));
});
