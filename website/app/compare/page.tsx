import Link from "next/link";
import { listing, listings, scalar, type Listing, type SearchParams } from "@/lib/catalog";
import { metadata, price, label } from "@/lib/site";
import { Notice } from "@/components/Notice";
export const dynamic = "force-dynamic";
export const generateMetadata = () => ({ ...metadata("Compare properties", "Compare property prices, sizes and availability before contacting our team.", "/compare"), robots: { index: false, follow: true } });
export default async function Compare({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const raw = params.slugs;
  const slugs = [...new Set((Array.isArray(raw) ? raw : scalar(raw).split(",")).filter(Boolean))].slice(0, 3);
  const [options, selected] = await Promise.all([listings({ page_size: "100" }).catch(() => null), Promise.all(slugs.map((slug) => listing(slug).catch(() => null)))]);
  const properties = selected.filter((value): value is Listing => value !== null);
  const choices = [...new Map([...(options?.data || []), ...properties].map((property) => [property.slug, property])).values()];
  return <section className="section container"><p className="eyebrow">Your shortlist</p><h1>Compare properties</h1><p>Choose up to three listings. Compare the facts, then ask the team about your preferred option.</p>
    <form className="search-form" method="get" action="/compare">{[0, 1, 2].map((index) => <label key={index}>Property {index + 1}<select name="slugs" defaultValue={slugs[index] || ""}><option value="">Choose a property</option>{choices.map((property) => <option key={property.id} value={property.slug}>{property.title}</option>)}</select></label>)}<button className="button" type="submit">Compare</button></form>
    {selected.some((item) => item === null) && <p role="alert">One or more selected properties could not be loaded. Only retrieved facts are shown.</p>}
    {properties.length ? <div className="comparison-wrap" style={{ marginTop: 30 }}><table><caption className="quiet">Property comparison using current catalog information</caption><thead><tr><th scope="col">Details</th>{properties.map((property) => <th scope="col" key={property.id}><Link href={`/properties/${encodeURIComponent(property.slug)}`}>{property.title}</Link></th>)}</tr></thead><tbody>{[
      { title: "Asking price", value: (property: Listing) => price(property.price_pkr) },
      { title: "Purpose", value: (property: Listing) => property.transaction_type },
      { title: "Location", value: (property: Listing) => `${property.area}, ${property.city}` },
      { title: "Property type", value: (property: Listing) => label(property.property_type) },
      { title: "Size", value: (property: Listing) => `${property.size_sqft.toLocaleString("en-PK")} sq ft` },
      { title: "Bedrooms", value: (property: Listing) => String(property.bedrooms) },
      { title: "Bathrooms", value: (property: Listing) => String(property.bathrooms ?? "Not provided") },
      { title: "Availability", value: (property: Listing) => label(property.availability_status) },
    ].map((row) => <tr key={row.title}><th scope="row">{row.title}</th>{properties.map((property) => <td key={property.id}>{row.value(property)}</td>)}</tr>)}</tbody></table></div> : <div style={{ marginTop: 30 }}><Notice title={choices.length ? "Build your comparison" : "No properties are available to compare"}><p>{choices.length ? "Select two or three properties above to see their details together." : "Return once company listings are published, or contact us with your requirements."}</p></Notice></div>}
  </section>;
}
