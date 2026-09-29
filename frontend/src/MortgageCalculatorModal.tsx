import React, { useState } from "react";
import { calculateInstallment } from "./financingMath.mjs";
import { useNativeDialog } from "./useNativeDialog";

type Property = {
  id: string;
  title: string;
  city: string;
  area: string;
  price_pkr: number;
  available: boolean;
};

type MortgageCalculatorModalProps = {
  property?: Property | null;
  onClose: () => void;
  onBookConsultation: (propertyId?: string) => void;
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
  return `PKR ${Math.round(price).toLocaleString()}`;
}

export function MortgageCalculatorModal({ property, onClose, onBookConsultation }: MortgageCalculatorModalProps) {
  const dialogRef = useNativeDialog(true);
  const [price, setPrice] = useState<number>(property?.price_pkr ?? 0);
  const [downPaymentPct, setDownPaymentPct] = useState<number>(25);
  const [tenureYears, setTenureYears] = useState<number>(5);
  const [annualRate, setAnnualRate] = useState<number>(14.5);

  const estimate = calculateInstallment(price, downPaymentPct, tenureYears, annualRate);
  const { downPaymentAmount, loanPrincipal, monthlyInstallment, totalInterest, totalMonths, totalPaid } = estimate;

  return (
    <dialog
      ref={dialogRef}
      className="orbit-native-modal"
      aria-labelledby="installment-estimate-title"
      onCancel={(event) => { event.preventDefault(); onClose(); }}
      onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <section className="mortgage-calc-window">
        <header className="calc-header">
          <div className="calc-header-title">
                <span className="calc-accent-pill">ESTIMATE</span>
            <div>
              <h3 id="installment-estimate-title">Monthly installment estimate</h3>
              <span className="calc-subtext">Calculated from the property price and assumptions below.</span>
            </div>
          </div>
          <button type="button" className="calc-close-btn" onClick={onClose} aria-label="Close calculator">×</button>
        </header>

        <div className="calc-body-grid">
          <div className="calc-inputs-col">
            {property && (
              <div className="calc-selected-prop-card">
                <span className="prop-badge">{property.id}</span>
                <span className="prop-name">{property.title}</span>
                <span className="prop-geo">{property.area}, {property.city}</span>
                {!property.available && <span className="availability-badge unavailable">Unavailable</span>}
              </div>
            )}

            <div className="calc-form-group">
              <label htmlFor="calc-property-price">Property price (PKR)</label>
              <div className="calc-input-row">
                <input
                  id="calc-property-price"
                  type="number"
                  className="calc-text-input"
                  min="0"
                  max="5000000000"
                  value={price || ""}
                  onChange={(event) => setPrice(Math.max(0, Number(event.target.value) || 0))}
                  step="500000"
                  placeholder="Enter a property price"
                />
                {price > 0 && <span className="calc-formatted-preview">{formatPricePKR(price)}</span>}
              </div>
            </div>

            <div className="calc-form-group">
              <div className="label-row">
                <label>Down payment ({downPaymentPct}%)</label>
                {price > 0 && <span className="highlight-val">{formatPricePKR(downPaymentAmount)}</span>}
              </div>
              <div className="pct-btn-group">
                {[15, 20, 25, 30, 40, 50].map((pct) => (
                  <button key={pct} type="button" className={`pct-btn ${downPaymentPct === pct ? "active" : ""}`} onClick={() => setDownPaymentPct(pct)}>
                    {pct}%
                  </button>
                ))}
              </div>
            </div>

            <div className="calc-form-group">
              <div className="label-row">
                <label>Financing tenure ({tenureYears} years)</label>
                <span className="highlight-val">{totalMonths} installments</span>
              </div>
              <div className="pct-btn-group">
                {[3, 5, 7, 10, 15, 20].map((years) => (
                  <button key={years} type="button" className={`pct-btn ${tenureYears === years ? "active" : ""}`} onClick={() => setTenureYears(years)}>
                    {years} yrs
                  </button>
                ))}
              </div>
            </div>

            <div className="calc-form-group">
              <div className="label-row">
                <label htmlFor="calc-annual-rate">Assumed annual rate ({annualRate.toFixed(1)}%)</label>
                <span className="rda-tag">EDITABLE</span>
              </div>
              <input
                id="calc-annual-rate"
                type="range"
                className="calc-range-slider"
                min="0.5"
                max="30"
                step="0.5"
                value={annualRate}
                onChange={(event) => setAnnualRate(Number(event.target.value))}
              />
            </div>
          </div>

          <div className="calc-results-col">
            <div className="calc-summary-hero">
              <span className="hero-sub">ESTIMATED MONTHLY INSTALLMENT</span>
              <div className="hero-amount">
                {price > 0 ? formatPricePKR(monthlyInstallment) : "Enter a price"}
                {price > 0 && <span className="per-mo"> / month</span>}
              </div>
              {price > 0 && <span className="hero-duration">For {totalMonths} monthly installments</span>}
            </div>

            {price > 0 ? (
              <div className="calc-metrics-stack">
                <div className="calc-metric-row"><span className="metric-name">Down payment</span><span className="metric-val">{formatPricePKR(downPaymentAmount)}</span></div>
                <div className="calc-metric-row"><span className="metric-name">Financed principal</span><span className="metric-val">{formatPricePKR(loanPrincipal)}</span></div>
                <div className="calc-metric-row"><span className="metric-name">Estimated interest</span><span className="metric-val mark-val">{formatPricePKR(totalInterest)}</span></div>
                <div className="calc-metric-row total-row"><span className="metric-name">Estimated total paid</span><span className="metric-val total-val">{formatPricePKR(totalPaid)}</span></div>
              </div>
            ) : (
              <p className="calc-empty-hint">Enter a listing price, or open this calculator from a property card.</p>
            )}

            <p className="calc-disclaimer">Estimate only. Actual bank rates, fees, taxes, eligibility, and payment schedules must be confirmed with the lender and relevant authorities.</p>
            <button
              type="button"
              className="calc-consult-action"
              disabled={!property?.available}
              onClick={() => {
                if (!property?.available) return;
                onClose();
                onBookConsultation(property.id);
              }}
            >
              {property?.available ? "Request a visit for this listing" : "Select an available listing to request a visit"}
            </button>
          </div>
        </div>
      </section>
    </dialog>
  );
}
