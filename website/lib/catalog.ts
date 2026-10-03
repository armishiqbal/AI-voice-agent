export type Photo = { url: string; alt_text: string; sort_order: number };
export type Listing = {
  id: string; slug: string; title: string; description: string;
  transaction_type: "sale" | "rent";
  property_type: "house" | "apartment" | "plot" | "shop" | "office" | "warehouse" | "other";
  city: string; area: string; price_pkr: number; bedrooms: number; bathrooms: number | null;
  size_sqft: number; amenities: string[]; photos: Photo[];
  availability_status: "available" | "needs_confirmation" | "unavailable" | "reserved" | "sold";
  availability_confirmed_at: string | null;
  verification: { status: "not_reviewed" | "reviewed" | "verified"; reviewed_at: string | null; scope: string | null };
  coordinates: { latitude: number; longitude: number } | null;
};
export type CatalogPage = { data: Listing[]; pagination: { page: number; page_size: number; total: number; total_pages: number } };
export type SearchParams = Record<string, string | string[] | undefined>;
export class CatalogError extends Error {
  constructor(message: string, public status = 502) { super(message); this.name = "CatalogError"; }
}
const backendUrl = (process.env.AWAAZ_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
export const scalar = (value: string | string[] | undefined): string => Array.isArray(value) ? value[0] || "" : value || "";
const allowedFilters = ["q", "transaction_type", "property_type", "city", "area", "min_price_pkr", "max_price_pkr", "bedrooms", "min_size_sqft", "max_size_sqft", "sort", "page", "page_size"];
export function catalogQuery(params: SearchParams): URLSearchParams {
  const query = new URLSearchParams();
  for (const key of allowedFilters) { const value = scalar(params[key]).trim(); if (value) query.set(key, value); }
  const amenities = params.amenities;
  for (const amenity of Array.isArray(amenities) ? amenities : amenities ? [amenities] : []) { if (amenity.trim()) query.append("amenities", amenity.trim()); }
  return query;
}
function object(value: unknown): value is Record<string, unknown> { return value !== null && typeof value === "object"; }
const nullableString = (value: unknown): boolean => value === null || typeof value === "string";
function isListing(value: unknown): value is Listing {
  if (!object(value)) return false;
  const texts = ["id", "slug", "title", "description", "city", "area"];
  if (!texts.every((key) => typeof value[key] === "string")) return false;
  if (!["sale", "rent"].includes(String(value.transaction_type)) || !["house", "apartment", "plot", "shop", "office", "warehouse", "other"].includes(String(value.property_type))) return false;
  if (!["price_pkr", "bedrooms", "size_sqft"].every((key) => typeof value[key] === "number" && Number.isFinite(value[key]))) return false;
  if (!(value.bathrooms === null || typeof value.bathrooms === "number")) return false;
  if (!Array.isArray(value.amenities) || !value.amenities.every((item) => typeof item === "string")) return false;
  if (!Array.isArray(value.photos) || !value.photos.every((photo) => object(photo) && typeof photo.url === "string" && typeof photo.alt_text === "string" && typeof photo.sort_order === "number")) return false;
  if (!["available", "needs_confirmation", "unavailable", "reserved", "sold"].includes(String(value.availability_status)) || !nullableString(value.availability_confirmed_at)) return false;
  if (!object(value.verification) || !["not_reviewed", "reviewed", "verified"].includes(String(value.verification.status)) || !nullableString(value.verification.reviewed_at) || !nullableString(value.verification.scope)) return false;
  return value.coordinates === null || (object(value.coordinates) && typeof value.coordinates.latitude === "number" && typeof value.coordinates.longitude === "number");
}
export async function apiJson(path: string, init?: RequestInit): Promise<unknown> {
  try {
    const response = await fetch(`${backendUrl}${path}`, { ...init, cache: "no-store", signal: AbortSignal.timeout(8000) });
    if (!response.ok) throw new CatalogError("The property service could not complete the request.", response.status);
    return await response.json();
  } catch (error) {
    if (error instanceof CatalogError) throw error;
    throw new CatalogError("The property service is temporarily unavailable.");
  }
}
export async function listings(params: SearchParams = {}): Promise<CatalogPage> {
  const value = await apiJson(`/v1/public/listings?${catalogQuery(params)}`);
  if (!object(value) || !Array.isArray(value.data) || !value.data.every(isListing) || !object(value.pagination)) throw new CatalogError("The property service returned an unexpected response.");
  const pagination = value.pagination;
  if (!["page", "page_size", "total", "total_pages"].every((key) => typeof pagination[key] === "number" && Number.isInteger(pagination[key]) && Number(pagination[key]) >= 0)) throw new CatalogError("The property service returned invalid pagination.");
  return { data: value.data, pagination: { page: Number(pagination.page), page_size: Number(pagination.page_size), total: Number(pagination.total), total_pages: Number(pagination.total_pages) } };
}
export async function listing(slug: string): Promise<Listing> {
  const value = await apiJson(`/v1/public/listings/${encodeURIComponent(slug)}`);
  if (!isListing(value)) throw new CatalogError("The property service returned an unexpected listing.");
  return value;
}
export function photoUrl(url: string): string | undefined {
  // Backend-approved relative media or HTTPS derivatives only; no inline/data URLs.
  if (url.startsWith("/") && !url.startsWith("//")) return url;
  try { const parsed = new URL(url); return parsed.protocol === "https:" ? parsed.toString() : undefined; } catch { return undefined; }
}
export function confirmedDate(value: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat("en-PK", { dateStyle: "medium", timeZone: "Asia/Karachi" }).format(date) : null;
}
