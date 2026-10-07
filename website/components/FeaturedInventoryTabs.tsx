"use client";

import { useState } from "react";
import Link from "next/link";
import { ListingCard } from "@/components/ListingCard";
import type { Listing } from "@/lib/catalog";

interface FeaturedInventoryTabsProps {
  properties: Listing[];
}

export function FeaturedInventoryTabs({ properties }: FeaturedInventoryTabsProps) {
  const [activeTab, setActiveTab] = useState<string>("all");

  const filterProperties = () => {
    switch (activeTab) {
      case "villas":
        return properties.filter((p) => p.property_type === "house");
      case "apartments":
        return properties.filter((p) => p.property_type === "apartment");
      case "commercial":
        return properties.filter((p) => ["office", "shop", "warehouse"].includes(p.property_type));
      case "dha-bahria":
        return properties.filter((p) => {
          const loc = `${p.area} ${p.title}`.toLowerCase();
          return loc.includes("dha") || loc.includes("bahria");
        });
      default:
        return properties;
    }
  };

  const filtered = filterProperties();

  const tabs = [
    {
      id: "all",
      label: "All Verified",
      count: properties.length,
      icon: (
        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <rect width="7" height="7" x="3" y="3" rx="1" />
          <rect width="7" height="7" x="14" y="3" rx="1" />
          <rect width="7" height="7" x="14" y="14" rx="1" />
          <rect width="7" height="7" x="3" y="14" rx="1" />
        </svg>
      ),
    },
    {
      id: "villas",
      label: "Luxury Villas",
      count: properties.filter((p) => p.property_type === "house").length,
      icon: (
        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
          <polyline points="9 22 9 12 15 12 15 22" />
        </svg>
      ),
    },
    {
      id: "apartments",
      label: "Apartments & Penthouses",
      count: properties.filter((p) => p.property_type === "apartment").length,
      icon: (
        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <rect width="16" height="20" x="4" y="2" rx="2" />
          <path d="M9 22v-4h6v4M8 6h.01M16 6h.01M12 6h.01M12 10h.01M12 14h.01M16 10h.01M16 14h.01M8 10h.01M8 14h.01" />
        </svg>
      ),
    },
    {
      id: "commercial",
      label: "Commercial & Offices",
      count: properties.filter((p) => ["office", "shop", "warehouse"].includes(p.property_type)).length,
      icon: (
        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <rect width="20" height="14" x="2" y="7" rx="2" />
          <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
        </svg>
      ),
    },
    {
      id: "dha-bahria",
      label: "DHA & Bahria Enclaves",
      count: properties.filter((p) => {
        const loc = `${p.area} ${p.title}`.toLowerCase();
        return loc.includes("dha") || loc.includes("bahria");
      }).length,
      icon: (
        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
          <circle cx="12" cy="10" r="3" />
        </svg>
      ),
    },
  ];

  return (
    <div className="featured-inventory-tabs-root">
      {/* Category Tabs Strip */}
      <div className="inventory-tabs-scroller" role="tablist" aria-label="Featured property categories">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            className={`inventory-tab-pill ${activeTab === tab.id ? "active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <span className="tab-pill-icon">{tab.icon}</span>
            <span className="tab-pill-label">{tab.label}</span>
            <span className="tab-count-badge">{tab.count}</span>
          </button>
        ))}
      </div>

      {/* Filtered Cards Grid */}
      {filtered.length > 0 ? (
        <div className="listing-grid featured-grid">
          {filtered.slice(0, 6).map((property) => (
            <ListingCard key={property.id} property={property} />
          ))}
        </div>
      ) : (
        <div className="tab-empty-notice">
          <p>No listings in this specific category are currently published in the catalog.</p>
          <button type="button" className="button small secondary" onClick={() => setActiveTab("all")}>
            View All Properties
          </button>
        </div>
      )}

      {/* Explore More Footer Bar */}
      <div className="featured-explore-footer">
        <p className="explore-footer-text">
          Displaying direct company inventory. All properties audited with physical surveys & title scrutiny.
        </p>
        <Link className="button primary" href="/properties">
          <span>Browse All Verified Inventory ({properties.length}+) →</span>
        </Link>
      </div>
    </div>
  );
}
