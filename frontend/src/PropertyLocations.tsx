import React, { useMemo, useState } from "react";
import { availabilityLabel, canRequestVisit, filterAndSortProperties, inventorySourceLabel, shouldAutoOpenInventoryImport } from "./propertyFacts.mjs";
import { useNativeDialog } from "./useNativeDialog";
import { InventoryImportPanel } from "./InventoryImportPanel";
import { KnowledgeImportPanel } from "./KnowledgeImportPanel";

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
  available: boolean;
  source_version: string;
  source: string;
};

type PropertyLocationsProps = {
  properties: Property[];
  apiUrl: string;
  loadState: "loading" | "ready" | "error";
  onRetry: () => void;
  onImportComplete: () => void;
  onClose: () => void;
  onSelectProperty: (propertyId: string) => void;
  onBook: (propertyId: string) => void;
};

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

export function PropertyLocations({ properties, apiUrl, loadState, onRetry, onImportComplete, onClose, onSelectProperty, onBook }: PropertyLocationsProps) {
  const dialogRef = useNativeDialog(true);
  const [selectedCity, setSelectedCity] = useState("all");
  const [selectedArea, setSelectedArea] = useState("all");
  const [selectedPurpose, setSelectedPurpose] = useState("all");
  const [maximumPrice, setMaximumPrice] = useState("");
  const [selectedBedrooms, setSelectedBedrooms] = useState("all");
  const [sortOrder, setSortOrder] = useState<"price_ascending" | "price_descending">("price_ascending");
  const [selectedPropertyId, setSelectedPropertyId] = useState<string | null>(null);
  const cities = useMemo(() => [...new Set(properties.map((property) => property.city))].sort(), [properties]);
  const purposes = useMemo(() => [...new Set(properties.map((property) => property.purpose))].sort(), [properties]);
  const bedroomCounts = useMemo(() => [...new Set(properties
    .map((property) => property.bedrooms)
    .filter((bedrooms) => bedrooms > 0))].sort((left, right) => left - right), [properties]);
  const areas = useMemo(
    () => [...new Set(properties
      .filter((property) => selectedCity === "all" || property.city === selectedCity)
      .map((property) => property.area))].sort(),
    [properties, selectedCity],
  );
  const filteredProperties = useMemo(() => filterAndSortProperties(properties, {
    city: selectedCity,
    area: selectedArea,
    purpose: selectedPurpose,
    maxPricePkr: maximumPrice === "" ? undefined : Number(maximumPrice),
    bedrooms: selectedBedrooms === "all" ? undefined : Number(selectedBedrooms),
    sortOrder,
  }), [properties, selectedCity, selectedArea, selectedPurpose, maximumPrice, selectedBedrooms, sortOrder]);

  function formatPurpose(purpose: string): string {
    return purpose.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  return (
    <dialog
      ref={dialogRef}
      className="orbit-native-modal"
      aria-labelledby="location-browser-title"
      onCancel={(event) => { event.preventDefault(); onClose(); }}
      onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <section className="location-browser-window">
        <header className="location-browser-header">
          <div>
            <p className="location-browser-eyebrow">AVAILABLE INVENTORY</p>
            <h2 id="location-browser-title">Browse by location</h2>
            <p>City and area are taken from imported property records.</p>
          </div>
          <button type="button" className="location-browser-close" onClick={onClose} aria-label="Close location browser">×</button>
        </header>

        <div className="location-filters" role="group" aria-label="Filter and sort company inventory">
          <label>
            <span>City</span>
            <select value={selectedCity} onChange={(event) => {
              setSelectedCity(event.target.value);
              setSelectedArea("all");
            }}>
              <option value="all">All cities</option>
              {cities.map((city) => <option key={city} value={city}>{city}</option>)}
            </select>
          </label>
          <label>
            <span>Area</span>
            <select value={selectedArea} onChange={(event) => setSelectedArea(event.target.value)}>
              <option value="all">All areas</option>
              {areas.map((area) => <option key={area} value={area}>{area}</option>)}
            </select>
          </label>
          <label>
            <span>Purpose</span>
            <select value={selectedPurpose} onChange={(event) => setSelectedPurpose(event.target.value)}>
              <option value="all">All purposes</option>
              {purposes.map((purpose) => <option key={purpose} value={purpose}>{formatPurpose(purpose)}</option>)}
            </select>
          </label>
          <label>
            <span>Bedrooms</span>
            <select value={selectedBedrooms} onChange={(event) => setSelectedBedrooms(event.target.value)}>
              <option value="all">Any bedrooms</option>
              {bedroomCounts.map((bedrooms) => <option key={bedrooms} value={bedrooms}>{bedrooms} bedrooms</option>)}
            </select>
          </label>
          <label>
            <span>Maximum price (PKR)</span>
            <input
              type="number"
              min="0"
              step="100000"
              inputMode="numeric"
              value={maximumPrice}
              onChange={(event) => setMaximumPrice(event.target.value)}
              placeholder="No limit"
              aria-label="Maximum price in Pakistani rupees"
            />
          </label>
          <label>
            <span>Sort by price</span>
            <select value={sortOrder} onChange={(event) => setSortOrder(event.target.value as typeof sortOrder)}>
              <option value="price_ascending">Lowest first</option>
              <option value="price_descending">Highest first</option>
            </select>
          </label>
          <span className="location-result-count" aria-live="polite">
            {filteredProperties.length} {filteredProperties.length === 1 ? "listing" : "listings"}
          </span>
        </div>

        <InventoryImportPanel
          apiUrl={apiUrl}
          onImportComplete={onImportComplete}
          autoOpen={shouldAutoOpenInventoryImport(loadState, properties.length)}
        />
        <KnowledgeImportPanel apiUrl={apiUrl} />

        {filteredProperties.length > 0 ? (
          <div className="location-list" role="list">
            {filteredProperties.map((property) => {
              const selected = property.id === selectedPropertyId;
              return (
                <article key={property.id} className={`location-listing ${selected ? "selected" : ""}`} role="listitem">
                  <button
                    type="button"
                    className="location-listing-select"
                    onClick={() => {
                      setSelectedPropertyId(property.id);
                      onSelectProperty(property.id);
                    }}
                    aria-pressed={selected}
                  >
                    <span className="location-listing-heading">
                      <strong>{property.title}</strong>
                      <span className={`availability-badge ${property.available ? "available" : "unavailable"}`}>
                        {availabilityLabel(property.available)}
                      </span>
                    </span>
                    <span className="location-listing-meta">{property.area}, {property.city} · {property.purpose}</span>
                    <span className="location-listing-price">{formatPricePKR(property.price_pkr)}</span>
                    <span className="location-listing-meta">
                      {property.bedrooms > 0 ? `${property.bedrooms} bedrooms` : "Commercial"} · {property.size_sqft.toLocaleString()} sq ft
                    </span>
                    <span className="prop-source">
                      {inventorySourceLabel(property.source, property.source_version)}
                    </span>
                  </button>
                  <button
                    type="button"
                    className="inspector-book-btn"
                    disabled={!canRequestVisit(property)}
                    onClick={() => {
                      onClose();
                      onBook(property.id);
                    }}
                  >
                    {property.available ? "Request a visit" : "Unavailable"}
                  </button>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="location-empty-state" role="status">
            {loadState === "loading"
              ? "Loading property inventory…"
              : loadState === "error"
                ? "Could not load property inventory. Check that the backend is running, then retry."
                : properties.length === 0
                  ? "No company listings have been imported yet. Import inventory to browse real availability."
                  : "No listings match this location filter."}
            {loadState === "error" && (
              <button type="button" className="inspector-book-btn" onClick={onRetry}>Retry inventory request</button>
            )}
          </div>
        )}
      </section>
    </dialog>
  );
}
