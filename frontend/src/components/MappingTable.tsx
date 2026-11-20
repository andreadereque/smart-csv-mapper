import type { FieldMapping, TargetField, TransformInfo } from "../api/schemas";
import { confidenceBadge, originLabel } from "./badges";
import { ParamsEditor } from "./ParamsEditor";

type Props = {
  fields: FieldMapping[];
  columns: string[];
  targets: TargetField[];
  transforms: TransformInfo[];
  onChange: (field: FieldMapping) => void;
};

const NO_COLUMN = "";

function transformLabel(spec: TransformInfo): string {
  if (spec.kind === "ai") {
    return `${spec.name} (AI)`;
  }
  return spec.name;
}

export function MappingTable({ fields, columns, targets, transforms, onChange }: Props) {
  const byName = new Map(transforms.map((t) => [t.name, t]));
  const required = new Set(targets.filter((t) => t.required).map((t) => t.name));

  function edit(field: FieldMapping, changes: Partial<FieldMapping>) {
    onChange({ ...field, ...changes, origin: "user", confidence: 1 });
  }

  return (
    <table className="mapping">
      <thead>
        <tr>
          <th scope="col">Target field</th>
          <th scope="col">Column in your file</th>
          <th scope="col">Transform</th>
          <th scope="col">Params</th>
          <th scope="col">Source</th>
          <th scope="col">Confidence</th>
        </tr>
      </thead>
      <tbody>
        {fields.map((field) => {
          const badge = confidenceBadge(field);
          return (
            <tr key={field.target} className={`tone-${badge.tone}`}>
              <th scope="row">
                {field.target}
                {required.has(field.target) && <span className="required"> *</span>}
              </th>
              <td>
                <select
                  aria-label={`${field.target} column`}
                  value={field.source ?? NO_COLUMN}
                  onChange={(event) => {
                    let source: string | null = event.target.value;
                    if (source === NO_COLUMN) {
                      source = null;
                    }
                    edit(field, { source });
                  }}
                >
                  <option value={NO_COLUMN}>— no column —</option>
                  {columns.map((column) => (
                    <option key={column} value={column}>
                      {column}
                    </option>
                  ))}
                </select>
              </td>
              <td>
                <select
                  aria-label={`${field.target} transform`}
                  value={field.transform}
                  onChange={(event) => edit(field, { transform: event.target.value, params: {} })}
                >
                  {transforms.map((spec) => (
                    <option key={spec.name} value={spec.name} title={spec.description}>
                      {transformLabel(spec)}
                    </option>
                  ))}
                </select>
              </td>
              <td>
                <ParamsEditor
                  target={field.target}
                  spec={byName.get(field.transform)}
                  params={field.params}
                  onChange={(params) => edit(field, { params })}
                />
              </td>
              <td>{originLabel(field.origin)}</td>
              <td>
                <span className={`badge ${badge.tone}`}>{badge.label}</span>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
