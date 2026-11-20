import { useMutation } from "@tanstack/react-query";
import { useState, type DragEvent } from "react";
import { uploadFile } from "../api/client";
import type { FileProfile } from "../api/schemas";

export function UploadStep({ onUploaded }: { onUploaded: (profile: FileProfile) => void }) {
  const [dragging, setDragging] = useState(false);
  const upload = useMutation({ mutationFn: uploadFile, onSuccess: onUploaded });

  function send(files: FileList | null) {
    const file = files?.[0];
    if (file) {
      upload.mutate(file);
    }
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    send(event.dataTransfer.files);
  }

  let zoneClass = "dropzone";
  if (dragging) {
    zoneClass = "dropzone dragging";
  }

  return (
    <section aria-labelledby="upload-title">
      <h2 id="upload-title">1. Upload a CSV</h2>
      <label
        className={zoneClass}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <span>Drop a .csv, .tsv or .txt file here, or click to choose one</span>
        <input
          type="file"
          accept=".csv,.tsv,.txt"
          aria-label="CSV file"
          disabled={upload.isPending}
          onChange={(event) => send(event.target.files)}
        />
      </label>
      {upload.isPending && <p role="status">Reading the file…</p>}
      {upload.isError && (
        <p role="alert" className="error">
          {upload.error.message}
        </p>
      )}
    </section>
  );
}
