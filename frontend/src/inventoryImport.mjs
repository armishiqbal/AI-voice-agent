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

function isRecord(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function parseInventoryImportResult(value) {
  if (!isRecord(value)) return null;
  const { accepted, rejected, source, batch_id: batchId, validation_errors: rawErrors } = value;
  if (
    !Number.isInteger(accepted) || accepted < 0
    || !Number.isInteger(rejected) || rejected < 0
    || typeof source !== "string"
    || typeof batchId !== "string"
    || !Array.isArray(rawErrors)
  ) return null;

  const validationErrors = rawErrors.flatMap((issue) => {
    if (!isRecord(issue)) return [];
    const { row, field, message } = issue;
    if (!Number.isInteger(row) || typeof field !== "string" || typeof message !== "string") return [];
    return [{ row, field, message }];
  });
  return { accepted, rejected, source, batchId, validationErrors };
}
