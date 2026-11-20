import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { z } from "zod";
import { server } from "../test/server";
import { profile } from "../test/fixtures";
import { ApiError, request, uploadFile } from "./client";

describe("request", () => {
  it("returns validated data", async () => {
    server.use(http.get("/api/thing", () => HttpResponse.json({ a: 1 })));
    await expect(request("/thing", z.object({ a: z.number() }))).resolves.toEqual({ a: 1 });
  });

  it("turns an API error body into an ApiError with code and message", async () => {
    server.use(
      http.get("/api/thing", () =>
        HttpResponse.json(
          { code: "duplicate_header", detail: "Duplicate column" },
          { status: 422 },
        ),
      ),
    );
    const error = await request("/thing", z.object({})).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 422,
      code: "duplicate_header",
      message: "Duplicate column",
    });
  });

  it("uses a generic message when the detail is not text", async () => {
    server.use(
      http.get("/api/thing", () =>
        HttpResponse.json({ detail: [{ loc: ["x"] }] }, { status: 422 }),
      ),
    );
    await expect(request("/thing", z.object({}))).rejects.toMatchObject({
      message: "Request failed (422)",
      code: undefined,
    });
  });

  it("copes with an error response that is not JSON", async () => {
    server.use(http.get("/api/thing", () => new HttpResponse("boom", { status: 500 })));
    await expect(request("/thing", z.object({}))).rejects.toMatchObject({
      status: 500,
      message: "Request failed (500)",
    });
  });

  it("copes with an error body of an unexpected shape", async () => {
    server.use(http.get("/api/thing", () => HttpResponse.json(["x"], { status: 502 })));
    await expect(request("/thing", z.object({}))).rejects.toMatchObject({
      message: "Request failed (502)",
    });
  });

  it("rejects a success response that does not match the schema", async () => {
    server.use(http.get("/api/thing", () => HttpResponse.json({ a: "not a number" })));
    await expect(request("/thing", z.object({ a: z.number() }))).rejects.toMatchObject({
      message: "The server sent an unexpected response.",
    });
  });

  it("explains when the server cannot be reached", async () => {
    server.use(http.get("/api/thing", () => HttpResponse.error()));
    await expect(request("/thing", z.object({}))).rejects.toMatchObject({
      status: 0,
      message: "Cannot reach the server. Is the backend running?",
    });
  });
});

describe("uploadFile", () => {
  it("posts the file as multipart form data", async () => {
    let received: File | null = null;
    server.use(
      http.post("/api/files", async ({ request }) => {
        received = (await request.formData()).get("file") as File;
        return HttpResponse.json(profile, { status: 201 });
      }),
    );
    const result = await uploadFile(new File(["a,b\n1,2\n"], "data.csv", { type: "text/csv" }));
    expect(result).toEqual(profile);
    expect(received).not.toBeNull();
    // jsdom renames multipart files to "blob", so check the content that was sent instead.
    expect(await received!.text()).toBe("a,b\n1,2\n");
  });
});
