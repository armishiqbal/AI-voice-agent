import assert from "node:assert/strict";
import test from "node:test";
import { buildInventoryImportUrl, buildInventoryTemplateDataUrl, parseInventoryImportResult } from "../src/inventoryImport.mjs";

test("downloadable inventory template contains the import schema and no sample property rows", () => {
  const url = buildInventoryTemplateDataUrl();
  const csv = decodeURIComponent(url.split(",", 2)[1]);
  assert.equal(url.startsWith("data:text/csv;charset=utf-8,"), true);
  assert.equal(csv.split("\n").length, 2);
  assert.equal(csv.endsWith("\n"), true);
  assert.deepEqual(csv.trim().split(","), [
    "id", "title", "city", "area", "purpose", "price_pkr", "bedrooms", "size_sqft",
    "amenities", "investment_goals", "nearby_schools", "nearby_hospitals", "developer",
    "payment_plan", "available", "assigned_employee", "source_version",
  ]);
});

test("inventory import URL encodes filename and source and removes API URL trailing slashes", () => {
  assert.equal(
    buildInventoryImportUrl("http://localhost:8000/", "DHA phase 6.csv", "Owner export & review"),
    "http://localhost:8000/v1/properties/import-file?filename=DHA+phase+6.csv&source=Owner+export+%26+review",
  );
});

test("inventory import response parser keeps only validated server fields", () => {
  assert.deepEqual(parseInventoryImportResult({
    accepted: 2,
    rejected: 1,
    source: "owner-reviewed-v1",
    batch_id: "batch-123",
    validation_errors: [
      { row: 4, field: "price_pkr", message: "Input should be greater than 0" },
      { row: "bad", field: "title", message: "ignored malformed issue" },
    ],
  }), {
    accepted: 2,
    rejected: 1,
    source: "owner-reviewed-v1",
    batchId: "batch-123",
    validationErrors: [
      { row: 4, field: "price_pkr", message: "Input should be greater than 0" },
    ],
  });
  assert.equal(parseInventoryImportResult({ accepted: "2", rejected: 0 }), null);
  assert.equal(parseInventoryImportResult(null), null);
});
