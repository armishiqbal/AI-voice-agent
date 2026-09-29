import React, { useState, type FormEvent } from "react";
import { buildKnowledgeImportUrl, parseKnowledgeImportResult, type KnowledgeImportResult } from "./knowledgeImport.mjs";

type KnowledgeImportPanelProps = { apiUrl: string };

function responseError(value: unknown, status: number): string {
  if (typeof value === "object" && value !== null && "detail" in value && typeof value.detail === "string") {
    return value.detail;
  }
  if (status === 401) return "Admin API key was rejected. Check it and retry.";
  return `Document ingestion failed (HTTP ${status}). Check the file and knowledge-service readiness.`;
}

export function KnowledgeImportPanel({ apiUrl }: KnowledgeImportPanelProps) {
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState("");
  const [propertyId, setPropertyId] = useState("");
  const [city, setCity] = useState("");
  const [language, setLanguage] = useState("en");
  const [version, setVersion] = useState("import-1");
  const [adminKey, setAdminKey] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<KnowledgeImportResult | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setResult(null);
    if (!file || source.trim().length < 3 || version.trim().length < 1) {
      setError("Choose a PDF, TXT, or Markdown file and provide a source and version.");
      return;
    }
    if (!/\.(pdf|txt|md)$/i.test(file.name)) {
      setError("Knowledge files support PDF, TXT, or Markdown formats.");
      return;
    }

    setSubmitting(true);
    try {
      const headers = adminKey.trim() ? { "X-Admin-API-Key": adminKey.trim() } : undefined;
      const response = await fetch(buildKnowledgeImportUrl(apiUrl, {
        filename: file.name,
        source: source.trim(),
        propertyId,
        city,
        language,
        version: version.trim(),
      }), { method: "POST", headers, body: file });
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        setError(responseError(body, response.status));
        return;
      }
      const imported = parseKnowledgeImportResult(body);
      if (!imported) {
        setError("The server returned an unexpected document-ingestion result.");
        return;
      }
      setResult(imported);
    } catch {
      setError("Could not reach the knowledge service. Check the connection and retry.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <details className="inventory-import-panel">
      <summary>Staff tools · Import brochures and FAQs</summary>
      <p className="inventory-import-help">
        Upload owner-approved PDF, TXT, or Markdown documents. Set the source and revision so retrieved answers retain provenance.
        An admin key, if required, stays in this dialog and is not saved.
      </p>
      <form className="inventory-import-form" onSubmit={(event) => void submit(event)}>
        <label>
          <span>Brochure or FAQ file</span>
          <input type="file" accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        </label>
        <label>
          <span>Source label</span>
          <input type="text" required minLength={3} maxLength={200} value={source} onChange={(event) => setSource(event.target.value)} placeholder="e.g. DHA payment plan brochure" />
        </label>
        <label>
          <span>Source revision</span>
          <input type="text" required minLength={1} maxLength={100} value={version} onChange={(event) => setVersion(event.target.value)} />
        </label>
        <label>
          <span>Property ID <small>(leave blank for general FAQs)</small></span>
          <input type="text" maxLength={128} value={propertyId} onChange={(event) => setPropertyId(event.target.value)} />
        </label>
        <label>
          <span>City <small>(leave blank for general documents)</small></span>
          <input type="text" maxLength={64} value={city} onChange={(event) => setCity(event.target.value)} />
        </label>
        <label>
          <span>Document language</span>
          <select value={language} onChange={(event) => setLanguage(event.target.value)}>
            <option value="en">English</option>
            <option value="ur-Latn">UrduLish · Latin</option>
            <option value="ur-Arab">Urdu · Arabic script</option>
            <option value="hi">Hindi</option>
            <option value="ar">Arabic</option>
            <option value="pa">Punjabi</option>
            <option value="bn">Bengali</option>
          </select>
        </label>
        <label className="inventory-import-key-field">
          <span>Admin API key <small>(only if this server requires it)</small></span>
          <input type="password" autoComplete="off" value={adminKey} onChange={(event) => setAdminKey(event.target.value)} placeholder="Kept in memory while this dialog is open" />
        </label>
        <button className="inventory-import-submit" type="submit" disabled={submitting || !file || source.trim().length < 3}>
          {submitting ? "Ingesting document…" : "Chunk and ingest document"}
        </button>
      </form>
      {error && <p className="inventory-import-feedback error" role="alert">{error}</p>}
      {result && (
        <p className="inventory-import-feedback success" role="status" aria-live="polite">
          Indexed {result.accepted} chunks from “{result.source}” ({String(result.metadata.version ?? "version unavailable")} · {String(result.metadata.language ?? "language unavailable")} ).
        </p>
      )}
    </details>
  );
}
