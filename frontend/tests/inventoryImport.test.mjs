import assert from "node:assert/strict";
import test from "node:test";
import {
  buildInventoryImportUrl,
  buildInventoryTemplateDataUrl,
  buildInventoryValidateUrl,
  parseInventoryImportResult,
  parseInventoryValidationResult,
} from "../src/inventoryImport.mjs";

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

test("inventory validation URL uses the preview endpoint", () => {
  assert.equal(
    buildInventoryValidateUrl("http://localhost:8000/", "company.csv", "approved rev 2"),
    "http://localhost:8000/v1/properties/validate-file?filename=company.csv&source=approved+rev+2",
  );
});

test("inventory validation response is parsed without requiring an import batch", () => {
  assert.deepEqual(parseInventoryValidationResult({
    accepted: 3,
    rejected: 1,
    source: "approved-v2",
    validation_errors: [{ row: 5, field: "id", message: "Duplicate property ID" }],
  }), {
    accepted: 3,
    rejected: 1,
    source: "approved-v2",
    validationErrors: [{ row: 5, field: "id", message: "Duplicate property ID" }],
  });
  assert.equal(parseInventoryValidationResult({ accepted: 3, rejected: 0 }), null);
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
