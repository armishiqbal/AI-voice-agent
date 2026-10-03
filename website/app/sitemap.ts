import type { MetadataRoute } from "next";
import { listings } from "@/lib/catalog";
import { siteUrl } from "@/lib/site";
export const dynamic = "force-dynamic";
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const pages: MetadataRoute.Sitemap = ["", "/properties", "/about", "/contact", "/privacy", "/terms"].map((path) => ({ url: `${siteUrl}${path}` }));
  // Avoid claiming timestamps or inventing listings when the backend is unavailable.
  try {
    const first = await listings({ page: "1", page_size: "100" });
    const found = [...first.data];
    for (let page = 2; page <= first.pagination.total_pages; page++) found.push(...(await listings({ page: String(page), page_size: "100" })).data);
    return [...pages, ...found.map((property) => ({ url: `${siteUrl}/properties/${encodeURIComponent(property.slug)}` }))];
  } catch { return pages; }
}
