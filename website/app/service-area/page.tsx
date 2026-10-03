import Link from "next/link";
import { metadata } from "@/lib/site";
import { listings } from "@/lib/catalog";
import { ListingCard } from "@/components/ListingCard";
import { Notice } from "@/components/Notice";
export const dynamic = "force-dynamic";
export const generateMetadata = () => ({ ...metadata("Our service area", "See where Awaaz Estate currently offers company property listings and assistance.", "/service-area"), ...(!process.env.SERVICE_CITY ? { robots: { index: false, follow: true } } : {}) });
export default async function ServiceArea() {
  const city = process.env.SERVICE_CITY?.trim();
  const area = process.env.SERVICE_AREA?.trim();
  const catalog = city ? await listings({ city, ...(area ? { area } : {}), page_size: "6" }).catch(() => null) : null;
  return <section className="section container"><p className="eyebrow">Where we can help</p><h1>Our service area</h1>{city ? <><h2>{area ? `${area}, ${city}` : city}</h2><p>Explore our published company properties in this service area. Contact the team to confirm whether your specific location and requirements are covered.</p>{catalog?.data.length ? <div className="listing-grid">{catalog.data.map((property) => <ListingCard key={property.id} property={property} />)}</div> : <Notice title={catalog ? "No properties published here yet" : "Listings could not be loaded"} error={!catalog}><p>The team can help review your property requirements.</p></Notice>}<p style={{ marginTop: 24 }}><Link className="text-link" href={`/properties?city=${encodeURIComponent(city)}${area ? `&area=${encodeURIComponent(area)}` : ""}`}>Search this service area</Link></p></> : <Notice title="Our service area has not yet been published"><p>Contact the team to confirm whether we can help in your preferred city and area.</p><Link className="text-link" href="/contact">Share your requirements</Link></Notice>}</section>;
}
