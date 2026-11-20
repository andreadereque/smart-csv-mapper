import { useState } from "react";
import type { FileProfile } from "./api/schemas";
import { ColumnProfileTable } from "./components/ColumnProfileTable";
import { UploadStep } from "./components/UploadStep";

export function App() {
  const [profile, setProfile] = useState<FileProfile | null>(null);

  return (
    <main>
      <header>
        <h1>smart-csv-mapper</h1>
        <p className="muted">
          The model proposes the column mapping, you review it, deterministic code does the rest.
        </p>
      </header>
      {profile === null && <UploadStep onUploaded={setProfile} />}
      {profile !== null && (
        <>
          <ColumnProfileTable profile={profile} />
          <button type="button" onClick={() => setProfile(null)}>
            Upload another file
          </button>
        </>
      )}
    </main>
  );
}
