export type InventoryImportIssue = { row: number; field: string; message: string };
export type InventoryImportResult = {
  accepted: number;
  rejected: number;
  source: string;
  batchId: string;
  validationErrors: InventoryImportIssue[];
};
export declare function buildInventoryTemplateDataUrl(): string;
export declare function buildInventoryImportUrl(apiUrl: string, filename: string, source: string): string;
export declare function parseInventoryImportResult(value: unknown): InventoryImportResult | null;
