import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError, exportCsv, type ExportResult } from "../api/client";
import { rows } from "../api/plural";
import type { FieldMapping } from "../api/schemas";

type Props = { fileId: string; fields: FieldMapping[] };

export function download(result: ExportResult) {
  const url = URL.createObjectURL(result.csv);
  const link = document.createElement("a");
  link.href = url;
  link.download = result.filename;
  link.click();
  URL.revokeObjectURL(url);
}

function InvalidRows({ error, onSkip }: { error: ApiError; onSkip: () => void }) {
  return (
    <div role="alert" className="error-box">
      <p className="error">{error.message}</p>
      <ul>
        {error.cellErrors.slice(0, 5).map((e) => (
          <li key={`${e.row}-${e.field}`}>
            Row {e.row}, {e.field}: {e.reason}
          </li>
        ))}
      </ul>
      <button type="button" className="secondary" onClick={onSkip}>
        Skip {rows(error.invalidRowCount)} with errors and export
      </button>
    </div>
  );
}

export function ExportPanel({ fileId, fields }: Props) {
  const queryClient = useQueryClient();
  const exporter = useMutation({
    mutationFn: (skipInvalid: boolean) => exportCsv(fileId, fields, skipInvalid),
    onSuccess: (result) => {
      download(result);
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });
  const error = exporter.error;
  let invalidRows: ApiError | null = null;
  if (error instanceof ApiError && error.code === "invalid_rows") {
    invalidRows = error;
  }
  return (
    <section aria-labelledby="export-title">
      <h2 id="export-title">4. Export</h2>
      <button type="button" disabled={exporter.isPending} onClick={() => exporter.mutate(false)}>
        Export clean CSV
      </button>
      {exporter.isPending && <p role="status">Transforming the whole file…</p>}
      {invalidRows && <InvalidRows error={invalidRows} onSkip={() => exporter.mutate(true)} />}
      {error && !invalidRows && (
        <p role="alert" className="error">
          {error.message}
        </p>
      )}
      {exporter.data && (
        <p className="ok-text" role="status">
          {rows(exporter.data.exported)} exported to {exporter.data.filename},{" "}
          {exporter.data.skipped} skipped.
        </p>
      )}
    </section>
  );
}
