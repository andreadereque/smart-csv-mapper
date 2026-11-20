import { useQuery } from "@tanstack/react-query";
import { getAudit } from "../api/client";

export function AuditHistory() {
  const audit = useQuery({ queryKey: ["audit"], queryFn: getAudit });
  return (
    <section aria-labelledby="audit-title">
      <h2 id="audit-title">Recent exports</h2>
      {audit.isError && <p className="error">{audit.error.message}</p>}
      {audit.data?.length === 0 && <p className="muted">Nothing exported yet.</p>}
      {audit.data && audit.data.length > 0 && (
        <table>
          <thead>
            <tr>
              <th scope="col">When (UTC)</th>
              <th scope="col">File</th>
              <th scope="col">Exported</th>
              <th scope="col">Skipped</th>
              <th scope="col">Model</th>
            </tr>
          </thead>
          <tbody>
            {audit.data.map((entry) => (
              <tr key={entry.id}>
                <td>{entry.at.replace("T", " ").replace("+00:00", "")}</td>
                <td>{entry.filename}</td>
                <td>{entry.rows_exported}</td>
                <td>{entry.rows_skipped}</td>
                <td>{entry.model}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
