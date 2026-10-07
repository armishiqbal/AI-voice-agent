"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { Listing } from "@/lib/catalog";
import { formatPkrShort, label } from "@/lib/site";

interface SectorVectorMapProps {
  properties: Listing[];
}

type MapSectorZone = {
  id: string;
  name: string;
  city: "Islamabad" | "Rawalpindi";
  authority: string;
  x: number;
  y: number;
  width: number;
  height: number;
  labelX: number;
  labelY: number;
};

const SECTOR_ZONES: MapSectorZone[] = [
  // Islamabad CDA Sectors
  { id: "e-7", name: "Sector E-7", city: "Islamabad", authority: "CDA", x: 260, y: 70, width: 85, height: 60, labelX: 302, labelY: 105 },
  { id: "f-6", name: "Sector F-6", city: "Islamabad", authority: "CDA", x: 360, y: 70, width: 85, height: 60, labelX: 402, labelY: 105 },
  { id: "f-7", name: "Sector F-7", city: "Islamabad", authority: "CDA", x: 260, y: 145, width: 85, height: 60, labelX: 302, labelY: 180 },
  { id: "f-8", name: "Sector F-8", city: "Islamabad", authority: "CDA", x: 160, y: 145, width: 85, height: 60, labelX: 202, labelY: 180 },
  { id: "f-10", name: "Sector F-10", city: "Islamabad", authority: "CDA", x: 60, y: 145, width: 85, height: 60, labelX: 102, labelY: 180 },
  { id: "blue-area", name: "Blue Area Jinnah Ave", city: "Islamabad", authority: "CDA Commercial", x: 260, y: 220, width: 220, height: 35, labelX: 370, labelY: 242 },
  { id: "g-9", name: "Sector G-9", city: "Islamabad", authority: "CDA", x: 160, y: 270, width: 85, height: 60, labelX: 202, labelY: 305 },
  { id: "g-10", name: "Sector G-10", city: "Islamabad", authority: "CDA", x: 60, y: 270, width: 85, height: 60, labelX: 102, labelY: 305 },
  // Islamabad Expressway & Agro Enclaves
  { id: "gulberg-greens", name: "Gulberg Greens (IBECHS)", city: "Islamabad", authority: "IBECHS / CDA NOC", x: 490, y: 290, width: 140, height: 80, labelX: 560, labelY: 335 },
  // Southern Twin City Enclaves
  { id: "dha-phase-2", name: "DHA Phase 2 & Giga Mall", city: "Islamabad", authority: "DHA", x: 440, y: 410, width: 150, height: 95, labelX: 515, labelY: 460 },
  { id: "bahria-town-phase-7", name: "Bahria Town Phase 7", city: "Rawalpindi", authority: "Bahria / RDA", x: 230, y: 430, width: 160, height: 85, labelX: 310, labelY: 475 },
];

export function SectorVectorMap({ properties }: SectorVectorMapProps) {
  const [selectedProperty, setSelectedProperty] = useState<Listing | null>(
    properties[0] || null
  );
  const [activeSectorId, setActiveSectorId] = useState<string | null>(null);

  // Match each property to a map coordinate
  const getCoordinatesForListing = (p: Listing): { x: number; y: number } => {
    const area = p.area.toLowerCase();
    if (area.includes("f-7") || area.includes("f7")) return { x: 302, y: 175 };
    if (area.includes("f-10") || area.includes("f10")) return { x: 102, y: 175 };
    if (area.includes("blue area")) return { x: 360, y: 237 };
    if (area.includes("gulberg")) return { x: 560, y: 330 };
    if (area.includes("dha")) return { x: 515, y: 455 };
    if (area.includes("bahria")) return { x: 310, y: 470 };
    return { x: 202, y: 175 }; // Default center
  };

  return (
    <div className="sector-vector-map-wrapper">
      <div className="map-top-bar">
        <div className="map-legend">
          <span className="legend-item">
            <span className="legend-color isb-color" />
            <span>Islamabad CDA &amp; Expressways</span>
          </span>
          <span className="legend-item">
            <span className="legend-color dha-color" />
            <span>DHA &amp; Bahria Gated Communities</span>
          </span>
          <span className="legend-item">
            <span className="legend-pin-dot" />
            <span>Active Verified Property Pin</span>
          </span>
        </div>

        <span className="map-count-badge">
          {properties.length} Verified {properties.length === 1 ? "Asset Plotted" : "Assets Plotted"}
        </span>
      </div>

      <div className="map-stage-container">
        {/* SVG Vector Blueprint */}
        <div className="svg-map-frame">
          <svg
            viewBox="0 0 720 540"
            className="islamabad-blueprint-svg"
            xmlns="http://www.w3.org/2000/svg"
          >
            {/* Background Map Grid */}
            <defs>
              <pattern id="gridPattern" width="30" height="30" patternUnits="userSpaceOnUse">
                <path d="M 30 0 L 0 0 0 30" fill="none" stroke="rgba(24, 82, 60, 0.08)" strokeWidth="0.8" />
              </pattern>
              <linearGradient id="margallaGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#0d2920" />
                <stop offset="50%" stopColor="#154534" />
                <stop offset="100%" stopColor="#0a2118" />
              </linearGradient>
            </defs>

            <rect width="100%" height="100%" fill="#f7fbf8" />
            <rect width="100%" height="100%" fill="url(#gridPattern)" />

            {/* Margalla Hills Ridge at Top */}
            <path
              d="M 0 0 L 720 0 L 720 40 Q 560 55 420 35 Q 260 55 120 35 Q 40 45 0 35 Z"
              fill="url(#margallaGrad)"
            />
            <text x="360" y="24" fill="#7fe0be" fontSize="11" fontWeight="700" letterSpacing="3" textAnchor="middle">
              MARGALLA HILLS NATIONAL PARK (FOOTHILLS RIDGE)
            </text>

            {/* Major Arterial Roads */}
            {/* Srinagar / Kashmir Highway */}
            <path d="M 20 205 L 700 205" stroke="#d5e4da" strokeWidth="6" strokeLinecap="round" />
            <text x="630" y="200" fill="#799587" fontSize="9" fontWeight="750">Srinagar Highway</text>

            {/* Islamabad Expressway */}
            <path d="M 400 220 Q 460 270 510 400 L 530 520" stroke="#d5e4da" strokeWidth="8" strokeLinecap="round" fill="none" />
            <text x="545" y="380" fill="#799587" fontSize="9" fontWeight="750" transform="rotate(70 545,380)">
              Islamabad Expressway (Signal-Free Corridor)
            </text>

            {/* Soan River / GT Road at South */}
            <path d="M 80 500 Q 220 470 420 510 L 700 480" stroke="#b8d5c5" strokeWidth="4" strokeDasharray="6,4" fill="none" />
            <text x="140" y="525" fill="#799587" fontSize="9" fontWeight="750">Soan River &amp; GT Road</text>

            {/* Sector Zones */}
            {SECTOR_ZONES.map((zone) => {
              const isSelected = activeSectorId === zone.id;
              const hasListings = properties.some((p) => {
                const a = p.area.toLowerCase();
                if (zone.id === "f-7") return a.includes("f-7") || a.includes("f7");
                if (zone.id === "f-10") return a.includes("f-10") || a.includes("f10");
                if (zone.id === "blue-area") return a.includes("blue area");
                if (zone.id === "gulberg-greens") return a.includes("gulberg");
                if (zone.id === "dha-phase-2") return a.includes("dha");
                if (zone.id === "bahria-town-phase-7") return a.includes("bahria");
                return false;
              });

              return (
                <g
                  key={zone.id}
                  className={`sector-svg-group ${isSelected ? "selected" : ""} ${hasListings ? "has-assets" : ""}`}
                  onClick={() => setActiveSectorId(zone.id)}
                >
                  <rect
                    x={zone.x}
                    y={zone.y}
                    width={zone.width}
                    height={zone.height}
                    rx="8"
                    className="sector-zone-rect"
                  />
                  <text
                    x={zone.labelX}
                    y={zone.labelY}
                    textAnchor="middle"
                    className="sector-zone-label"
                  >
                    {zone.name}
                  </text>
                  <text
                    x={zone.labelX}
                    y={zone.labelY + 14}
                    textAnchor="middle"
                    className="sector-auth-sub"
                  >
                    {zone.authority}
                  </text>
                </g>
              );
            })}

            {/* Interactive Listing Pins */}
            {properties.map((p) => {
              const coords = getCoordinatesForListing(p);
              const isSelected = selectedProperty?.id === p.id;

              return (
                <g
                  key={p.id}
                  transform={`translate(${coords.x}, ${coords.y})`}
                  className={`property-map-pin ${isSelected ? "active-pin" : ""}`}
                  onClick={() => setSelectedProperty(p)}
                >
                  <circle r={isSelected ? "14" : "10"} className="pin-halo" />
                  <circle r={isSelected ? "8" : "6"} className="pin-core" />
                  <text y="-14" textAnchor="middle" className="pin-price-label">
                    {formatPkrShort(p.price_pkr)}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        {/* Selected Property Preview Drawer */}
        {selectedProperty && (
          <aside className="map-selected-drawer">
            <div className="drawer-header">
              <span className="drawer-kicker">{label(selectedProperty.property_type)}</span>
              <span className="drawer-price">{formatPkrShort(selectedProperty.price_pkr)} PKR</span>
            </div>

            <div className="drawer-thumb-wrap">
              {selectedProperty.photos[0] && (
                <Image
                  src={selectedProperty.photos[0].url}
                  alt={selectedProperty.title}
                  fill
                  sizes="320px"
                  style={{ objectFit: "cover" }}
                />
              )}
              <span className="drawer-status-tag">
                {selectedProperty.verification?.status === "verified" ? "Title Verified" : "Review Recorded"}
              </span>
            </div>

            <h4 className="drawer-title">{selectedProperty.title}</h4>
            <p className="drawer-location">
              {selectedProperty.area}, {selectedProperty.city}
            </p>

            <div className="drawer-specs-row">
              {selectedProperty.bedrooms > 0 && (
                <span>
                  <strong>{selectedProperty.bedrooms}</strong> Beds
                </span>
              )}
              {selectedProperty.bathrooms && (
                <span>
                  <strong>{selectedProperty.bathrooms}</strong> Baths
                </span>
              )}
              <span>
                <strong>{selectedProperty.size_sqft.toLocaleString()}</strong> sq ft
              </span>
            </div>

            <div className="drawer-actions">
              <Link href={`/properties/${selectedProperty.slug}`} className="button primary full-width">
                View Full Dossier →
              </Link>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
