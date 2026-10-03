import Link from "next/link";
import { notFound } from "next/navigation";
import { listing, CatalogError, photoUrl, confirmedDate } from "@/lib/catalog";
import { metadata, price, label } from "@/lib/site";
import { Notice } from "@/components/Notice";
import { InquiryForm } from "@/components/InquiryForm";
export const dynamic = "force-dynamic";
type Props = { params: Promise<{ slug: string }> };
export async function generateMetadata({ params }: Props) {
  const { slug } = await params;
  const property = await listing(slug).catch(() => null);
  return property ? metadata(property.title, `${property.property_type} in ${property.area}, ${property.city}. ${price(property.price_pkr)}. Availability: ${label(property.availability_status)}.`, `/properties/${encodeURIComponent(property.slug)}`) : { title: "Listing unavailable", robots: { index: false, follow: true } };
}
export default async function ListingPage({ params }: Props) {
  const { slug } = await params;
  let cause: unknown;
  const property = await listing(slug).catch((error: unknown) => { cause = error; return null; });
  if (!property) {
    if (cause instanceof CatalogError && cause.status === 404) notFound();
    return <section className="section container"><Notice error title="This listing could not be loaded"><p>The property service is temporarily unavailable. Please try again shortly.</p></Notice></section>;
  }
  const date = confirmedDate(property.availability_confirmed_at);
  const photos = [...property.photos].sort((a, b) => a.sort_order - b.sort_order).filter((photo) => photoUrl(photo.url));
  const active = property.availability_status === "available";
  return <section className="section container"><nav className="breadcrumbs" aria-label="Breadcrumb"><Link href="/">Home</Link><span>/</span><Link href="/properties">Properties</Link><span>/</span><span>{property.title}</span></nav>
    <div className="detail-heading"><span className="badge">{label(property.property_type)} · For {property.transaction_type}</span><h1>{property.title}</h1><p><Link href={`/areas/${encodeURIComponent(property.city)}/${encodeURIComponent(property.area)}`}>{property.area}, {property.city}</Link></p><p className="price">{price(property.price_pkr)}</p><p className="quiet">{property.transaction_type === "rent" ? "Confirm the rental period and charges with our team." : "Asking price. Confirm current terms with our team."}</p></div>
    <div className="gallery">{photos.length ? photos.slice(0, 6).map((photo, index) => <img key={`${photo.url}-${index}`} src={photoUrl(photo.url)} alt={photo.alt_text || property.title} width="580" height="320" loading={index === 0 ? "eager" : "lazy"} />) : <div className="no-photo">Property photographs have not been provided.</div>}</div>
    <div className="detail-layout"><div><dl className="fact-grid"><div><dt>Size</dt><dd>{property.size_sqft.toLocaleString("en-PK")} sq ft</dd></div><div><dt>Bedrooms</dt><dd>{property.bedrooms}</dd></div><div><dt>Bathrooms</dt><dd>{property.bathrooms ?? "Not provided"}</dd></div><div><dt>Property type</dt><dd>{label(property.property_type)}</dd></div><div><dt>Availability</dt><dd>{label(property.availability_status)}</dd></div><div><dt>Last confirmed</dt><dd>{date || "Not provided"}</dd></div></dl>
      <div className="detail-copy"><h2>About this property</h2><p style={{ whiteSpace: "pre-line" }}>{property.description || "Further property details have not been provided. Ask the team for more information."}</p><h2>Amenities</h2>{property.amenities.length ? <ul>{property.amenities.map((amenity) => <li key={amenity}>{amenity}</li>)}</ul> : <p>Amenities have not been provided.</p>}<h2>Information review</h2><p>{property.verification.status === "not_reviewed" ? "This listing has not been reviewed." : `Listing information ${label(property.verification.status)}${confirmedDate(property.verification.reviewed_at) ? ` on ${confirmedDate(property.verification.reviewed_at)}` : ""}.`}</p><p>{property.verification.scope || "No verification scope has been provided. Confirm ownership, approvals and documentation independently before a transaction."}</p>
        <Link className="button secondary" href={`/compare?slugs=${encodeURIComponent(property.slug)}`}>Compare this property</Link>
      </div></div>
      <aside><div className="inquiry-panel"><h2>{active ? "Interested in this property?" : "Ask about this property"}</h2><p>{active ? "Ask for more details or request a viewing. Our team will confirm the next steps." : "This property is not currently confirmed as available. Ask the team for updates or alternatives."}</p><InquiryForm listingId={property.id} listingTitle={property.title} /><p className="quiet" style={{ marginTop: 20 }}>Prefer a conversation? <Link href="/assistant">Ask Awaaz</Link>.</p></div></aside>
    </div>
  </section>;
}
