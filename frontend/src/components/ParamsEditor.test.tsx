import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { transforms } from "../test/fixtures";
import { linesToParams, paramsToLines, ParamsEditor } from "./ParamsEditor";

const [trim, parseDate, mapValues] = transforms;

describe("lookup table text", () => {
  it("parses key=value lines, keeping '=' inside values and skipping junk", () => {
    expect(linesToParams("pagado=0\n *= a=b \nno equals\n=orphan\n")).toEqual({
      pagado: "0",
      "*": "a=b",
    });
  });

  it("round-trips", () => {
    expect(paramsToLines({ a: "1", b: "2" })).toBe("a=1\nb=2");
  });
});

describe("ParamsEditor", () => {
  it("renders nothing for an unknown transform or one without params", () => {
    const { container, rerender } = render(
      <ParamsEditor target="email" spec={undefined} params={{}} onChange={vi.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
    rerender(<ParamsEditor target="email" spec={trim} params={{}} onChange={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("edits named params", () => {
    const onChange = vi.fn();
    render(<ParamsEditor target="due_date" spec={parseDate} params={{}} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("due_date format"), { target: { value: "%d/%m/%Y" } });
    expect(onChange).toHaveBeenCalledWith({ format: "%d/%m/%Y" });
  });

  it("shows the current value of a named param", () => {
    render(
      <ParamsEditor
        target="due_date"
        spec={parseDate}
        params={{ format: "%Y" }}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("due_date format")).toHaveValue("%Y");
  });

  it("edits a lookup table as lines", () => {
    const onChange = vi.fn();
    render(
      <ParamsEditor target="status" spec={mapValues} params={{ a: "1" }} onChange={onChange} />,
    );
    const box = screen.getByLabelText("status lookup table");
    expect(box).toHaveValue("a=1");
    fireEvent.change(box, { target: { value: "a=1\nb=2" } });
    expect(onChange).toHaveBeenCalledWith({ a: "1", b: "2" });
  });
});
