"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCompare } from "@/lib/compare";
import { formatPkrShort } from "@/lib/site";
import { photoUrl } from "@/lib/catalog";

export function ComparisonTray() {
  const router = useRouter();
  const { ready, items, count, remove, clear } = useCompare();

  if (!ready || count === 0) return null;

  const compareUrl = `/compare?slugs=${items.map((i) => encodeURIComponent(i.slug)).join(",")}`;

  return (
    <div className="comparison-tray-dock" role="region" aria-label="Property comparison tray">
      <div className="comparison-tray-inner">
        {/* Header / Info Pill */}
        <div className="tray-info-header">
          <div className="tray-badge-counter">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
              <path d="M16 3h5v5M4 20L20.2 3.8M21 16v5h-5M15 15l5.1 5.1M4 4l5 5" />
            </svg>
            <span>Compare ({count}/3)</span>
          </div>
          <span className="tray-hint">Select up to 3 listings to evaluate side-by-side</span>
        </div>

        {/* 3 Slot Items */}
        <div className="tray-slots-row">
          {items.map((item) => (
            <div key={item.slug} className="tray-slot filled">
              {item.photo_url ? (
                <img
                  src={photoUrl(item.photo_url)}
                  alt=""
                  width="44"
                  height="44"
                  className="tray-slot-thumb"
                />
              ) : (
                <div className="tray-slot-placeholder-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
                  </svg>
                </div>
              )}
              <div className="tray-slot-text">
                <span className="tray-slot-title" title={item.title}>{item.title}</span>
                {item.price_pkr && (
                  <span className="tray-slot-price">{formatPkrShort(item.price_pkr)}</span>
                )}
              </div>
              <button
                type="button"
                className="tray-remove-btn"
                onClick={() => remove(item.slug)}
                title={`Remove ${item.title} from comparison`}
                aria-label={`Remove ${item.title}`}
              >
                ×
              </button>
            </div>
          ))}

          {/* Empty slot placeholder if count < 3 */}
          {Array.from({ length: 3 - count }).map((_, idx) => (
            <div key={`empty-${idx}`} className="tray-slot empty">
              <span className="empty-slot-plus">+</span>
              <span className="empty-slot-label">Add Listing</span>
            </div>
          ))}
        </div>

        {/* Action Controls */}
        <div className="tray-actions">
          <button
            type="button"
            className="tray-clear-btn"
            onClick={clear}
            title="Clear all selected properties"
          >
            Clear
          </button>
          <button
            type="button"
            className="button small tray-launch-btn"
            onClick={() => router.push(compareUrl)}
          >
            <span>Compare Now</span>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
