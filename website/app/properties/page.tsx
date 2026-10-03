import Link from "next/link";
import { listings, catalogQuery, type SearchParams, CatalogError } from "@/lib/catalog";
import { metadata } from "@/lib/site";
import { SearchForm } from "@/components/SearchForm";
import { ListingCard } from "@/components/ListingCard";
import { Notice } from "@/components/Notice";
export const dynamic = "force-dynamic";
export async function generateMetadata({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  return { ...metadata("Find a property", "Browse company properties for sale and rent. Filter by location, type and price.", "/properties"), ...(Object.keys(params).length ? { robots: { index: false, follow: true } } : {}) };
}
export default async function PropertiesPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  let error: unknown;
  const result = await listings({ ...params, page_size: "12" }).catch((cause: unknown) => { error = cause; return null; });
  function pageHref(page: number): string { const query = catalogQuery(params); query.set("page", String(page)); return `/properties?${query}`; }
  return <section className="section container"><p className="eyebrow">The company catalog</p><h1>Find your next property</h1><SearchForm params={params} full />
    {!result ? <Notice error title={error instanceof CatalogError && error.status === 422 ? "Check your search filters" : "The property search is unavailable"}><p>{error instanceof CatalogError && error.status === 422 ? "Some filter values are invalid. Check your price ranges and search values, then try again." : "We could not retrieve listings. Please try again shortly or contact our team."}</p></Notice> : <>
      <p aria-live="polite">{result.pagination.total} {result.pagination.total === 1 ? "property" : "properties"} found</p>
      {result.data.length ? <div className="listing-grid">{result.data.map((property) => <ListingCard key={property.id} property={property} />)}</div> : <Notice title="No properties match this search"><p>Try a wider location or price range, or tell us what you are looking for.</p><Link className="text-link" href="/contact">Share your requirements</Link></Notice>}
      {result.pagination.total_pages > 1 && <nav className="pagination" aria-label="Search results pages">{result.pagination.page > 1 && <Link className="button secondary" href={pageHref(result.pagination.page - 1)}>Previous</Link>}<span>Page {result.pagination.page} of {result.pagination.total_pages}</span>{result.pagination.page < result.pagination.total_pages && <Link className="button secondary" href={pageHref(result.pagination.page + 1)}>Next</Link>}</nav>}
    </>}
  </section>;
}
