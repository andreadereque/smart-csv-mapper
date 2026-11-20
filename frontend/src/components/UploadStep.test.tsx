import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { profile } from "../test/fixtures";
import { renderWithQuery } from "../test/render";
import { server } from "../test/server";
import { UploadStep } from "./UploadStep";

const csv = () => new File(["a;b\n1;2\n"], "clientes.csv", { type: "text/csv" });

describe("UploadStep", () => {
  it("uploads the chosen file and hands back the profile", async () => {
    server.use(http.post("/api/files", () => HttpResponse.json(profile, { status: 201 })));
    const onUploaded = vi.fn();
    renderWithQuery(<UploadStep onUploaded={onUploaded} />);
    await userEvent.upload(screen.getByLabelText("CSV file"), csv());
    await vi.waitFor(() =>
      expect(onUploaded).toHaveBeenCalledWith(
        profile,
        expect.anything(),
        undefined,
        expect.anything(),
      ),
    );
  });

  it("shows progress while the file is being read", async () => {
    server.use(
      http.post("/api/files", async () => {
        await delay(50);
        return HttpResponse.json(profile, { status: 201 });
      }),
    );
    renderWithQuery(<UploadStep onUploaded={vi.fn()} />);
    await userEvent.upload(screen.getByLabelText("CSV file"), csv());
    expect(await screen.findByRole("status")).toHaveTextContent("Reading the file…");
    expect(screen.getByLabelText("CSV file")).toBeDisabled();
  });

  it("shows the server's explanation when the file is rejected", async () => {
    server.use(
      http.post("/api/files", () =>
        HttpResponse.json(
          { code: "duplicate_header", detail: "Duplicate column header: 'email'." },
          { status: 422 },
        ),
      ),
    );
    renderWithQuery(<UploadStep onUploaded={vi.fn()} />);
    await userEvent.upload(screen.getByLabelText("CSV file"), csv());
    expect(await screen.findByRole("alert")).toHaveTextContent("Duplicate column header: 'email'.");
  });

  it("accepts a dropped file and highlights the zone while dragging", async () => {
    server.use(http.post("/api/files", () => HttpResponse.json(profile, { status: 201 })));
    const onUploaded = vi.fn();
    renderWithQuery(<UploadStep onUploaded={onUploaded} />);
    const zone = screen.getByText(/Drop a .csv/).closest("label")!;
    fireEvent.dragOver(zone);
    expect(zone).toHaveClass("dragging");
    fireEvent.dragLeave(zone);
    expect(zone).not.toHaveClass("dragging");
    fireEvent.dragOver(zone);
    fireEvent.drop(zone, { dataTransfer: { files: [csv()] } });
    expect(zone).not.toHaveClass("dragging");
    await vi.waitFor(() => expect(onUploaded).toHaveBeenCalled());
  });

  it("sends nothing when the selection is empty", async () => {
    let requests = 0;
    server.use(
      http.post("/api/files", () => {
        requests += 1;
        return HttpResponse.json(profile, { status: 201 });
      }),
    );
    renderWithQuery(<UploadStep onUploaded={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("CSV file"), { target: { files: [] } });
    await delay(30);
    expect(requests).toBe(0);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
