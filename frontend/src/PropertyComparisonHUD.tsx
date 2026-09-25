import React from "react";

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
  if (sqft >= 4500) {
    return `${(sqft / 4500).toFixed(1)} Kanal`;
  }
  return `${(sqft / 225).toFixed(1)} Marla`;
}

function getNocStatus(area: string): { status: string; authority: string } {
  const a = area.toLowerCase();
  if (a.includes("clifton")) return { status: "SBCA APPROVED", authority: "Sindh Building Control Authority" };
  if (a.includes("dha")) return { status: "DHA APPROVED", authority: "Defence Housing Authority / Cantonment" };
  if (a.includes("gulberg")) return { status: "LDA APPROVED", authority: "Lahore Development Authority" };
  if (a.includes("blue area") || a.includes("f-11")) return { status: "CDA APPROVED", authority: "Capital Development Authority" };
  return { status: "VERIFIED CLEAR TITLE", authority: "Local Land Registry & Town Planning" };
}

export function PropertyComparisonHUD({ properties, onClose, onBook }: PropertyComparisonHUDProps) {
  if (!properties || properties.length === 0) return null;

  return (
    <div className="orbit-modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Property Comparison HUD">
      <div className="compare-hud-window" onClick={(e) => e.stopPropagation()}>
        <div className="compare-hud-header">
          <div className="compare-header-title">
            <span className="compare-pulse-dot" />
            <h3>Side-by-Side Verified Property Comparison HUD</h3>
            <span className="compare-badge">{properties.length} Properties Selected</span>
          </div>
          <button type="button" className="compare-close-btn" onClick={onClose} aria-label="Close Comparison">
            ✕
          </button>
        </div>

        <div className="compare-grid-container">
          <table className="compare-table">
            <thead>
              <tr>
                <th className="feature-col">Property Metric</th>
                {properties.map((p) => (
                  <th key={p.id} className="prop-col">
                    <span className="prop-col-id">{p.id}</span>
                    <h4 className="prop-col-title">{p.title}</h4>
                    <span className="prop-col-geo">{p.area}, {p.city}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="feature-name">Total Price</td>
                {properties.map((p) => (
                  <td key={p.id} className="feature-val price-val">
                    {formatPricePKR(p.price_pkr)}
                  </td>
                ))}
              </tr>

              <tr>
                <td className="feature-name">Price / Sq Ft</td>
                {properties.map((p) => {
                  const ppsf = Math.round(p.price_pkr / Math.max(p.size_sqft, 1));
                  return (
                    <td key={p.id} className="feature-val">
                      PKR {ppsf.toLocaleString()} / sq ft
                    </td>
                  );
                })}
              </tr>

              <tr>
                <td className="feature-name">Size & Land Unit</td>
                {properties.map((p) => (
                  <td key={p.id} className="feature-val">
                    <strong>{p.size_sqft.toLocaleString()} sq ft</strong>
                    <div className="sub-unit">({getMarlaEquivalent(p.size_sqft)})</div>
                  </td>
                ))}
              </tr>

              <tr>
                <td className="feature-name">Layout & Beds</td>
                {properties.map((p) => (
                  <td key={p.id} className="feature-val">
                    {p.bedrooms > 0 ? `${p.bedrooms} Bedrooms` : "Commercial Open Plan"}
                  </td>
                ))}
              </tr>

              <tr>
                <td className="feature-name">Investment Purpose</td>
                {properties.map((p) => (
                  <td key={p.id} className="feature-val">
                    <span className="purpose-tag">{p.purpose.toUpperCase()}</span>
                  </td>
                ))}
              </tr>

              <tr>
                <td className="feature-name">Estimated Rental Yield</td>
                {properties.map((p) => {
                  const yieldPct = p.city === "Karachi" ? "5.8% - 6.5%" : p.city === "Islamabad" ? "6.0% - 7.0%" : "4.8% - 5.5%";
                  return (
                    <td key={p.id} className="feature-val yield-val">
                      {yieldPct} Gross ROI
                    </td>
                  );
                })}
              </tr>

              <tr>
                <td className="feature-name">Payment Schedule</td>
                {properties.map((p) => (
                  <td key={p.id} className="feature-val">
                    {p.payment_plan}
                  </td>
                ))}
              </tr>

              <tr>
                <td className="feature-name">Regulatory NOC Status</td>
                {properties.map((p) => {
                  const noc = getNocStatus(p.area);
                  return (
                    <td key={p.id} className="feature-val">
                      <span className="noc-verified-badge">{noc.status}</span>
                      <div className="noc-auth-text">{noc.authority}</div>
                    </td>
                  );
                })}
              </tr>

              <tr>
                <td className="feature-name">Assigned Consultant</td>
                {properties.map((p) => (
                  <td key={p.id} className="feature-val consultant-name">
                    {p.assigned_employee}
                  </td>
                ))}
              </tr>

              <tr>
                <td className="feature-name">Direct Action</td>
                {properties.map((p) => (
                  <td key={p.id} className="feature-val action-cell">
                    <button
                      type="button"
                      className="compare-book-btn"
                      onClick={() => {
                        onClose();
                        onBook(p.id);
                      }}
                    >
                      Book Site Tour
                    </button>
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
