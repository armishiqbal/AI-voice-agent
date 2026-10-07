"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { setStoredShortlist, useShortlist } from "@/lib/favorites";
import { ListingCard } from "@/components/ListingCard";
import { InquiryForm } from "@/components/InquiryForm";
import { isListing, type Listing } from "@/lib/catalog";

export default function ShortlistPage() {
  const { ready, slugs, count, clear } = useShortlist();
  const [properties, setProperties] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [clearDialogOpen, setClearDialogOpen] = useState(false);
  const [inquireProperty, setInquireProperty] = useState<Listing | null>(null);
  const clearDialogRef = useRef<HTMLDialogElement>(null);
  const inquiryDialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (!ready) return;

    if (slugs.length === 0) {
      setProperties([]);
      setError(false);
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setError(false);

    fetch(`/api/shortlist?slugs=${encodeURIComponent(slugs.join(","))}`, {
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Could not load saved properties.");
        const payload: unknown = await response.json();
        if (
          typeof payload !== "object" ||
          payload === null ||
          !("data" in payload) ||
          !Array.isArray(payload.data) ||
          !payload.data.every(isListing)
        ) {
          throw new Error("The saved properties response was invalid.");
        }
        setProperties(payload.data);
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(true);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [ready, slugs, retryCount]);

  useEffect(() => {
    const dialog = clearDialogRef.current;
    if (!dialog) return;
    if (clearDialogOpen && !dialog.open) dialog.showModal();
    if (!clearDialogOpen && dialog.open) dialog.close();
  }, [clearDialogOpen]);

  useEffect(() => {
    const dialog = inquiryDialogRef.current;
    if (!dialog) return;
    if (inquireProperty && !dialog.open) dialog.showModal();
    if (!inquireProperty && dialog.open) dialog.close();
  }, [inquireProperty]);

  const compareSlugs = properties.slice(0, 3).map((property) => property.slug);
  const compareUrl = `/compare?slugs=${encodeURIComponent(compareSlugs.join(","))}`;
  const missingCount = Math.max(count - properties.length, 0);
  const removeMissing = () => {
    setStoredShortlist(properties.map((property) => property.slug));
  };

  return (
    <section className="shortlist-page container" aria-labelledby="shortlist-title">
      <nav className="breadcrumbs" aria-label="Breadcrumb">
        <Link href="/">Home</Link>
        <span aria-hidden="true">/</span>
        <Link href="/properties">Properties</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">Saved</span>
      </nav>

      <header className="shortlist-page-heading">
        <div>
          <p className="eyebrow">Your shortlist</p>
          <h1 id="shortlist-title">Saved for later</h1>
          <p>Keep properties you like together. Your list is saved in this browser.</p>
        </div>
        <p className="shortlist-count-chip" aria-live="polite">
          <strong>{ready ? count : "—"}</strong>
          <span>{count === 1 ? "saved property" : "saved properties"}</span>
        </p>
      </header>

      {count > 0 && (
        <div className="shortlist-toolbar">
          <p>
            {properties.length > 0
              ? `${properties.length} ${properties.length === 1 ? "property" : "properties"} ready to review`
              : "Your saved properties are being loaded."}
          </p>
          <div className="shortlist-actions">
            {properties.length >= 2 && (
              <Link className="button" href={compareUrl}>
                Compare {compareSlugs.length === 3 && properties.length > 3 ? "first 3" : "properties"}
              </Link>
            )}
            <button
              type="button"
              className="button secondary"
              onClick={() => setClearDialogOpen(true)}
              aria-haspopup="dialog"
            >
              Clear saved list
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="shortlist-loading-grid" aria-label="Loading saved properties" aria-busy="true">
          {Array.from({ length: Math.min(Math.max(count, 1), 3) }, (_, index) => (
            <div className="shortlist-skeleton" key={index} aria-hidden="true">
              <div className="shortlist-skeleton-image" />
              <div className="shortlist-skeleton-line" />
              <div className="shortlist-skeleton-line shortlist-skeleton-line-short" />
              <div className="shortlist-skeleton-line" />
            </div>
          ))}
        </div>
      ) : error ? (
        <div className="shortlist-state-card shortlist-error" role="alert">
          <p className="eyebrow">Connection problem</p>
          <h2>We couldn&rsquo;t load your saved properties</h2>
          <p>Your saved list is still in this browser. Try loading it again.</p>
          <button className="button" type="button" onClick={() => setRetryCount((value) => value + 1)}>
            Try again
          </button>
        </div>
      ) : count === 0 ? (
        <div className="shortlist-discovery-layout">
          <section className="shortlist-empty-panel">
            <div className="shortlist-empty-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
              </svg>
            </div>
            <p className="eyebrow">Nothing saved yet</p>
            <h2>Keep the places you like close</h2>
            <p>Tap the bookmark on any property to add it here. You can compare your saved places later.</p>
            <Link className="button" href="/properties">Browse properties</Link>
          </section>

          <aside className="shortlist-next-steps" aria-labelledby="shortlist-explore-title">
            <p className="eyebrow">Explore Awaaz Estate</p>
            <h2 id="shortlist-explore-title">Find your next move</h2>
            <Link href="/properties?transaction_type=sale" className="shortlist-explore-link">
              <span><strong>Buy a property</strong><small>Homes, plots, and more</small></span>
              <span aria-hidden="true">↗</span>
            </Link>
            <Link href="/properties?transaction_type=rent" className="shortlist-explore-link">
              <span><strong>Find a rental</strong><small>Explore places for rent</small></span>
              <span aria-hidden="true">↗</span>
            </Link>
            <Link href="/assistant" className="shortlist-explore-link">
              <span><strong>Ask the Awaaz assistant</strong><small>Search by telling us what you need</small></span>
              <span aria-hidden="true">↗</span>
            </Link>
          </aside>
        </div>
      ) : properties.length === 0 ? (
        <div className="shortlist-state-card">
          <p className="eyebrow">Saved list needs a refresh</p>
          <h2>We couldn&rsquo;t find these property details</h2>
          <p>
            The saved links may have left the public catalog. Remove those entries or continue browsing current listings.
          </p>
          <div className="shortlist-state-actions">
            <button className="button secondary" type="button" onClick={removeMissing}>
              Remove saved links
            </button>
            <Link className="button" href="/properties">Browse properties</Link>
          </div>
        </div>
      ) : (
        <>
          {missingCount > 0 && (
            <div className="shortlist-missing-note" role="status">
              <p>
                {missingCount} saved {missingCount === 1 ? "property link could not" : "property links could not"} be found in the catalog.
              </p>
              <button type="button" onClick={removeMissing}>Remove missing links</button>
            </div>
          )}

          <div className="listing-grid shortlist-listing-grid">
            {properties.map((property) => (
              <article key={property.id} className="shortlist-item-wrapper">
                <ListingCard property={property} />
                <button
                  type="button"
                  className="shortlist-inquiry-button"
                  onClick={() => setInquireProperty(property)}
                >
                  Ask about this property
                </button>
              </article>
            ))}
          </div>
        </>
      )}

      <dialog
        ref={clearDialogRef}
        className="shortlist-dialog"
        aria-labelledby="clear-shortlist-title"
        onClose={() => setClearDialogOpen(false)}
      >
        <p className="eyebrow">Saved properties</p>
        <h2 id="clear-shortlist-title">Clear your saved list?</h2>
        <p>This removes all {count} saved {count === 1 ? "property" : "properties"} from this browser.</p>
        <div className="shortlist-dialog-actions">
          <button className="button secondary" type="button" onClick={() => setClearDialogOpen(false)}>
            Keep list
          </button>
          <button className="button shortlist-clear-confirm" type="button" onClick={() => {
            clear();
            setClearDialogOpen(false);
          }}>
            Clear saved list
          </button>
        </div>
      </dialog>

      <dialog
        ref={inquiryDialogRef}
        className="shortlist-dialog shortlist-inquiry-dialog"
        aria-labelledby="inquiry-dialog-title"
        onClose={() => setInquireProperty(null)}
        onClick={(event) => {
          if (event.target === event.currentTarget) setInquireProperty(null);
        }}
      >
        {inquireProperty && (
          <>
            <div className="shortlist-dialog-heading">
              <div>
                <p className="eyebrow">Property inquiry</p>
                <h2 id="inquiry-dialog-title">{inquireProperty.title}</h2>
              </div>
              <button
                className="shortlist-dialog-close"
                type="button"
                onClick={() => setInquireProperty(null)}
                aria-label="Close property inquiry"
              >
                ×
              </button>
            </div>
            <InquiryForm listingId={inquireProperty.id} listingTitle={inquireProperty.title} />
          </>
        )}
      </dialog>
    </section>
  );
}
