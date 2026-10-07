"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type Listing, photoUrl } from "@/lib/catalog";
import { price, formatPkrShort, label, formatPropertySize } from "@/lib/site";
import { FavoriteButton } from "@/components/FavoriteButton";
import { getStoredCompare, setStoredCompare, removeFromCompare, type CompareItem } from "@/lib/compare";

interface PropertyComparisonMatrixProps {
  properties: Listing[];
  choices: Listing[];
}

export function PropertyComparisonMatrix({ properties, choices }: PropertyComparisonMatrixProps) {
  const router = useRouter();
  const [highlightDiff, setHighlightDiff] = useState(false);

  const slugs = properties.map((p) => p.slug);

  // Synchronize matrix properties with the persistent comparison tray
  useEffect(() => {
    if (properties.length > 0) {
      const items: CompareItem[] = properties.map((p) => ({
        slug: p.slug,
        title: p.title,
        price_pkr: p.price_pkr,
        photo_url: p.photos[0]?.url || null,
        property_type: p.property_type,
        area: p.area,
        city: p.city,
      }));
      setStoredCompare(items);
    }
  }, [properties]);

  const updateComparison = (newSlugs: string[]) => {
    const valid = newSlugs.filter(Boolean);
    if (valid.length === 0) {
      router.push("/compare");
    } else {
      router.push(`/compare?slugs=${valid.map(encodeURIComponent).join(",")}`);
    }
  };

  const removeProperty = (slugToRemove: string) => {
    removeFromCompare(slugToRemove);
    updateComparison(slugs.filter((s) => s !== slugToRemove));
  };

  const addProperty = (slugToAdd: string) => {
    if (!slugToAdd || slugs.includes(slugToAdd) || slugs.length >= 3) return;
    const choice = choices.find((c) => c.slug === slugToAdd);
    if (choice) {
      const current = getStoredCompare();
      if (!current.some((c) => c.slug === slugToAdd) && current.length < 3) {
        setStoredCompare([
          ...current,
          {
            slug: choice.slug,
            title: choice.title,
            price_pkr: choice.price_pkr,
            photo_url: choice.photos[0]?.url || null,
            property_type: choice.property_type,
            area: choice.area,
            city: choice.city,
          },
        ]);
      }
    }
    updateComparison([...slugs, slugToAdd]);
  };

  const changePropertyAt = (index: number, newSlug: string) => {
    const updated = [...slugs];
    if (newSlug) {
      updated[index] = newSlug;
    } else {
      removeFromCompare(updated[index]);
      updated.splice(index, 1);
    }
    updateComparison(updated);
  };

  // Common amenities to compare
  const popularAmenities = [
    { key: "parking", label: "Covered Parking / Garage" },
    { key: "generator", label: "Backup Generator / Solar" },
    { key: "security", label: "24/7 Gated Security" },
    { key: "lawn", label: "Lawn / Garden" },
    { key: "pool", label: "Swimming Pool" },
    { key: "cooling", label: "Central HVAC / AC" },
  ];

  // Helper to test if a row differs across properties
  const isRowDifferent = (getValue: (p: Listing) => string | number | boolean) => {
    if (properties.length <= 1) return false;
    const firstVal = getValue(properties[0]);
    return properties.some((p) => getValue(p) !== firstVal);
  };

  // Data rows
  const specRows = [
    {title:"Publisher",getValue:(p:Listing)=>p.publisher?.name||"Not provided",render:(p:Listing)=><span>{p.publisher?.name||"Not provided"}</span>},
    {title:"Monthly rental equivalent",getValue:(p:Listing)=>p.transaction_type==="rent"?p.price_pkr/(p.rental_period==="yearly"?12:1):"Not a rental",render:(p:Listing)=><span>{p.transaction_type==="rent"?price(p.price_pkr/(p.rental_period==="yearly"?12:1)):"Not a rental"}</span>},
    {
      title: "Asking Price",
      getValue: (p: Listing) => formatPkrShort(p.price_pkr),
      render: (p: Listing) => (
        <div>
          <strong className="matrix-price-primary">{formatPkrShort(p.price_pkr)}</strong>
          <span className="matrix-price-sub">{price(p.price_pkr)}{p.transaction_type==="rent"?` / ${p.rental_period||"period not confirmed"}`:""}</span>
        </div>
      ),
    },
    {
      title: "Purpose",
      getValue: (p: Listing) => p.transaction_type,
      render: (p: Listing) => (
        <span className="badge-pill transaction-pill">For {p.transaction_type === "sale" ? "Sale" : "Rent"}</span>
      ),
    },
    {
      title: "Location / Sector",
      getValue: (p: Listing) => `${p.area}, ${p.city}`,
      render: (p: Listing) => <span>{p.area}, {p.city}</span>,
    },
    {
      title: "Property Type",
      getValue: (p: Listing) => p.property_type,
      render: (p: Listing) => <span>{label(p.property_type)}</span>,
    },
    {
      title: "Size / Area",
      getValue: (p: Listing) => p.size_sqft,
      render: (p: Listing) => <span>{formatPropertySize(p.size_sqft,p.property_type,p.sqft_per_marla)}</span>,
    },
    {
      title: "Price per sq ft",
      getValue: (p: Listing) => Math.round(p.price_pkr / (p.size_sqft || 1)),
      render: (p: Listing) => (
        <span>Rs. {Math.round(p.price_pkr / (p.size_sqft || 1)).toLocaleString("en-PK")} / sq ft</span>
      ),
    },
    {
      title: "Bedrooms",
      getValue: (p: Listing) => p.bedrooms,
      render: (p: Listing) => <span>{p.bedrooms} Beds</span>,
    },
    {
      title: "Bathrooms",
      getValue: (p: Listing) => p.bathrooms ?? 0,
      render: (p: Listing) => <span>{p.bathrooms ? `${p.bathrooms} Baths` : "Not provided"}</span>,
    },
    {
      title: "Availability Status",
      getValue: (p: Listing) => p.availability_status,
      render: (p: Listing) => (
        <span className={`status-chip-matrix ${p.availability_status}`}>
          {label(p.availability_status)}
        </span>
      ),
    },
    {
      title: "Review scope",
      getValue: (p: Listing) => p.verification.status,
      render: (p: Listing) => (
        <span className={`verification-chip-matrix ${p.verification.status}`}>
          {p.verification.status === "verified" ? (
            <>
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ display: "inline-block", verticalAlign: "middle", marginRight: 4 }}>
                <polyline points="20 6 9 17 4 12" />
              </svg>
              {p.verification.scope || "Review recorded"}
            </>
          ) : (
            label(p.verification.status)
          )}
        </span>
      ),
    },
  ];

  return (
    <div className="comparison-matrix-wrapper">
      {/* Top Selector & Controls Bar */}
      <div className="matrix-toolbar">
        <div className="matrix-selectors-row">
          {[0, 1, 2].map((idx) => {
            const currentSlug = slugs[idx] || "";
            return (
              <div key={idx} className="matrix-selector-cell">
                <label className="selector-label">Property {idx + 1}</label>
                <div className="selector-select-wrap">
                  <select
                    value={currentSlug}
                    onChange={(e) => changePropertyAt(idx, e.target.value)}
                    className="selector-dropdown"
                  >
                    <option value="">{currentSlug ? "Remove Property" : "Select to compare..."}</option>
                    {choices.map((choice) => (
                      <option
                        key={choice.id}
                        value={choice.slug}
                        disabled={slugs.includes(choice.slug) && choice.slug !== currentSlug}
                      >
                        {choice.title} ({choice.area})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            );
          })}
        </div>

        {/* Highlight Differences Toggle */}
        {properties.length > 1 && (
          <div className="matrix-controls-row">
            <button
              type="button"
              className={`toggle-diff-btn ${highlightDiff ? "active" : ""}`}
              onClick={() => setHighlightDiff(!highlightDiff)}
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 2a10 10 0 0 1 0 20v-20z" />
              </svg>
              <span>{highlightDiff ? "Differences Highlighted" : "Highlight Differences"}</span>
            </button>
            <span className="diff-hint-text">
              {highlightDiff ? "Showing highlighted variations across properties" : "Click to spotlight differing specs"}
            </span>
          </div>
        )}
      </div>

      {properties.length === 0 ? (
        <div className="empty-matrix-placeholder">
          <p>Please select at least one property above to inspect features and specifications.</p>
        </div>
      ) : (
        <div className="matrix-table-container">
          <table className="matrix-table">
            <thead>
              {/* Sticky Property Cards Header */}
              <tr className="sticky-header-row">
                <th className="feature-col-header">
                  <span className="feature-header-text">Property Details</span>
                </th>
                {properties.map((property) => {
                  const photo = [...property.photos].sort((a, b) => a.sort_order - b.sort_order).find((p) => photoUrl(p.url));
                  const validUrl = photo ? photoUrl(photo.url) : null;

                  return (
                    <th key={property.id} className="property-card-col">
                      <div className="matrix-card-head">
                        <button
                          type="button"
                          className="remove-col-btn"
                          onClick={() => removeProperty(property.slug)}
                          title="Remove from comparison"
                          aria-label={`Remove ${property.title}`}
                        >
                          ×
                        </button>

                        <div className="matrix-thumb-wrap">
                          {validUrl ? (
                            <img
                              src={validUrl}
                              alt={photo?.alt_text || property.title}
                              className="matrix-thumb-img"
                            />
                          ) : (
                            <div className="matrix-no-thumb">No photo</div>
                          )}
                          <FavoriteButton slug={property.slug} title={property.title} className="matrix-fav-btn" />
                        </div>

                        <h3 className="matrix-card-title">
                          <Link href={`/properties/${encodeURIComponent(property.slug)}`}>
                            {property.title}
                          </Link>
                        </h3>

                        <p className="matrix-card-price">{formatPkrShort(property.price_pkr)}</p>
                        <p className="matrix-card-loc">{property.area}, {property.city}</p>

                        <Link
                          className="button primary small view-home-btn"
                          href={`/properties/${encodeURIComponent(property.slug)}`}
                        >
                          View Home
                        </Link>
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>

            <tbody>
              {/* Specification Rows */}
              {specRows.map((row) => {
                const isDiff = isRowDifferent(row.getValue);
                const rowClass = highlightDiff ? (isDiff ? "row-diff-highlight" : "row-diff-dim") : "";

                return (
                  <tr key={row.title} className={rowClass}>
                    <th scope="row" className="feature-row-label">
                      {row.title}
                      {highlightDiff && isDiff && <span className="diff-pill-dot" title="Differs" />}
                    </th>
                    {properties.map((property) => (
                      <td key={property.id} className="matrix-cell">
                        {row.render(property)}
                      </td>
                    ))}
                  </tr>
                );
              })}

              {/* Amenity Comparison Section Header */}
              <tr className="matrix-section-divider">
                <th colSpan={properties.length + 1}>
                  <span>Key Infrastructure & Amenities</span>
                </th>
              </tr>

              {/* Amenity Rows */}
              {popularAmenities.map((amenity) => {
                const hasAmenity = (prop: Listing) =>
                  prop.amenities.some((a) => a.toLowerCase().includes(amenity.key));

                const isDiff = isRowDifferent(hasAmenity);
                const rowClass = highlightDiff ? (isDiff ? "row-diff-highlight" : "row-diff-dim") : "";

                return (
                  <tr key={amenity.key} className={rowClass}>
                    <th scope="row" className="feature-row-label">
                      {amenity.label}
                      {highlightDiff && isDiff && <span className="diff-pill-dot" title="Differs" />}
                    </th>
                    {properties.map((property) => {
                      const present = hasAmenity(property);
                      return (
                        <td key={property.id} className="matrix-cell text-center">
                          {present ? (
                            <span className="amenity-check" title="Available">
                              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="3">
                                <polyline points="20 6 9 17 4 12" />
                              </svg>
                              <span>Included</span>
                            </span>
                          ) : (
                            <span className="amenity-cross" title="Not specified">
                              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5">
                                <line x1="18" y1="6" x2="6" y2="18" />
                                <line x1="6" y1="6" x2="18" y2="18" />
                              </svg>
                              <span>—</span>
                            </span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}

              {/* Bottom Schedule Action Row */}
              <tr className="matrix-action-footer-row">
                <th scope="row" className="feature-row-label">
                  Ready to Tour?
                </th>
                {properties.map((property) => (
                  <td key={property.id} className="matrix-cell">
                    <Link
                      className="button secondary small"
                      href={`/properties/${encodeURIComponent(property.slug)}`}
                    >
                      Book Tour
                    </Link>
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
