import React, { useState } from "react";

type Property = {
  id: string;
  title: string;
  city: string;
  area: string;
  price_pkr: number;
  bedrooms: number;
  size_sqft: number;
  purpose: string;
  amenities: string[];
  payment_plan: string;
  assigned_employee: string;
  source?: string;
};

type PropertyMapRadarProps = {
  properties: Property[];
  onClose: () => void;
  onSelectProperty: (propertyId: string) => void;
  onBook: (propertyId: string) => void;
};

type CityKey = "all" | "Karachi" | "Lahore" | "Islamabad";

const CITY_COORDINATES: Record<string, { lat: number; lng: number; zoom: number; desc: string }> = {
  Karachi: { lat: 24.82, lng: 67.04, zoom: 12, desc: "Clifton & DHA Coastal Prime Zone" },
  Lahore: { lat: 31.49, lng: 74.38, zoom: 12, desc: "DHA & Gulberg Central Metropolitan" },
  Islamabad: { lat: 33.70, lng: 73.04, zoom: 12, desc: "Margalla Foothills & Blue Area Hub" },
};

const LOCALITY_OFFSETS: Record<string, { x: number; y: number }> = {
  clifton: { x: 35, y: 65 },
  dha: { x: 55, y: 72 },
  gulberg: { x: 48, y: 42 },
  "blue area": { x: 52, y: 38 },
  "f-11": { x: 38, y: 45 },
  bahria: { x: 68, y: 58 },
};

function getMarlaEquivalent(sqft: number): string {
  if (sqft >= 4500) {
    return `${(sqft / 4500).toFixed(1).replace(/\.0$/, "")} Kanal`;
  }
  return `${(sqft / 225).toFixed(1).replace(/\.0$/, "")} Marla`;
}

function formatPricePKR(price: number): string {
  if (price >= 10_000_000) {
    const crore = (price / 10_000_000).toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
    return `PKR ${crore} Crore`;
  }
  if (price >= 100_000) {
    const lakh = (price / 100_000).toFixed(1).replace(/\.0$/, "");
    return `PKR ${lakh} Lakh`;
  }
  return `PKR ${price.toLocaleString()}`;
}

export function PropertyMapRadar({ properties, onClose, onSelectProperty, onBook }: PropertyMapRadarProps) {
  const [selectedCity, setSelectedCity] = useState<CityKey>("all");
  const [activePinId, setActivePinId] = useState<string | null>(properties[0]?.id || null);

  const filteredProperties = properties.filter((p) => {
    if (selectedCity === "all") return true;
    return p.city.toLowerCase() === selectedCity.toLowerCase();
  });

  const activeProp = properties.find((p) => p.id === activePinId) || filteredProperties[0] || null;

  return (
    <div className="orbit-modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Geospatial Map Radar">
      <div className="map-radar-window" onClick={(e) => e.stopPropagation()}>
        <div className="radar-top-bar">
          <div className="radar-title-wrap">
            <span className="radar-live-beacon" />
            <div>
              <h3>Awaaz Geospatial Property Radar HUD</h3>
              <span className="radar-subtext">Verified Real Estate Clusters across Pakistan</span>
            </div>
          </div>

          <div className="city-filter-pills">
            {(["all", "Karachi", "Lahore", "Islamabad"] as CityKey[]).map((city) => (
              <button
                key={city}
                type="button"
                className={`city-pill ${selectedCity === city ? "active" : ""}`}
                onClick={() => setSelectedCity(city)}
              >
                {city === "all" ? "All Pakistan" : city}
              </button>
            ))}
          </div>

          <button type="button" className="radar-close-btn" onClick={onClose} aria-label="Close Radar">
            ✕
          </button>
        </div>

        <div className="radar-stage-grid">
          {/* Main Visual Cyberpunk Radar Screen */}
          <div className="radar-screen-wrap">
            <div className="radar-sweep-scanner" />
            <div className="radar-grid-lines" />
            <div className="radar-rings">
              <div className="radar-ring ring-1" />
              <div className="radar-ring ring-2" />
              <div className="radar-ring ring-3" />
            </div>

            {/* Coordinates HUD overlay */}
            <div className="radar-coords-hud">
              <span>LAT: {selectedCity !== "all" ? CITY_COORDINATES[selectedCity].lat : "24.8607° N"}</span>
              <span>LNG: {selectedCity !== "all" ? CITY_COORDINATES[selectedCity].lng : "67.0011° E"}</span>
              <span className="radar-target-tag">{filteredProperties.length} CLUSTERS LOCKED</span>
            </div>

            {/* Property Pins scattered across Radar screen */}
            {filteredProperties.map((p, idx) => {
              const lower = (p.area + " " + p.title).toLowerCase();
              let coords = { x: 30 + ((idx * 27) % 55), y: 25 + ((idx * 33) % 55) };
              for (const [key, pos] of Object.entries(LOCALITY_OFFSETS)) {
                if (lower.includes(key)) {
                  coords = {
                    x: Math.min(85, Math.max(15, pos.x + ((idx % 3) * 6 - 6))),
                    y: Math.min(85, Math.max(15, pos.y + ((idx % 2) * 6 - 3))),
                  };
                  break;
                }
              }

              const isSelected = p.id === activePinId;

              return (
                <div
                  key={p.id}
                  className={`radar-pin-marker ${isSelected ? "selected" : ""}`}
                  style={{ left: `${coords.x}%`, top: `${coords.y}%` }}
                  onClick={() => {
                    setActivePinId(p.id);
                    onSelectProperty(p.id);
                  }}
                  title={`${p.title} - ${formatPricePKR(p.price_pkr)}`}
                >
                  <div className="pin-pulse" />
                  <div className="pin-core">
                    <span className="pin-dot" />
                    <span className="pin-label">{p.area.split(" ")[0]}</span>
                  </div>
                  <div className="pin-price-tag">{formatPricePKR(p.price_pkr)}</div>
                </div>
              );
            })}
          </div>

          {/* Side Info Inspector Panel */}
          <div className="radar-inspector-panel">
            {activeProp ? (
              <div className="inspector-card">
                <div className="inspector-header">
                  <span className="inspector-badge">{activeProp.city.toUpperCase()} CLUSTER</span>
                  <span className="inspector-noc">✓ SBCA / LDA VERIFIED</span>
                </div>

                <h4 className="inspector-title">{activeProp.title}</h4>
                <div className="inspector-geo">{activeProp.area}, {activeProp.city}</div>
                <div className="inspector-price">{formatPricePKR(activeProp.price_pkr)}</div>

                <div className="inspector-specs-grid">
                  <div className="spec-box">
                    <span className="spec-lbl">Land Area</span>
                    <strong className="spec-val">{getMarlaEquivalent(activeProp.size_sqft)}</strong>
                    <span className="spec-sub">({activeProp.size_sqft.toLocaleString()} sq ft)</span>
                  </div>
                  <div className="spec-box">
                    <span className="spec-lbl">Bedrooms</span>
                    <strong className="spec-val">{activeProp.bedrooms > 0 ? `${activeProp.bedrooms} Bed` : "Commercial"}</strong>
                    <span className="spec-sub">Architectural Layout</span>
                  </div>
                  <div className="spec-box">
                    <span className="spec-lbl">Payment Plan</span>
                    <strong className="spec-val">{activeProp.payment_plan}</strong>
                    <span className="spec-sub">Verified Developer</span>
                  </div>
                  <div className="spec-box">
                    <span className="spec-lbl">Consultant</span>
                    <strong className="spec-val">{activeProp.assigned_employee}</strong>
                    <span className="spec-sub">Awaaz Prime Agent</span>
                  </div>
                </div>

                <div className="inspector-actions">
                  <button
                    type="button"
                    className="inspector-book-btn"
                    onClick={() => {
                      onClose();
                      onBook(activeProp.id);
                    }}
                  >
                    Schedule On-Site Tour
                  </button>
                </div>
              </div>
            ) : (
              <div className="inspector-empty">Select any radar pin to inspect property coordinates.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
