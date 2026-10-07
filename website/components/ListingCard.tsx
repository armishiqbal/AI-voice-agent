import Link from "next/link";
import { photoUrl, confirmedDate, type Listing } from "@/lib/catalog";
import { formatPkrShort, price, label, formatPropertySize } from "@/lib/site";
import { FavoriteButton } from "@/components/FavoriteButton";
import { CompareButton } from "@/components/CompareButton";

export function ListingCard({ property }: { property: Listing }) {
  const photo = [...property.photos].sort((a, b) => a.sort_order - b.sort_order).find((item) => photoUrl(item.url));
  const date = confirmedDate(property.availability_confirmed_at);
  const isReviewed = property.verification?.status === "reviewed" || property.verification?.status === "verified";

  return (
    <article className="listing-card modern-card">
      <div className="listing-image-wrap">
        <Link className="listing-image" href={`/properties/${encodeURIComponent(property.slug)}`} aria-label={`View ${property.title}`}>
          {photo ? (
            <img src={photoUrl(photo.url)} alt={photo.alt_text || property.title} loading="lazy" width="400" height="250" />
          ) : (
            <span className="no-photo">Property photos not provided</span>
          )}

          {/* Status & Verification Badges */}
          <div className="card-badge-row">
            <span className="badge-pill transaction-badge">
              For {property.transaction_type === "sale" ? "Sale" : "Rent"}
            </span>
            {isReviewed && (
              <span className="badge-pill verified-badge">
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="3" style={{ marginRight: 4 }}>
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                Review recorded
              </span>
            )}
          </div>
        </Link>

        {/* Favorite Button */}
        <FavoriteButton slug={property.slug} title={property.title} className="card-favorite-btn" />
      </div>

      <div className="listing-body">
        <div className="price-header">
          <p className="price-primary">
            {formatPkrShort(property.price_pkr)}
            {property.transaction_type === "rent" ? (
              <span className="price-period"> / {property.rental_period || "mo"}</span>
            ) : null}
          </p>
          <span className="price-full">{price(property.price_pkr)}</span>
        </div>

        {property.publisher && (
          <Link href={`/agencies/${encodeURIComponent(property.publisher.slug)}`} className="card-agency-pill">
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
            <span>{property.publisher.name}</span>
          </Link>
        )}

        <h3 className="card-title">
          <Link href={`/properties/${encodeURIComponent(property.slug)}`}>{property.title}</Link>
        </h3>

        <p className="card-location">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" style={{ marginRight: 6, flexShrink: 0 }}>
            <path d="M12 2a8 8 0 0 0-8 8c0 5.25 8 12 8 12s8-6.75 8-12a8 8 0 0 0-8-8z" />
            <circle cx="12" cy="10" r="3" />
          </svg>
          <span>{property.area}, {property.city}</span>
        </p>

        {/* Modern Specifications Chips */}
        <div className="card-specs">
          <div className="spec-chip" title="Bedrooms">
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M2 4v16M2 8h18a2 2 0 0 1 2 2v10M2 17h20M6 8v9" />
            </svg>
            <span>{property.bedrooms} Beds</span>
          </div>

          <div className="spec-chip" title="Bathrooms">
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 12h16a1 1 0 0 1 1 1v3a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4v-3a1 1 0 0 1 1-1Z" />
              <path d="M6 12V5a2 2 0 0 1 2-2h1a2 2 0 0 1 2 2v1" />
            </svg>
            <span>{property.bathrooms ?? "—"} Baths</span>
          </div>

          <div className="spec-chip" title="Property Size">
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2">
              <rect width="18" height="18" x="3" y="3" rx="2" />
              <path d="M3 9h18M9 21V9" />
            </svg>
            <span>{formatPropertySize(property.size_sqft, property.property_type, property.sqft_per_marla)}</span>
          </div>
        </div>

        <p className="card-confirmed-status">
          <span className="status-dot available" />
          {label(property.availability_status)} {date ? `· Confirmed ${date}` : ""}
        </p>

        <div className="card-actions-modern">
          <Link className="card-primary-action" href={`/properties/${encodeURIComponent(property.slug)}`}>
            Explore Details →
          </Link>
          <CompareButton
            item={{
              slug: property.slug,
              title: property.title,
              price_pkr: property.price_pkr,
              photo_url: photo?.url || null,
              property_type: property.property_type,
              area: property.area,
              city: property.city,
            }}
          />
        </div>
      </div>
    </article>
  );
}
