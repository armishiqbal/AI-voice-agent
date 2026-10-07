"use client";

import { useState } from "react";
import Link from "next/link";
import { type Listing, type SearchParams, catalogQuery } from "@/lib/catalog";
import { PropertyFilterBar } from "@/components/PropertyFilterBar";
import { ListingCard } from "@/components/ListingCard";
import { SectorVectorMap } from "@/components/SectorVectorMap";
import { Notice } from "@/components/Notice";

interface PropertiesCatalogContainerProps {
  params: SearchParams;
  properties: Listing[];
  total: number;
  page: number;
  totalPages: number;
  errorMessage?: string | null;
  isValidationError?: boolean;
}

export function PropertiesCatalogContainer({
  params,
  properties,
  total,
  page,
  totalPages,
  errorMessage,
  isValidationError,
}: PropertiesCatalogContainerProps) {
  const [viewMode, setViewMode] = useState<"grid" | "list" | "map">("grid");

  const buildPageHref = (targetPage: number) => {
    const query = catalogQuery(params);
    query.set("page", String(targetPage));
    return `/properties?${query.toString()}`;
  };

  const hasPrice = Boolean(params.min_price_pkr || params.max_price_pkr);
  const hasLocation = Boolean(params.city || params.area || params.q);
  const hasType = Boolean(params.property_type);

  const getRelaxedHref = (removeKeys: string[]) => {
    const q = catalogQuery(params);
    removeKeys.forEach((k) => q.delete(k));
    q.delete("page");
    const qs = q.toString();
    return qs ? `/properties?${qs}` : "/properties";
  };

  return (
    <div className="properties-catalog-root">
      {/* Dynamic Pill Filter Console */}
      <PropertyFilterBar
        params={params}
        totalResults={total}
        currentView={viewMode}
        onViewChange={(mode) => setViewMode(mode)}
      />

      {/* Error State */}
      {errorMessage ? (
        <Notice error title={isValidationError ? "Check your search filters" : "The property search is unavailable"}>
          <p>{errorMessage}</p>
        </Notice>
      ) : (
        <>
          {/* Listings Display: Grid, List, or Sector Map */}
          {properties.length > 0 ? (
            viewMode === "map" ? (
              <SectorVectorMap properties={properties} />
            ) : (
              <div className={`listing-grid ${viewMode === "list" ? "list-view" : ""}`}>
                {properties.map((property) => (
                  <ListingCard key={property.id} property={property} />
                ))}
              </div>
            )
          ) : (
            <Notice title="No properties match your current criteria">
              <p>
                We could not find any active properties matching this specific combination. Try relaxing your parameters below:
              </p>
              <div style={{ marginTop: 16, display: "flex", flexWrap: "wrap", gap: 10 }}>
                {hasPrice && (
                  <Link className="button small secondary" href={getRelaxedHref(["min_price_pkr", "max_price_pkr"])}>
                    Remove Price Filter
                  </Link>
                )}
                {hasLocation && (
                  <Link className="button small secondary" href={getRelaxedHref(["area", "city", "q"])}>
                    Show All Locations
                  </Link>
                )}
                {hasType && (
                  <Link className="button small secondary" href={getRelaxedHref(["property_type"])}>
                    Any Property Type
                  </Link>
                )}
                <Link className="button small primary" href="/properties">
                  Reset All Filters
                </Link>
                <Link className="button small secondary" href="/assistant">
                  Ask Voice Concierge
                </Link>
              </div>
            </Notice>
          )}

          {/* Luxury Pagination Controls */}
          {totalPages > 1 && (
            <nav className="pagination-modern" aria-label="Search results pages">
              {page > 1 ? (
                <Link className="pagination-btn" href={buildPageHref(page - 1)}>
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <polyline points="15 18 9 12 15 6" />
                  </svg>
                  Previous
                </Link>
              ) : (
                <span className="pagination-btn disabled">
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <polyline points="15 18 9 12 15 6" />
                  </svg>
                  Previous
                </span>
              )}

              <div className="pagination-numbers">
                {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => {
                  // Show current page, first, last, and immediate neighbors
                  if (p === 1 || p === totalPages || (p >= page - 1 && p <= page + 1)) {
                    return (
                      <Link
                        key={p}
                        href={buildPageHref(p)}
                        className={`page-number-pill ${p === page ? "active" : ""}`}
                        aria-current={p === page ? "page" : undefined}
                      >
                        {p}
                      </Link>
                    );
                  }
                  if (p === page - 2 || p === page + 2) {
                    return <span key={p} className="page-ellipsis">…</span>;
                  }
                  return null;
                })}
              </div>

              {page < totalPages ? (
                <Link className="pagination-btn" href={buildPageHref(page + 1)}>
                  Next
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <polyline points="9 18 15 12 9 6" />
                  </svg>
                </Link>
              ) : (
                <span className="pagination-btn disabled">
                  Next
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <polyline points="9 18 15 12 9 6" />
                  </svg>
                </span>
              )}
            </nav>
          )}
        </>
      )}
    </div>
  );
}
