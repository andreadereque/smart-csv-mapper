import { expect, it } from "vitest";
import { rows } from "./plural";

it("uses the singular only for one", () => {
  expect([0, 1, 2].map(rows)).toEqual(["0 rows", "1 row", "2 rows"]);
});
