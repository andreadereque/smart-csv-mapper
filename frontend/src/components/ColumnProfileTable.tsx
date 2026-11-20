import type { FileProfile } from "../api/schemas";

function delimiterName(delimiter: string): string {
  if (delimiter === "\t") {
    return "tab";
  }
  return `"${delimiter}"`;
}

function percent(ratio: number): string {
  return `${Math.round(ratio * 100)}%`;
}

export function ColumnProfileTable({ profile }: { profile: FileProfile }) {
  return (
    <section aria-labelledby="profile-title">
      <h2 id="profile-title">{profile.filename}</h2>
      <p className="muted">
        {profile.row_count} rows · {profile.columns.length} columns · {profile.encoding} · delimiter{" "}
        {delimiterName(profile.delimiter)}
      </p>
      <table>
        <thead>
          <tr>
            <th scope="col">Column</th>
            <th scope="col">Sample values</th>
            <th scope="col">Distinct</th>
            <th scope="col">Empty</th>
          </tr>
        </thead>
        <tbody>
          {profile.columns.map((column) => (
            <tr key={column.name}>
              <th scope="row">{column.name}</th>
              <td>{column.samples.join(" · ")}</td>
              <td>{column.distinct_count}</td>
              <td>{percent(column.empty_ratio)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
