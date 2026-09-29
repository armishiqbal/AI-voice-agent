import React, { useEffect, useState, type FormEvent } from "react";
import { buildInventoryImportUrl, buildInventoryTemplateDataUrl, parseInventoryImportResult, type InventoryImportResult } from "./inventoryImport.mjs";

type InventoryImportPanelProps = {
  apiUrl: string;
  onImportComplete: () => void;
  autoOpen?: boolean;
};

function apiErrorMessage(value: unknown, status: number): string {
  if (typeof value === "object" && value !== null && "detail" in value) {
    const detail = value.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      const fields = detail.flatMap((item) => {
        if (typeof item !== "object" || item === null || !("msg" in item)) return [];
        return typeof item.msg === "string" ? [item.msg] : [];
      });
      if (fields.length) return fields.join("; ");
    }
  }
  if (status === 401) return "Admin API key was rejected. Check it and retry.";
  return `Inventory import failed (HTTP ${status}). Check the file and server logs.`;
}

export function InventoryImportPanel({ apiUrl, onImportComplete, autoOpen = false }: InventoryImportPanelProps) {
  const [isOpen, setIsOpen] = useState(autoOpen);
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState("");
  const [adminKey, setAdminKey] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<InventoryImportResult | null>(null);

  useEffect(() => {
    if (autoOpen) setIsOpen(true);
  }, [autoOpen]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setResult(null);
    if (!file || !source.trim() || !reviewed) {
      setError("Choose a file, provide its source, and confirm the owner-reviewed inventory before importing.");
      return;
    }
    if (!/\.csv$|\.json$/i.test(file.name)) {
      setError("Inventory imports support CSV and JSON files.");
      return;
    }

    setSubmitting(true);
    try {
      const headers = adminKey.trim() ? { "X-Admin-API-Key": adminKey.trim() } : undefined;
      const response = await fetch(buildInventoryImportUrl(apiUrl, file.name, source.trim()), {
        method: "POST",
        headers,
        body: file,
      });
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        setError(apiErrorMessage(body, response.status));
        return;
      }
      const imported = parseInventoryImportResult(body);
      if (!imported) {
        setError("The server returned an unexpected inventory import result.");
        return;
      }
      setResult(imported);
      onImportComplete();
    } catch {
      setError("Could not reach the inventory service. Check the connection and retry.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <details className="inventory-import-panel" open={isOpen} onToggle={(event) => setIsOpen(event.currentTarget.open)}>
      <summary>Staff tools · Import property inventory</summary>
      <p className="inventory-import-help">
        Upload an owner-reviewed CSV or JSON file. The backend validates every record; rejected rows are not imported.
        Existing property IDs are updated in place.
        An admin key, if required by this server, stays in this dialog and is not saved.
      </p>
      <a className="inventory-template-link" href={buildInventoryTemplateDataUrl()} download="owner-reviewed-property-inventory.csv">
        Download a blank CSV template
      </a>
      <p className="inventory-template-note">Headers only—no demo listings. Use purpose sale/rent/commercial/investment, PKR integer prices, true/false availability, and | between list values.</p>
      <form className="inventory-import-form" onSubmit={(event) => void submit(event)}>
        <label>
          <span>Inventory file</span>
          <input
            type="file"
            accept=".csv,.json,text/csv,application/json"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setReviewed(false);
            }}
          />
        </label>
        <label>
          <span>Source label</span>
          <input
            type="text"
            required
            minLength={3}
            maxLength={200}
            value={source}
            onChange={(event) => {
              setSource(event.target.value);
              setReviewed(false);
            }}
            placeholder="e.g. owner-approved inventory · revision 1"
          />
        </label>
        <label>
          <span>Admin API key <small>(only if this server requires it)</small></span>
          <input
            type="password"
            autoComplete="off"
            value={adminKey}
            onChange={(event) => setAdminKey(event.target.value)}
            placeholder="Kept in memory while this dialog is open"
          />
        </label>
        <label className="inventory-import-confirm">
          <input type="checkbox" checked={reviewed} onChange={(event) => setReviewed(event.target.checked)} />
          <span>I reviewed this file and approve updating these property records.</span>
        </label>
        <button className="inventory-import-submit" type="submit" disabled={submitting || !file || source.trim().length < 3 || !reviewed}>
          {submitting ? "Validating and importing…" : "Validate and import listings"}
        </button>
      </form>
      {error && <p className="inventory-import-feedback error" role="alert">{error}</p>}
      {result && (
        <div className="inventory-import-feedback success" role="status" aria-live="polite">
          <p>{result.accepted} accepted · {result.rejected} rejected · batch {result.batchId}</p>
          <p>Source: {result.source}. The inventory list is refreshing.</p>
          {result.validationErrors.length > 0 && (
            <ul>
              {result.validationErrors.map((issue, index) => (
                <li key={`${issue.row}-${issue.field}-${index}`}>
                  Row {issue.row}, {issue.field}: {issue.message}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </details>
  );
}
