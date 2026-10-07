import type { MetadataRoute } from "next";
import { listings } from "@/lib/catalog";
import {agencies,agents,guides} from "@/lib/marketplace";
import { siteUrl } from "@/lib/site";
export const dynamic = "force-dynamic";
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const pages: MetadataRoute.Sitemap = ["", "/properties", "/about", "/contact", "/privacy", "/terms", "/areas", "/agents", "/sell"].map((path) => ({ url: `${siteUrl}${path}` }));
  // Avoid claiming timestamps or inventing listings when the backend is unavailable.
  try {
    const first = await listings({ page: "1", page_size: "100" });
    const found = [...first.data];
    for (let page = 2; page <= first.pagination.total_pages; page++) found.push(...(await listings({ page: String(page), page_size: "100" })).data);
    const [orgs,people,areas]=await Promise.all([agencies().catch(()=>[]),agents().catch(()=>[]),guides().catch(()=>[])]);
    const extra=[...orgs.map(o=>`/agencies/${o.slug}`),...people.map(p=>`/agents/${p.slug}`),...areas.flatMap(g=>[`/areas/${g.city_slug}/${g.area_slug}`,`/buy/${g.city_slug}/${g.area_slug}`,`/rent/${g.city_slug}/${g.area_slug}`])].map(path=>({url:`${siteUrl}${path}`}));
    return [...pages,...extra, ...found.map((property) => ({ url: `${siteUrl}/properties/${encodeURIComponent(property.slug)}` }))];
  } catch { return pages; }
}
