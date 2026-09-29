export type AvailabilityRecord = { available: boolean } | null | undefined;
export declare function canRequestVisit(property: AvailabilityRecord): boolean;
export declare function availabilityLabel(available: boolean): "Available" | "Unavailable";
export declare function inventorySourceLabel(source: string, version: string): string;
export declare function inventoryStatusSummary(
  loadState: "loading" | "error" | "ready",
  properties: AvailabilityRecord[],
): { tone: "loading" | "error" | "empty" | "ready"; label: string; detail: string };
export declare function shouldAutoOpenInventoryImport(
  loadState: "loading" | "error" | "ready",
  propertyCount: number,
): boolean;
export type PropertyBrowseFilters = {
  city?: string;
  area?: string;
  purpose?: string;
  maxPricePkr?: number;
  bedrooms?: number;
  sortOrder?: "price_ascending" | "price_descending";
};
export declare function filterAndSortProperties<T extends {
  city: string;
  area: string;
  purpose: string;
  bedrooms: number;
  price_pkr: number;
}>(properties: readonly T[], filters?: PropertyBrowseFilters): T[];
