export type InventoryImportIssue = { row: number; field: string; message: string };
export type InventoryValidationResult = {
  accepted: number;
  rejected: number;
  source: string;
  validationErrors: InventoryImportIssue[];
};
export type InventoryImportResult = InventoryValidationResult & { batchId: string };
export declare function buildInventoryTemplateDataUrl(): string;
export declare function buildInventoryImportUrl(apiUrl: string, filename: string, source: string): string;
export declare function buildInventoryValidateUrl(apiUrl: string, filename: string, source: string): string;
export declare function parseInventoryValidationResult(value: unknown): InventoryValidationResult | null;
export declare function parseInventoryImportResult(value: unknown): InventoryImportResult | null;
