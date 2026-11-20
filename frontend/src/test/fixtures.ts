import type { FileProfile } from "../api/schemas";

export const profile: FileProfile = {
  file_id: "f1",
  filename: "clientes.csv",
  encoding: "utf-8",
  delimiter: ";",
  row_count: 300,
  columns: [
    { name: "Referencia", samples: ["CL-0001", "CL-0002"], distinct_count: 300, empty_ratio: 0 },
    { name: "Correo", samples: ["ana@example.com"], distinct_count: 299, empty_ratio: 0.25 },
  ],
};
