import React from "react";
import { availabilityLabel, canRequestVisit, inventorySourceLabel } from "./propertyFacts.mjs";
import { useNativeDialog } from "./useNativeDialog";

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

type PropertyComparisonHUDProps = {
  properties: Property[];
  onClose: () => void;
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

function getMarlaEquivalent(sqft: number): string {
  return sqft >= 4_500
    ? `${(sqft / 4_500).toFixed(1).replace(/\.0$/, "")} Kanal`
    : `${(sqft / 225).toFixed(1).replace(/\.0$/, "")} Marla`;
}

function PropertyValue({ children }: { children: React.ReactNode }) {
  return <td className="feature-val">{children}</td>;
}

export function PropertyComparisonHUD({ properties, onClose, onBook }: PropertyComparisonHUDProps) {
  const dialogRef = useNativeDialog(true);
  if (!properties.length) return null;

  return (
    <dialog
      ref={dialogRef}
      className="orbit-native-modal"
      aria-labelledby="compare-listings-title"
      onCancel={(event) => { event.preventDefault(); onClose(); }}
      onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <section className="compare-hud-window">
        <header className="compare-hud-header">
          <div className="compare-header-title">
            <span className="compare-pulse-dot" />
            <h3 id="compare-listings-title">Compare property listings</h3>
            <span className="compare-badge">{properties.length} selected</span>
          </div>
          <button type="button" className="compare-close-btn" onClick={onClose} aria-label="Close comparison">×</button>
        </header>

        <div className="compare-grid-container">
          <table className="compare-table">
            <thead>
              <tr>
                <th className="feature-col">Listing detail</th>
                {properties.map((property) => (
                  <th key={property.id} className="prop-col">
                    <span className="prop-col-id">{property.id}</span>
                    <h4 className="prop-col-title">{property.title}</h4>
                    <span className="prop-col-geo">{property.area}, {property.city}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="feature-name">Price</td>
                {properties.map((property) => <PropertyValue key={property.id}>{formatPricePKR(property.price_pkr)}</PropertyValue>)}
              </tr>
              <tr>
                <td className="feature-name">Price per sq ft (calculated)</td>
                {properties.map((property) => (
                  <PropertyValue key={property.id}>PKR {Math.round(property.price_pkr / property.size_sqft).toLocaleString()} / sq ft</PropertyValue>
                ))}
              </tr>
              <tr>
                <td className="feature-name">Size</td>
                {properties.map((property) => (
                  <PropertyValue key={property.id}>{property.size_sqft.toLocaleString()} sq ft · {getMarlaEquivalent(property.size_sqft)}</PropertyValue>
                ))}
              </tr>
              <tr>
                <td className="feature-name">Purpose and bedrooms</td>
                {properties.map((property) => (
                  <PropertyValue key={property.id}>{property.purpose} · {property.bedrooms > 0 ? `${property.bedrooms} bedrooms` : "Commercial"}</PropertyValue>
                ))}
              </tr>
              <tr>
                <td className="feature-name">Payment plan</td>
                {properties.map((property) => <PropertyValue key={property.id}>{property.payment_plan || "Not provided"}</PropertyValue>)}
              </tr>
              <tr>
                <td className="feature-name">Availability</td>
                {properties.map((property) => (
                  <PropertyValue key={property.id}>
                    <span className={`availability-badge ${property.available ? "available" : "unavailable"}`}>
                      {availabilityLabel(property.available)}
                    </span>
                  </PropertyValue>
                ))}
              </tr>
              <tr>
                <td className="feature-name">Inventory source</td>
                {properties.map((property) => (
                  <PropertyValue key={property.id}>
                    {inventorySourceLabel(property.source, property.source_version)}
                  </PropertyValue>
                ))}
              </tr>
              <tr>
                <td className="feature-name">Assigned employee</td>
                {properties.map((property) => <PropertyValue key={property.id}>{property.assigned_employee || "Not assigned"}</PropertyValue>)}
              </tr>
              <tr>
                <td className="feature-name">Visit request</td>
                {properties.map((property) => (
                  <PropertyValue key={property.id}>
                    <button
                      type="button"
                      className="compare-book-btn"
                      disabled={!canRequestVisit(property)}
                      onClick={() => {
                        onClose();
                        onBook(property.id);
                      }}
                    >
                      {canRequestVisit(property) ? "Request a visit" : "Unavailable"}
                    </button>
                  </PropertyValue>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </dialog>
  );
}
