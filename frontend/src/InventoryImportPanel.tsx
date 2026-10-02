import React, { useEffect, useState, type FormEvent } from "react";
import {
  buildInventoryImportUrl,
  buildInventoryTemplateDataUrl,
  buildInventoryValidateUrl,
  parseInventoryImportResult,
  parseInventoryValidationResult,
  type InventoryImportResult,
  type InventoryValidationResult,
} from "./inventoryImport.mjs";

type InventoryImportPanelProps = {
  apiUrl: string;
  onImportComplete: () => void;
  autoOpen?: boolean;
};

function apiErrorMessage(value: unknown, status: number): string {
  if (typeof value === "object" && value !== null && "detail" in value) {
    const detail = value.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (typeof detail === "object" && detail !== null && "message" in detail) {
      return typeof detail.message === "string" ? detail.message : `Inventory import failed (HTTP ${status}).`;
    }
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
  const [preview, setPreview] = useState<InventoryValidationResult | null>(null);
  const [result, setResult] = useState<InventoryImportResult | null>(null);

  useEffect(() => {
    if (autoOpen) setIsOpen(true);
  }, [autoOpen]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
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
      if (!preview) {
        const response = await fetch(buildInventoryValidateUrl(apiUrl, file.name, source.trim()), {
          method: "POST",
          headers,
          body: file,
        });
        const body: unknown = await response.json().catch(() => null);
        if (!response.ok) {
          setError(apiErrorMessage(body, response.status));
          return;
        }
        const validated = parseInventoryValidationResult(body);
        if (!validated) {
          setError("The server returned an unexpected inventory validation result.");
          return;
        }
        setPreview(validated);
        if (validated.rejected > 0) {
          setError("No listings were imported. Fix every rejected row, choose the corrected file, and validate it again.");
        } else if (validated.accepted === 0) {
          setError("The file contains no property records, so it cannot be imported.");
        }
        return;
      }

      if (preview.rejected > 0 || preview.accepted === 0) {
        setError("Fix the validation issues before importing.");
        return;
      }

      const response = await fetch(buildInventoryImportUrl(apiUrl, file.name, source.trim()), {
        method: "POST",
        headers,
        body: file,
      });
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        if (typeof body === "object" && body !== null && "detail" in body) {
          const rejectedPreview = parseInventoryValidationResult(body.detail);
          if (rejectedPreview) setPreview(rejectedPreview);
        }
        setError(apiErrorMessage(body, response.status));
        return;
      }
      const imported = parseInventoryImportResult(body);
      if (!imported) {
        setError("The server returned an unexpected inventory import result.");
        return;
      }
      setResult(imported);
      setPreview(null);
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
        Upload an owner-reviewed CSV or JSON file. Preview validation first; the import is blocked unless every record is valid.
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
              setPreview(null);
              setResult(null);
              setError("");
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
              setPreview(null);
              setResult(null);
              setError("");
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
        <button
          className="inventory-import-submit"
          type="submit"
          disabled={
            submitting || !file || source.trim().length < 3 || !reviewed
            || (preview !== null && (preview.rejected > 0 || preview.accepted === 0))
          }
        >
          {submitting
            ? (preview ? "Importing validated listings…" : "Validating file…")
            : preview
              ? `Import ${preview.accepted} validated listings`
              : "Validate inventory file"}
        </button>
      </form>
      {error && <p className="inventory-import-feedback error" role="alert">{error}</p>}
      {preview && (
        <div
          className={`inventory-import-feedback ${preview.rejected > 0 || preview.accepted === 0 ? "error" : "success"}`}
          role="status"
          aria-live="polite"
        >
          <p>Validation: {preview.accepted} accepted · {preview.rejected} rejected</p>
          <p>Source: {preview.source}. {preview.rejected === 0 && preview.accepted > 0 ? "Review the count, then confirm import." : "No listings were changed."}</p>
          {preview.validationErrors.length > 0 && (
            <ul>
              {preview.validationErrors.map((issue, index) => (
                <li key={`${issue.row}-${issue.field}-${index}`}>
                  Row {issue.row}, {issue.field}: {issue.message}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
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
