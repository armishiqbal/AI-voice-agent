export function buildKnowledgeImportUrl(apiUrl, { filename, source, propertyId, city, language, version }) {
  const query = new URLSearchParams({ filename, source, language, source_version: version });
  if (propertyId.trim()) query.set("property_id", propertyId.trim());
  if (city.trim()) query.set("city", city.trim());
  return `${apiUrl.replace(/\/+$/, "")}/v1/knowledge/ingest-file?${query.toString()}`;
}

function isRecord(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function parseKnowledgeImportResult(value) {
  if (!isRecord(value) || !Number.isInteger(value.accepted) || value.accepted < 0) return null;
  if (typeof value.source !== "string" || !isRecord(value.metadata)) return null;
  return { accepted: value.accepted, source: value.source, metadata: value.metadata };
}
