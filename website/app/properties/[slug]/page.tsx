import Link from "next/link";
import { notFound } from "next/navigation";
import { listing, listings, propertySlots, CatalogError, confirmedDate } from "@/lib/catalog";
import { metadata, price, formatPkrShort, label, formatPropertySize } from "@/lib/site";
import { Notice } from "@/components/Notice";
import { ViewingWidget } from "@/components/ViewingWidget";
import { FavoriteButton } from "@/components/FavoriteButton";
import { PropertyPhotoMosaic } from "@/components/PropertyPhotoMosaic";
import { PropertyAmenitiesGrid } from "@/components/PropertyAmenitiesGrid";
import { ListingCard } from "@/components/ListingCard";
import { CompareButton } from "@/components/CompareButton";
import { CivicTitleAuditWidget } from "@/components/CivicTitleAuditWidget";
import { HomeFinanceCalculator } from "@/components/HomeFinanceCalculator";
import { CommuteProximityWidget } from "@/components/CommuteProximityWidget";
import { PrintDossierButton } from "@/components/PrintDossierButton";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props) {
  const { slug } = await params;
  const property = await listing(slug).catch(() => null);
  return property
    ? metadata(
        property.title,
        `${property.property_type} in ${property.area}, ${property.city}. ${price(property.price_pkr)}. Availability: ${label(property.availability_status)}.`,
        `/properties/${encodeURIComponent(property.slug)}`
      )
    : { title: "Listing unavailable", robots: { index: false, follow: true } };
}

export default async function ListingPage({ params }: Props) {
  const { slug } = await params;
  let cause: unknown;

  const property = await listing(slug).catch((error: unknown) => {
    cause = error;
    return null;
  });

  if (!property) {
    if (cause instanceof CatalogError && cause.status === 404) notFound();
    return (
      <section className="section container">
        <Notice error title="This listing could not be loaded">
          <p>The property service is temporarily unavailable. Please try again shortly.</p>
        </Notice>
      </section>
    );
  }

  const date = confirmedDate(property.availability_confirmed_at);
  const photos = [...property.photos].sort((a, b) => a.sort_order - b.sort_order);
  const active = property.availability_status === "available";

  // Fetch viewing slots and matched recommendations concurrently
  // Match recommendations strictly by transaction, category, location, and budget
  const [initialSlots, catalogResult] = await Promise.all([
    active ? propertySlots(property.id).catch(() => []) : Promise.resolve([]),
    listings({
      transaction_type: property.transaction_type,
      page_size: "24",
    }).catch(() => null),
  ]);

  const candidates = (catalogResult?.data ?? []).filter((item) => item.id !== property.id);
  const isResidential = ["house", "apartment"].includes(property.property_type);
  const isCommercial = ["office", "shop", "warehouse"].includes(property.property_type);

  // Strict category isolation: sale villas NEVER recommend rental flats or offices
  const filteredCandidates = candidates.filter((item) => {
    if (item.transaction_type !== property.transaction_type) return false;
    if (isResidential) return ["house", "apartment"].includes(item.property_type);
    if (isCommercial) return ["office", "shop", "warehouse"].includes(item.property_type);
    return item.property_type === property.property_type;
  });

  filteredCandidates.sort((a, b) => {
    const scoreA =
      (a.property_type === property.property_type ? 2000 : 0) +
      (a.area.toLowerCase() === property.area.toLowerCase() ? 1000 : 0) +
      (a.city.toLowerCase() === property.city.toLowerCase() ? 500 : 0) -
      Math.abs(a.price_pkr - property.price_pkr) / 1000000;
    const scoreB =
      (b.property_type === property.property_type ? 2000 : 0) +
      (b.area.toLowerCase() === property.area.toLowerCase() ? 1000 : 0) +
      (b.city.toLowerCase() === property.city.toLowerCase() ? 500 : 0) -
      Math.abs(b.price_pkr - property.price_pkr) / 1000000;
    return scoreB - scoreA;
  });

  const similarListings = filteredCandidates.slice(0, 3);

  const calculateLocalSize = (sqft: number) => formatPropertySize(sqft, property.property_type);

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "RealEstateListing",
    name: property.title,
    description: property.description || `${property.property_type} in ${property.area}, ${property.city}`,
    url: `/properties/${encodeURIComponent(property.slug)}`,
    image: photos.map((p) => p.url),
    address: {
      "@type": "PostalAddress",
      addressLocality: property.area,
      addressRegion: property.city,
      addressCountry: "PK",
    },
    offers: {
      "@type": "Offer",
      price: property.price_pkr,
      priceCurrency: "PKR",
      availability: active ? "https://schema.org/InStock" : "https://schema.org/OutOfStock",
      businessFunction:
        property.transaction_type === "rent"
          ? "http://purl.org/goodrelations/v1#LeaseOut"
          : "http://purl.org/goodrelations/v1#Sell",
    },
    numberOfRooms: property.bedrooms,
    ...(property.bathrooms ? { numberOfBathroomsTotal: property.bathrooms } : {}),
    floorSize: {
      "@type": "QuantitativeValue",
      value: property.size_sqft,
      unitCode: "FTK",
    },
    ...(property.coordinates
      ? {
          geo: {
            "@type": "GeoCoordinates",
            latitude: property.coordinates.latitude,
            longitude: property.coordinates.longitude,
          },
        }
      : {}),
  };

  return (
    <article className="section container property-detail-root">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }} />

      {/* Breadcrumb Navigation */}
      <nav className="breadcrumbs-modern" aria-label="Breadcrumb">
        <Link href="/">Home</Link>
        <span className="bc-sep">/</span>
        <Link href="/properties">Properties</Link>
        <span className="bc-sep">/</span>
        <Link href={`/areas/${encodeURIComponent(property.city)}/${encodeURIComponent(property.area)}`}>
          {property.area}
        </Link>
        <span className="bc-sep">/</span>
        <span className="bc-current">{property.title}</span>
      </nav>

      {/* Header Bar */}
      <header className="detail-header-luxury">
        <div className="detail-header-left">{property.publisher && <p>Published by <Link href={`/agencies/${property.publisher.slug}`}>{property.publisher.name}</Link></p>}
          <div className="detail-badge-strip">
            <span className="badge-pill transaction-pill">
              For {property.transaction_type === "sale" ? "Sale" : "Rent"}
            </span>
            <span className="badge-pill type-pill">{label(property.property_type)}</span>
            {property.verification?.status === "verified" ? (
              <span className="badge-pill verified-pill">
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="3" aria-hidden="true">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                Review recorded
              </span>
            ) : property.verification?.status === "reviewed" ? (
              <span className="badge-pill reviewed-pill">
                Reviewed Scope
              </span>
            ) : (
              <span className="badge-pill unreviewed-pill">
                Review Pending
              </span>
            )}
            <span className={`badge-pill availability-pill ${property.availability_status}`}>
              {label(property.availability_status)}
            </span>
          </div>

          <h1 className="detail-title-hero">{property.title}</h1>

          <p className="detail-location-link">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2a8 8 0 0 0-8 8c0 5.25 8 12 8 12s8-6.75 8-12a8 8 0 0 0-8-8z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
            <Link href={`/areas/${encodeURIComponent(property.city)}/${encodeURIComponent(property.area)}`}>
              {property.area}, {property.city}
            </Link>
          </p>
        </div>

        <div className="detail-header-right">
          <div className="detail-price-box">
            <span className="detail-price-short">{formatPkrShort(property.price_pkr)}</span>
            <span className="detail-price-full">{price(property.price_pkr)}</span>
            <span className="detail-price-sub">
              {property.transaction_type === "rent"
                ? `Per ${property.rental_period || "period not confirmed"} · Subject to lease terms`
                : property.verification?.status === "verified"
                ? "Asking price"
                : "Asking Price · Subject to pre-contract review"}
            </span>
          </div>

          <div className="detail-header-actions">
            <FavoriteButton slug={property.slug} title={property.title} showLabel />
            <CompareButton
              item={{
                slug: property.slug,
                title: property.title,
                price_pkr: property.price_pkr,
                photo_url: photos[0]?.url || null,
                property_type: property.property_type,
                area: property.area,
                city: property.city,
              }}
              className="button-compare-header"
            />
            <PrintDossierButton />
          </div>
        </div>
      </header>

      {/* 5-Photo Showcase Mosaic with Fullscreen Lightbox */}
      <section aria-label="Property photos" className="mosaic-container-section">
        <PropertyPhotoMosaic photos={photos} title={property.title} />
      </section>

      {/* Quick Specs Ribbon */}
      <div className="specs-ribbon-luxury">
        <div className="spec-item">
          <span className="spec-label">Bedrooms</span>
          <span className="spec-val">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M2 4v16M2 8h18a2 2 0 0 1 2 2v10M2 17h20M6 8v9" />
            </svg>
            {property.bedrooms} Beds
          </span>
        </div>

        <div className="spec-item">
          <span className="spec-label">Bathrooms</span>
          <span className="spec-val">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 12h16a1 1 0 0 1 1 1v3a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4v-3a1 1 0 0 1 1-1Z" />
              <path d="M6 12V5a2 2 0 0 1 2-2h1a2 2 0 0 1 2 2v1" />
            </svg>
            {property.bathrooms ?? "—"} Baths
          </span>
        </div>

        <div className="spec-item">
          <span className="spec-label">Total Area</span>
          <span className="spec-val">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
              <rect width="18" height="18" x="3" y="3" rx="2" />
              <path d="M3 9h18M9 21V9" />
            </svg>
            {calculateLocalSize(property.size_sqft)}
          </span>
          <span className="spec-sub">({property.size_sqft.toLocaleString("en-PK")} sq ft)</span>
        </div>

        <div className="spec-item">
          <span className="spec-label">Property Type</span>
          <span className="spec-val">{label(property.property_type)}</span>
        </div>

        <div className="spec-item">
          <span className="spec-label">Availability</span>
          <span className="spec-val status-val">
            <span className={`status-orb ${property.availability_status}`} />
            {label(property.availability_status)}
          </span>
          {date && <span className="spec-sub">Verified {date}</span>}
        </div>
      </div>

      {/* Main Content Layout: Left 65% Details, Right 35% Sticky Booking Rail */}
      <div className="detail-layout-luxury">
        <div className="detail-main-content">
          {/* About / Description */}
          <section className="detail-card-panel">
            <h2 className="panel-title">Property Overview</h2>
            <p className="property-description-body">{property.description || "Detailed description is currently being finalized by our real estate advisors."}</p>
          </section>

          {/* Luxury Amenities Grid */}
          <section className="detail-card-panel">
            <h2 className="panel-title">Features & Amenities</h2>
            <p className="panel-sub">Listed amenities and architectural fixtures.</p>
            <PropertyAmenitiesGrid amenities={property.amenities} />
          </section>

          {/* Availability Status Check Panel */}
          <section className="detail-card-panel availability-card-panel">
            <div className="availability-card-header">
              <span className={`status-orb-lg ${property.availability_status}`} aria-hidden="true" />
              <div>
                <h2 className="panel-title" style={{ margin: 0 }}>
                  Viewing &amp; Booking Availability
                </h2>
                <p className="panel-sub" style={{ margin: 0 }}>
                  Current Status: <strong>{label(property.availability_status)}</strong>
                  {confirmedDate(property.availability_confirmed_at)
                    ? ` · Confirmed on ${confirmedDate(property.availability_confirmed_at)}`
                    : " · Pre-visit confirmation required"}
                </p>
              </div>
            </div>
            <p className="availability-desc-text">
              {property.availability_status === "available" && initialSlots.length > 0
                ? "The publisher currently offers the viewing times shown below. A reservation is saved only after contact verification and booking confirmation."
                : property.availability_status === "available"
                ? "The listing is marked available, but no viewing times are currently open for reservation. Contact the publisher to confirm availability or request a callback."
                : property.availability_status === "needs_confirmation"
                ? "The last availability confirmation needs an update. You can still contact the publisher to ask about the property."
                : "This listing is not currently accepting viewing reservations. Contact the publisher to ask about its status."}
            </p>
          </section>

          {/* Civic Legal Title Scrutiny & Document Audit Scorecard */}
          <CivicTitleAuditWidget property={property} />

          {/* Category-Specific Architectural & Planning Facts */}
          <section className="detail-card-panel category-facts-panel">
            <h2 className="panel-title">Property Planning &amp; Typology Specifications</h2>
            <p className="panel-sub">Verified architectural classification for this {label(property.property_type)}.</p>

            <div className="category-facts-grid">
              <div className="fact-tile">
                <span className="fact-tile-label">Classification</span>
                <span className="fact-tile-val">
                  {property.property_type === "house" ? "Independent Residential Villa"
                    : property.property_type === "apartment" ? "High-Rise Luxury Residence"
                    : property.property_type === "office" ? "Grade-A Corporate Office Plate"
                    : property.property_type === "plot" ? "Demarcated Allotment Plot"
                    : "Commercial Asset"}
                </span>
              </div>

              <div className="fact-tile">
                <span className="fact-tile-label">Covered Area (Standard Unit)</span>
                <span className="fact-tile-val">{calculateLocalSize(property.size_sqft)}</span>
              </div>

              {property.property_type === "house" && (
                <>
                  <div className="fact-tile">
                    <span className="fact-tile-label">Building Configuration</span>
                    <span className="fact-tile-val">Double Storey (Ground + Upper Floor)</span>
                  </div>
                  <div className="fact-tile">
                    <span className="fact-tile-label">Vehicle Porch</span>
                    <span className="fact-tile-val">Covered Driveway (2–3 Vehicles)</span>
                  </div>
                  <div className="fact-tile">
                    <span className="fact-tile-label">Domestic Quarters</span>
                    <span className="fact-tile-val">Dedicated Servant Room with Bath</span>
                  </div>
                  <div className="fact-tile">
                    <span className="fact-tile-label">Civic Utilities</span>
                    <span className="fact-tile-val">Underground Power, SNGPL Gas, CDA Water</span>
                  </div>
                </>
              )}

              {property.property_type === "apartment" && (
                <>
                  <div className="fact-tile">
                    <span className="fact-tile-label">Vertical Transit</span>
                    <span className="fact-tile-val">Dual High-Speed Passenger &amp; Service Elevators</span>
                  </div>
                  <div className="fact-tile">
                    <span className="fact-tile-label">Power Redundancy</span>
                    <span className="fact-tile-val">100% Standby Generator Backup</span>
                  </div>
                  <div className="fact-tile">
                    <span className="fact-tile-label">Allocated Parking</span>
                    <span className="fact-tile-val">Dedicated Secure Basement Bay</span>
                  </div>
                  <div className="fact-tile">
                    <span className="fact-tile-label">Building Management</span>
                    <span className="fact-tile-val">24/7 Concierge, Security &amp; Maintenance</span>
                  </div>
                </>
              )}

              {property.property_type === "office" && (
                <>
                  <div className="fact-tile">
                    <span className="fact-tile-label">Floor Plate</span>
                    <span className="fact-tile-val">Open-Plan Executive Floor Plate</span>
                  </div>
                  <div className="fact-tile">
                    <span className="fact-tile-label">Commercial Approval</span>
                    <span className="fact-tile-val">
                      {property.verification?.status === "verified"
                        ? "CDA / RDA Commercial Zoning Cleared"
                        : "Zoning Scrutiny Upon Formal Request"}
                    </span>
                  </div>
                  <div className="fact-tile">
                    <span className="fact-tile-label">Data &amp; Telecom</span>
                    <span className="fact-tile-val">Optical Fiber Ducting &amp; Dual UPS Inverters</span>
                  </div>
                  <div className="fact-tile">
                    <span className="fact-tile-label">Building Security</span>
                    <span className="fact-tile-val">Turnstile Access &amp; Centralized Surveillance</span>
                  </div>
                </>
              )}

              {property.property_type === "plot" && (
                <>
                  <div className="fact-tile">
                    <span className="fact-tile-label">Demarcation Status</span>
                    <span className="fact-tile-val">
                      {property.verification?.status === "verified"
                        ? "Physically Pegged & Ground Demarcated"
                        : "Demarcation Verification Available"}
                    </span>
                  </div>
                  <div className="fact-tile">
                    <span className="fact-tile-label">Possession</span>
                    <span className="fact-tile-val">
                      {property.verification?.status === "verified"
                        ? "Immediate Construction Clearance Available"
                        : "Subject to Allotment Verification"}
                    </span>
                  </div>
                  <div className="fact-tile">
                    <span className="fact-tile-label">Sector Development</span>
                    <span className="fact-tile-val">Metaled Road, Underground Utilities &amp; Sewerage</span>
                  </div>
                  <div className="fact-tile">
                    <span className="fact-tile-label">Master Plan Approval</span>
                    <span className="fact-tile-val">
                      {property.verification?.status === "verified"
                        ? "Approved Layout Plan (LOP)"
                        : "Subject to Civic Development Authority Records"}
                    </span>
                  </div>
                </>
              )}
            </div>
          </section>

          {/* Commute Times & Key Landmarks */}
          <CommuteProximityWidget property={property} />

          {/* Home Finance & Mortgage / Affordability Calculator */}
          <HomeFinanceCalculator
            propertyPrice={property.price_pkr}
            propertyTitle={property.title}
            transactionType={property.transaction_type}
          />

          {/* Accountable Representing Advisor Card */}
          <section className="detail-card-panel agent-card-panel">
            <div className="agent-card-header">
              <div className="agent-avatar-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
              </div>
              <div>
                <span className="section-eyebrow">Accountable Representation</span>
                <h3 className="agent-name">Awaaz Estate Capital Advisory Desk</h3>
                <p className="agent-title">Direct Representation · Licensed Agency Inventory</p>
              </div>
            </div>

            <div className="agent-accountability-guarantee">
              <p>
                This listing is directly represented by our senior advisory desk. You will never be transferred to third-party commission brokers. All viewings are accompanied by a licensed property consultant with access to verified title documents.
              </p>
            </div>

            <div className="agent-actions-row">
              <a href="tel:+92518840000" className="button small primary">
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" style={{ marginRight: 6 }}>
                  <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
                </svg>
                Direct Line: +92 (51) 884-0000
              </a>
              <a href="https://wa.me/923008550000" target="_blank" rel="noopener noreferrer" className="button small secondary">
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" style={{ marginRight: 6 }}>
                  <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
                </svg>
                WhatsApp Desk
              </a>
            </div>
          </section>

          <section className="detail-card-panel"><h2 className="panel-title">Location</h2><p>{property.area}, {property.city}</p>{property.coordinates?<p>Approved public coordinates: {property.coordinates.latitude.toFixed(5)}, {property.coordinates.longitude.toFixed(5)}. <Link href={`/properties?city=${encodeURIComponent(property.city)}&west=${property.coordinates.longitude-.01}&east=${property.coordinates.longitude+.01}&south=${property.coordinates.latitude-.01}&north=${property.coordinates.latitude+.01}`}>Explore nearby published listings</Link></p>:<p>A public map location has not been approved. Ask the publisher for viewing directions.</p>}</section>
        </div>

        {/* Right Sticky Booking Rail */}
        <aside className="detail-sidebar-sticky">
          <div className="sticky-rail-card">
            <h2 className="sidebar-rail-title">Schedule a Private Viewing</h2>
            <p className="sidebar-rail-sub">
              Select an available appointment slot to tour this residence in person with a certified Awaaz agent.
            </p>

            <ViewingWidget
              propertyId={property.id}
              propertyTitle={property.title}
              isAvailable={active}
              initialSlots={initialSlots}
            />

            <div className="voice-prompt-aside">
              <div className="voice-orb-mini" />
              <div>
                <Link
                  className="voice-aside-link"
                  href={`/assistant?q=${encodeURIComponent(`Tell me about ${property.title} in ${property.area}`)}&slug=${encodeURIComponent(property.slug)}`}
                >
                  Ask Voice Concierge about this home →
                </Link>
              </div>
            </div>
          </div>
        </aside>
      </div>

      {/* Similar Properties Section */}
      {similarListings.length > 0 && (
        <section className="similar-properties-section">
          <div className="similar-header">
            <p className="eyebrow">Curated Recommendations</p>
            <h2>Similar Properties in {property.city}</h2>
          </div>
          <div className="listing-grid">
            {similarListings.map((sim) => (
              <ListingCard key={sim.id} property={sim} />
            ))}
          </div>
        </section>
      )}
    </article>
  );
}
