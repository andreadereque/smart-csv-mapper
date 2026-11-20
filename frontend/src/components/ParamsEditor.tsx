import type { TransformInfo } from "../api/schemas";

type Props = {
  target: string;
  spec: TransformInfo | undefined;
  params: Record<string, string>;
  onChange: (params: Record<string, string>) => void;
};

export function linesToParams(text: string): Record<string, string> {
  const params: Record<string, string> = {};
  for (const line of text.split("\n")) {
    const [key, ...rest] = line.split("=");
    if (key.trim() !== "" && rest.length > 0) {
      params[key.trim()] = rest.join("=").trim();
    }
  }
  return params;
}

export function paramsToLines(params: Record<string, string>): string {
  return Object.entries(params)
    .map(([key, value]) => `${key}=${value}`)
    .join("\n");
}

export function ParamsEditor({ target, spec, params, onChange }: Props) {
  if (spec === undefined) {
    return null;
  }
  if (spec.free_params) {
    return (
      <textarea
        aria-label={`${target} lookup table`}
        placeholder={"pagado=0\n*=1"}
        rows={3}
        defaultValue={paramsToLines(params)}
        onChange={(event) => onChange(linesToParams(event.target.value))}
      />
    );
  }
  const names = [...spec.required_params, ...spec.optional_params];
  return (
    <>
      {names.map((name) => (
        <input
          key={name}
          aria-label={`${target} ${name}`}
          placeholder={name}
          value={params[name] ?? ""}
          onChange={(event) => onChange({ ...params, [name]: event.target.value })}
        />
      ))}
    </>
  );
}
