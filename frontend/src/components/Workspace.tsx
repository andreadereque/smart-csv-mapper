import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getTargetSchema, getTransforms, suggestMapping } from "../api/client";
import type { FieldMapping, FileProfile, MappingProposal } from "../api/schemas";
import { ColumnProfileTable } from "./ColumnProfileTable";
import { ExportPanel } from "./ExportPanel";
import { MappingTable } from "./MappingTable";
import { PreviewPanel } from "./PreviewPanel";

export function replaceField(fields: FieldMapping[], changed: FieldMapping): FieldMapping[] {
  return fields.map((field) => {
    if (field.target === changed.target) {
      return changed;
    }
    return field;
  });
}

function Review({ profile, proposal }: { profile: FileProfile; proposal: MappingProposal }) {
  const [fields, setFields] = useState(proposal.fields);
  const targets = useQuery({ queryKey: ["schema"], queryFn: getTargetSchema, staleTime: Infinity });
  const transforms = useQuery({
    queryKey: ["transforms"],
    queryFn: getTransforms,
    staleTime: Infinity,
  });

  function update(changed: FieldMapping) {
    setFields((current) => replaceField(current, changed));
  }

  if (!targets.data || !transforms.data) {
    return <p role="status">Loading the schema…</p>;
  }
  return (
    <>
      <section aria-labelledby="review-title">
        <h2 id="review-title">2. Review the mapping</h2>
        <p className="muted">
          Proposed by {proposal.model} (prompt {proposal.prompt_version}, {proposal.attempts}{" "}
          attempt(s)). Yellow rows need a look. Any change you make is marked as yours.
        </p>
        {proposal.warnings.map((w) => (
          <p key={w} className="warning">
            {w}
          </p>
        ))}
        <MappingTable
          fields={fields}
          columns={profile.columns.map((c) => c.name)}
          targets={targets.data}
          transforms={transforms.data}
          onChange={update}
        />
      </section>
      <PreviewPanel
        fileId={profile.file_id}
        fields={fields}
        targets={targets.data.map((t) => t.name)}
      />
      <ExportPanel fileId={profile.file_id} fields={fields} />
    </>
  );
}

export function Workspace({ profile }: { profile: FileProfile }) {
  const proposal = useQuery({
    queryKey: ["suggest", profile.file_id],
    queryFn: () => suggestMapping(profile.file_id),
    staleTime: Infinity,
    retry: false,
  });
  return (
    <>
      <ColumnProfileTable profile={profile} />
      {proposal.isPending && (
        <p role="status">The model is reading your columns… (about 15 s on a laptop)</p>
      )}
      {proposal.isError && (
        <p role="alert" className="error">
          {proposal.error.message}
        </p>
      )}
      {proposal.data && <Review profile={profile} proposal={proposal.data} />}
    </>
  );
}
