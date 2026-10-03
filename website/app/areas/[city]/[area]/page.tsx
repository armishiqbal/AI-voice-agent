import Link from "next/link";
import { listings } from "@/lib/catalog";
import { metadata } from "@/lib/site";
import { Notice } from "@/components/Notice";
import { ListingCard } from "@/components/ListingCard";
export const dynamic = "force-dynamic";
type Props = { params: Promise<{ city: string; area: string }> };
export async function generateMetadata({ params }: Props) { const { city, area } = await params; return { ...metadata(`Properties in ${area}, ${city}`, `Explore published company listings in ${area}, ${city}.`, `/areas/${encodeURIComponent(city)}/${encodeURIComponent(area)}`), robots: { index: false, follow: true } }; }
export default async function Area({ params }: Props) {
  const { city, area } = await params;
  const catalog = await listings({ city, area, page_size: "12" }).catch(() => null);
  return <section className="section container"><nav className="breadcrumbs" aria-label="Breadcrumb"><Link href="/">Home</Link><span>/</span><Link href="/properties">Properties</Link><span>/</span><span>{area}</span></nav><p className="eyebrow">Explore by location</p><h1>{area}, {city}</h1><p>Published company listings for this area. Ask the team to confirm local amenities, access and property details.</p><p className="quiet">A reviewed area guide has not yet been published.</p>
    {catalog?.data.length ? <div className="listing-grid">{catalog.data.map((property) => <ListingCard key={property.id} property={property} />)}</div> : <Notice error={!catalog} title={catalog ? "No published listings in this area" : "Area listings could not be loaded"}><p>{catalog ? "Tell us your requirements or browse the full company catalog." : "The property service is temporarily unavailable."}</p><Link className="text-link" href="/contact">Contact our team</Link></Notice>}
    {catalog && catalog.pagination.total > 12 && <p style={{ marginTop: 24 }}><Link className="text-link" href={`/properties?city=${encodeURIComponent(city)}&area=${encodeURIComponent(area)}`}>View all properties in this area</Link></p>}
  </section>;
}
