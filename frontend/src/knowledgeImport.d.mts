export type KnowledgeImportRequest = {
  filename: string;
  source: string;
  propertyId: string;
  city: string;
  language: string;
  version: string;
};
export type KnowledgeImportResult = { accepted: number; source: string; metadata: Record<string, unknown> };
export declare function buildKnowledgeImportUrl(apiUrl: string, request: KnowledgeImportRequest): string;
export declare function parseKnowledgeImportResult(value: unknown): KnowledgeImportResult | null;
