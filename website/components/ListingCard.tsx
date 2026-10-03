import Link from "next/link";
import { photoUrl, confirmedDate, type Listing } from "@/lib/catalog";
import { price, label } from "@/lib/site";
export function ListingCard({ property }: { property: Listing }) {
  const photo = [...property.photos].sort((a, b) => a.sort_order - b.sort_order).find((item) => photoUrl(item.url));
  const date = confirmedDate(property.availability_confirmed_at);
  return <article className="listing-card">
    <Link className="listing-image" href={`/properties/${encodeURIComponent(property.slug)}`} aria-label={`View ${property.title}`}>
      {photo ? <img src={photoUrl(photo.url)} alt={photo.alt_text || property.title} loading="lazy" width="400" height="225" /> : <span className="no-photo">Property photos not provided</span>}
      <span className="badge">For {property.transaction_type === "sale" ? "sale" : "rent"}</span>
    </Link>
    <div className="listing-body"><p className="price">{price(property.price_pkr)}</p><h3><Link href={`/properties/${encodeURIComponent(property.slug)}`}>{property.title}</Link></h3><p className="location">{property.area}, {property.city}</p>
      <div className="facts"><span>{label(property.property_type)}</span><span>{property.bedrooms} bedrooms</span><span>{property.size_sqft.toLocaleString("en-PK")} sq ft</span></div>
      <p className="quiet">{label(property.availability_status)}{date ? ` · Confirmed ${date}` : " · Confirmation date not provided"}</p>
      <div className="card-actions"><Link className="text-link" href={`/properties/${encodeURIComponent(property.slug)}`}>View details →</Link><Link className="text-link" href={`/compare?slugs=${encodeURIComponent(property.slug)}`}>Compare</Link></div>
    </div>
  </article>;
}
