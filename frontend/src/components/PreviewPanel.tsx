import { useMutation } from "@tanstack/react-query";
import { previewRows } from "../api/client";
import type { FieldMapping, Preview } from "../api/schemas";
import { AIStatsLine } from "./AIStatsLine";

type Props = { fileId: string; fields: FieldMapping[]; targets: string[] };

function errorIndex(preview: Preview): Map<string, string> {
  return new Map(preview.errors.map((e) => [`${e.row}:${e.field}`, `${e.reason}`]));
}

function PreviewTable({ preview, targets }: { preview: Preview; targets: string[] }) {
  const errors = errorIndex(preview);
  const counts = Object.entries(preview.error_count_by_field);
  return (
    <>
      {counts.length === 0 && (
        <p className="ok-text">No errors in the first {preview.rows_checked} rows.</p>
      )}
      {counts.length > 0 && (
        <p className="error">
          Errors in the first {preview.rows_checked} rows:{" "}
          {counts.map(([field, n]) => `${field} (${n})`).join(", ")}
        </p>
      )}
      <AIStatsLine stats={preview.ai_stats} />
      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">#</th>
              {targets.map((t) => (
                <th key={t} scope="col">
                  {t}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {preview.rows.map((row, index) => (
              <tr key={index}>
                <th scope="row">{index + 1}</th>
                {targets.map((t) => {
                  const reason = errors.get(`${index + 1}:${t}`);
                  if (reason === undefined) {
                    return <td key={t}>{row[t]}</td>;
                  }
                  return (
                    <td key={t} className="cell-error" title={reason}>
                      ⚠ {reason}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export function PreviewPanel({ fileId, fields, targets }: Props) {
  const preview = useMutation({ mutationFn: () => previewRows(fileId, fields) });
  return (
    <section aria-labelledby="preview-title">
      <h2 id="preview-title">3. Preview</h2>
      <button type="button" disabled={preview.isPending} onClick={() => preview.mutate()}>
        Preview the first 20 rows
      </button>
      {preview.isPending && <p role="status">Transforming…</p>}
      {preview.isError && (
        <p role="alert" className="error">
          {preview.error.message}
        </p>
      )}
      {preview.data && <PreviewTable preview={preview.data} targets={targets} />}
    </section>
  );
}
