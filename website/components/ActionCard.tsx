"use client";

import React, { useState } from "react";
import Link from "next/link";
import { addToShortlist, removeFromShortlist, isShortlisted } from "@/lib/favorites";

export interface ActionPayload {
  property_id?: string;
  property_ids?: string[];
  property_title?: string;
  action?: "add" | "remove";
  city?: string;
  area?: string;
  max_price?: number;
  min_price?: number;
  bedrooms?: number;
  purpose?: string;
  count?: number;
  property_price_pkr?: number;
  down_payment_pct?: number;
  tenure_years?: number;
  finance_type?: string;
  loan_amount_pkr?: number;
  estimated_monthly_payment_pkr?: number;
  path?: string;
  label?: string;
  [key: string]: unknown;
}

export interface ChatAction {
  id: string;
  kind: "filter_catalog" | "compare_properties" | "shortlist_property" | "calculate_mortgage" | "schedule_viewing" | "navigate_to";
  payload: ActionPayload;
  summary: string;
  status?: "executed" | "undone" | "confirmed";
}

interface ActionCardProps {
  action: ChatAction;
  onUndo?: (actionId: string) => void;
}

export function ActionCard({ action, onUndo }: ActionCardProps) {
  const [localStatus, setLocalStatus] = useState<"executed" | "undone" | "confirmed">(
    action.status || "executed"
  );

  const handleToggleShortlist = (propId: string) => {
    const slug = propId.toLowerCase();
    if (isShortlisted(slug)) {
      removeFromShortlist(slug);
      setLocalStatus("undone");
    } else {
      addToShortlist(slug);
      setLocalStatus("executed");
    }
    if (onUndo) onUndo(action.id);
  };

  // 1. Catalog Filter Action Card
  if (action.kind === "filter_catalog") {
    const p = action.payload;
    const queryParts: string[] = [];
    if (p.city) queryParts.push(`city=${encodeURIComponent(p.city)}`);
    if (p.area) queryParts.push(`area=${encodeURIComponent(p.area)}`);
    if (p.max_price) queryParts.push(`max_price_pkr=${p.max_price}`);
    if (p.bedrooms) queryParts.push(`bedrooms=${p.bedrooms}`);
    if (p.purpose) queryParts.push(`transaction_type=${encodeURIComponent(p.purpose)}`);
    const catalogUrl = queryParts.length > 0 ? `/properties?${queryParts.join("&")}` : "/properties";

    return (
      <div className="action-card action-card-filter" role="region" aria-label="Catalog Filter Action">
        <div className="action-card-header">
          <div className="action-card-title-group">
            <span className="action-card-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
              </svg>
            </span>
            <span className="action-card-title">Live Catalog Filter Applied</span>
          </div>
          <span className="action-card-badge status-active">Active Filter</span>
        </div>

        <div className="action-card-body">
          <div className="action-filter-tags">
            {p.city && <span className="action-tag"><strong>City:</strong> {p.city}</span>}
            {p.area && <span className="action-tag"><strong>Area:</strong> {p.area}</span>}
            {p.max_price && (
              <span className="action-tag">
                <strong>Max:</strong> Rs. {(p.max_price / 10_000_000).toFixed(1)} Cr
              </span>
            )}
            {p.bedrooms && <span className="action-tag"><strong>Beds:</strong> {p.bedrooms}</span>}
            {p.purpose && <span className="action-tag"><strong>Type:</strong> {p.purpose}</span>}
          </div>
          {typeof p.count === "number" && (
            <p className="action-detail-note">
              Found <strong>{p.count}</strong> verified listing{p.count === 1 ? "" : "s"} matching this criteria.
            </p>
          )}
        </div>

        <div className="action-card-footer">
          <Link href={catalogUrl} className="action-btn action-btn-primary">
            <span>View Filtered Results</span>
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.2">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </Link>
          <Link href="/properties" className="action-btn action-btn-ghost">
            Clear Filters
          </Link>
        </div>
      </div>
    );
  }

  if (action.kind === "compare_properties") {
    const ids = Array.isArray(action.payload.property_ids) ? action.payload.property_ids : [];
    return (
      <div className="action-card action-card-filter" role="region" aria-label="Property comparison action">
        <div className="action-card-header">
          <div className="action-card-title-group"><span className="action-card-title">Side-by-side comparison opened</span></div>
          <span className="action-card-badge status-active">{ids.length} Listings</span>
        </div>
        <div className="action-card-body">
          <p className="action-detail-note">Comparing current results: <strong>{ids.map((id) => id.toUpperCase()).join(", ")}</strong>. Review the available listing details before deciding.</p>
        </div>
        <div className="action-card-footer">
          <Link href="/properties" className="action-btn action-btn-primary"><span>Browse listings</span></Link>
        </div>
      </div>
    );
  }

  // 2. Shortlist / Favorite Action Card
  if (action.kind === "shortlist_property") {
    const propId = String(action.payload.property_id || "PROP-001");
    const isAdd = action.payload.action !== "remove";
    const currentActive = localStatus === "executed" ? isAdd : !isAdd;

    return (
      <div className="action-card action-card-shortlist" role="region" aria-label="Shortlist Action">
        <div className="action-card-header">
          <div className="action-card-title-group">
            <span className="action-card-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" stroke="currentColor" strokeWidth="1.5">
                <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
              </svg>
            </span>
            <span className="action-card-title">
              {currentActive ? "Property Saved to Shortlist" : "Removed from Shortlist"}
            </span>
          </div>
          <span className={`action-card-badge ${currentActive ? "status-success" : "status-muted"}`}>
            {currentActive ? "Shortlist Synced" : "Unsaved"}
          </span>
        </div>

        <div className="action-card-body">
          <p className="action-property-ref">
            Reference: <strong>{propId.toUpperCase()}</strong>
          </p>
          <p className="action-detail-note">
            {currentActive
              ? "Saved to your local session and header counter. Access anytime from the top bar."
              : "Property has been removed from your saved collection."}
          </p>
        </div>

        <div className="action-card-footer">
          <Link href="/shortlist" className="action-btn action-btn-primary">
            <span>View Shortlist</span>
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.2">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </Link>
          <button
            type="button"
            className="action-btn action-btn-secondary"
            onClick={() => handleToggleShortlist(propId)}
          >
            {currentActive ? "Undo (Remove)" : "Save Again"}
          </button>
        </div>
      </div>
    );
  }

  // 3. Mortgage Calculation Action Card
  if (action.kind === "calculate_mortgage") {
    const p = action.payload;
    const price = Number(p.property_price_pkr || 0);
    const downPct = Number(p.down_payment_pct || 25);
    const tenure = Number(p.tenure_years || 20);
    const isIslamic = p.finance_type === "diminishing_musharakah";
    const financeLabel = isIslamic ? "Diminishing Musharakah" : p.finance_type === "conventional" ? "Conventional" : "Choose financing terms";
    const financeQuery = isIslamic ? "islamic" : p.finance_type === "conventional" ? "conventional" : "unspecified";
    const downPkr = Math.round(price * (downPct / 100));
    const loanPkr = price - downPkr;

    return (
      <div className="action-card action-card-finance" role="region" aria-label="Mortgage Calculation Action">
        <div className="action-card-header">
          <div className="action-card-title-group">
            <span className="action-card-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="4" y="2" width="16" height="20" rx="2" />
                <line x1="8" y1="6" x2="16" y2="6" />
                <line x1="16" y1="14" x2="16" y2="18" />
                <path d="M16 10h.01" />
                <path d="M12 10h.01" />
                <path d="M8 10h.01" />
                <path d="M12 14h.01" />
                <path d="M8 14h.01" />
                <path d="M12 18h.01" />
                <path d="M8 18h.01" />
              </svg>
            </span>
            <span className="action-card-title">Installment Estimator Opened</span>
          </div>
          <span className="action-card-badge status-gold">
            {financeLabel}
          </span>
        </div>

        <div className="action-card-body">
          <div className="finance-hero-metric">
            <span className="metric-label">Installment estimate opened</span>
            <p className="action-detail-note">The monthly amount depends on the rate and financing terms you choose in the editable calculator. No bank quote has been requested.</p>
          </div>

          <div className="finance-metrics-grid">
            <div className="metric-sub-card">
              <span className="metric-sub-label">Property Value</span>
              <span className="metric-sub-val">PKR {price.toLocaleString()}</span>
            </div>
            <div className="metric-sub-card">
              <span className="metric-sub-label">Down Payment ({downPct}%)</span>
              <span className="metric-sub-val">PKR {downPkr.toLocaleString()}</span>
            </div>
            <div className="metric-sub-card">
              <span className="metric-sub-label">Financing Amount</span>
              <span className="metric-sub-val">PKR {loanPkr.toLocaleString()}</span>
            </div>
            <div className="metric-sub-card">
              <span className="metric-sub-label">Loan Tenure</span>
              <span className="metric-sub-val">{tenure} Years ({tenure * 12} mo)</span>
            </div>
          </div>
        </div>

        <div className="action-card-footer">
          <Link
            href={`/calculator?price=${price}&down=${downPct}&tenure=${tenure}&type=${financeQuery}`}
            className="action-btn action-btn-primary"
          >
            <span>Open Interactive Calculator</span>
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.2">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </Link>
          <Link href="/contact?subject=Home+Financing+Advisory" className="action-btn action-btn-ghost">
            Request Bank Quotation
          </Link>
        </div>
      </div>
    );
  }

  // 4. Schedule Viewing Action Card
  if (action.kind === "schedule_viewing") {
    const propId = String(action.payload.property_id || "Listing");
    return (
      <div className="action-card action-card-viewing" role="region" aria-label="Viewing Schedule Action">
        <div className="action-card-header">
          <div className="action-card-title-group">
            <span className="action-card-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                <line x1="16" y1="2" x2="16" y2="6" />
                <line x1="8" y1="2" x2="8" y2="6" />
                <line x1="3" y1="10" x2="21" y2="10" />
              </svg>
            </span>
            <span className="action-card-title">Viewing request form opened</span>
          </div>
          <span className="action-card-badge status-active">Slot Reservation</span>
        </div>

        <div className="action-card-body">
            <p className="action-detail-note">
            No visit is booked yet. Choose a slot and confirm your contact details and consent to submit a request for <strong>{propId}</strong>.
          </p>
        </div>

        <div className="action-card-footer">
          <Link href={`/contact?property=${encodeURIComponent(propId)}`} className="action-btn action-btn-primary">
            <span>Confirm Viewing Slot</span>
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.2">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </Link>
        </div>
      </div>
    );
  }

  // 5. Navigation Action Card
  if (action.kind === "navigate_to") {
    const path = String(action.payload.path || "/catalog");
    const label = String(action.payload.label || "Page");

    return (
      <div className="action-card action-card-nav" role="region" aria-label="Page Navigation Action">
        <div className="action-card-header">
          <div className="action-card-title-group">
            <span className="action-card-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" />
              </svg>
            </span>
            <span className="action-card-title">Navigation: {label}</span>
          </div>
          <span className="action-card-badge status-active">Route</span>
        </div>

        <div className="action-card-body">
          <p className="action-detail-note">
            Target route: <code>{path}</code>
          </p>
        </div>

        <div className="action-card-footer">
          <Link href={path} className="action-btn action-btn-primary">
            <span>Proceed to {label}</span>
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.2">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </Link>
        </div>
      </div>
    );
  }

  return null;
}
