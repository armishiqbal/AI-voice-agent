import assert from "node:assert/strict";
import test from "node:test";
import { buildKnowledgeImportUrl, parseKnowledgeImportResult } from "../src/knowledgeImport.mjs";

test("knowledge import URL sends provenance and omits empty property filters", () => {
  assert.equal(buildKnowledgeImportUrl("http://localhost:8000/", {
    filename: "DHA brochure.pdf",
    source: "Owner docs",
    propertyId: "",
    city: "",
    language: "ur-Latn",
    version: "rev 2",
  }), "http://localhost:8000/v1/knowledge/ingest-file?filename=DHA+brochure.pdf&source=Owner+docs&language=ur-Latn&source_version=rev+2");
});

test("knowledge import parser rejects malformed server responses", () => {
  assert.deepEqual(parseKnowledgeImportResult({ accepted: 4, source: "faq-v1", metadata: { language: "en" } }), {
    accepted: 4,
    source: "faq-v1",
    metadata: { language: "en" },
  });
  assert.equal(parseKnowledgeImportResult({ accepted: -1, source: "bad", metadata: {} }), null);
  assert.equal(parseKnowledgeImportResult({ accepted: 4, source: "bad", metadata: [] }), null);
});
