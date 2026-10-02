const inventoryTemplateHeaders = [
  "id", "title", "city", "area", "purpose", "price_pkr", "bedrooms", "size_sqft",
  "amenities", "investment_goals", "nearby_schools", "nearby_hospitals", "developer",
  "payment_plan", "available", "assigned_employee", "source_version",
];

export function buildInventoryTemplateDataUrl() {
  const csv = `${inventoryTemplateHeaders.join(",")}\n`;
  return `data:text/csv;charset=utf-8,${encodeURIComponent(csv)}`;
}

export function buildInventoryImportUrl(apiUrl, filename, source) {
  const query = new URLSearchParams({ filename, source });
  return `${apiUrl.replace(/\/+$/, "")}/v1/properties/import-file?${query.toString()}`;
}

export function buildInventoryValidateUrl(apiUrl, filename, source) {
  const query = new URLSearchParams({ filename, source });
  return `${apiUrl.replace(/\/+$/, "")}/v1/properties/validate-file?${query.toString()}`;
}

function isRecord(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function parseInventoryValidationResult(value) {
  if (!isRecord(value)) return null;
  const { accepted, rejected, source, validation_errors: rawErrors } = value;
  if (
    !Number.isInteger(accepted) || accepted < 0
    || !Number.isInteger(rejected) || rejected < 0
    || typeof source !== "string"
    || !Array.isArray(rawErrors)
  ) return null;

  const validationErrors = rawErrors.flatMap((issue) => {
    if (!isRecord(issue)) return [];
    const { row, field, message } = issue;
    if (!Number.isInteger(row) || typeof field !== "string" || typeof message !== "string") return [];
    return [{ row, field, message }];
  });
  return { accepted, rejected, source, validationErrors };
}

export function parseInventoryImportResult(value) {
  const preview = parseInventoryValidationResult(value);
  if (!preview || !isRecord(value) || typeof value.batch_id !== "string") return null;
  return { ...preview, batchId: value.batch_id };
}
