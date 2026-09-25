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
  const initialPrice = property?.price_pkr || 25_000_000;
  const [price, setPrice] = useState<number>(initialPrice);
  const [downPaymentPct, setDownPaymentPct] = useState<number>(25);
  const [tenureYears, setTenureYears] = useState<number>(5);
  const [isRDA, setIsRDA] = useState<boolean>(false);
  const [interestRate, setInterestRate] = useState<number>(14.5);
  const [isFiler, setIsFiler] = useState<boolean>(true);

  // Roshan Apna Ghar subsidized rate calculation
  const effectiveRate = isRDA ? Math.min(interestRate, 12.5) : interestRate;

  const downPaymentAmount = (price * downPaymentPct) / 100;
  const loanPrincipal = price - downPaymentAmount;

  const monthlyRate = effectiveRate / 100 / 12;
  const totalMonths = tenureYears * 12;

  let monthlyInstallment = 0;
  if (monthlyRate > 0 && totalMonths > 0) {
    monthlyInstallment =
      (loanPrincipal * monthlyRate * Math.pow(1 + monthlyRate, totalMonths)) /
      (Math.pow(1 + monthlyRate, totalMonths) - 1);
  } else if (totalMonths > 0) {
    monthlyInstallment = loanPrincipal / totalMonths;
  }

  const totalRepayment = monthlyInstallment * totalMonths;
  const totalInterest = Math.max(0, totalRepayment - loanPrincipal);

  // FBR Section 236K Advance Tax on Purchase
  const fbrTaxRate = isFiler ? 0.03 : price > 100_000_000 ? 0.15 : 0.105;
  const fbrTaxAmount = price * fbrTaxRate;

  return (
    <div className="orbit-modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Mortgage & Financing Calculator">
      <div className="mortgage-calc-window" onClick={(e) => e.stopPropagation()}>
        <div className="calc-header">
          <div className="calc-header-title">
            <span className="calc-accent-pill">FINANCE HUD</span>
            <div>
              <h3>Pakistani Real Estate Mortgage & Installment Calculator</h3>
              <span className="calc-subtext">SBP KIBOR + Bank Spread & Roshan Digital Account (RDA)</span>
            </div>
          </div>
          <button type="button" className="calc-close-btn" onClick={onClose} aria-label="Close Calculator">✕</button>
        </div>

        <div className="calc-body-grid">
          {/* Inputs Section */}
          <div className="calc-inputs-col">
            {property && (
              <div className="calc-selected-prop-card">
                <span className="prop-badge">{property.id}</span>
                <span className="prop-name">{property.title}</span>
                <span className="prop-geo">{property.area}, {property.city}</span>
              </div>
            )}

            <div className="calc-form-group">
              <label>Property Value (PKR)</label>
              <div className="calc-input-row">
                <input
                  type="number"
                  className="calc-text-input"
                  value={price}
                  onChange={(e) => setPrice(Math.max(100_000, Number(e.target.value) || 0))}
                  step="500000"
                />
                <span className="calc-formatted-preview">{formatPricePKR(price)}</span>
              </div>
            </div>

            <div className="calc-form-group">
              <div className="label-row">
                <label>Down Payment ({downPaymentPct}%)</label>
                <span className="highlight-val">{formatPricePKR(downPaymentAmount)}</span>
              </div>
              <div className="pct-btn-group">
                {[15, 20, 25, 30, 40, 50].map((pct) => (
                  <button
                    key={pct}
                    type="button"
                    className={`pct-btn ${downPaymentPct === pct ? "active" : ""}`}
                    onClick={() => setDownPaymentPct(pct)}
                  >
                    {pct}%
                  </button>
                ))}
              </div>
            </div>

            <div className="calc-form-group">
              <div className="label-row">
                <label>Financing Tenure ({tenureYears} Years)</label>
                <span className="highlight-val">{tenureYears * 12} Monthly Installments</span>
              </div>
              <div className="pct-btn-group">
                {[3, 5, 7, 10, 15, 20].map((yrs) => (
                  <button
                    key={yrs}
                    type="button"
                    className={`pct-btn ${tenureYears === yrs ? "active" : ""}`}
                    onClick={() => setTenureYears(yrs)}
                  >
                    {yrs} Yrs
                  </button>
                ))}
              </div>
            </div>

            <div className="calc-form-group">
              <div className="label-row">
                <label>Annual Markup / KIBOR Rate ({effectiveRate.toFixed(1)}%)</label>
                {isRDA && <span className="rda-tag">RDA SUBSIDY APPLIED</span>}
              </div>
              <input
                type="range"
                className="calc-range-slider"
                min="10.0"
                max="22.0"
                step="0.5"
                value={interestRate}
                onChange={(e) => setInterestRate(parseFloat(e.target.value))}
              />
            </div>

            <div className="calc-toggle-row">
              <label className="toggle-label">
                <input
                  type="checkbox"
                  checked={isRDA}
                  onChange={(e) => setIsRDA(e.target.checked)}
                />
                <span>Roshan Digital Account (Overseas Pakistani Scheme)</span>
              </label>

              <label className="toggle-label">
                <input
                  type="checkbox"
                  checked={isFiler}
                  onChange={(e) => setIsFiler(e.target.checked)}
                />
                <span>Active FBR Tax Filer (ATL Verified)</span>
              </label>
            </div>
          </div>

          {/* Results Summary Card */}
          <div className="calc-results-col">
            <div className="calc-summary-hero">
              <span className="hero-sub">ESTIMATED MONTHLY INSTALLMENT</span>
              <div className="hero-amount">{formatPricePKR(monthlyInstallment)} <span className="per-mo">/ month</span></div>
              <span className="hero-duration">For {totalMonths} consecutive months</span>
            </div>

            <div className="calc-metrics-stack">
              <div className="calc-metric-row">
                <span className="metric-name">Down Payment Required</span>
                <span className="metric-val">{formatPricePKR(downPaymentAmount)}</span>
              </div>
              <div className="calc-metric-row">
                <span className="metric-name">Bank Financed Principal</span>
                <span className="metric-val">{formatPricePKR(loanPrincipal)}</span>
              </div>
              <div className="calc-metric-row">
                <span className="metric-name">Total Markup / Bank Profit</span>
                <span className="metric-val mark-val">{formatPricePKR(totalInterest)}</span>
              </div>
              <div className="calc-metric-row">
                <span className="metric-name">FBR Section 236K Tax ({isFiler ? "Filer 3%" : "Non-Filer 10.5%"})</span>
                <span className="metric-val tax-val">{formatPricePKR(fbrTaxAmount)}</span>
              </div>
              <div className="calc-metric-row total-row">
                <span className="metric-name">Total Acquisition Outlay</span>
                <span className="metric-val total-val">{formatPricePKR(downPaymentAmount + totalRepayment + fbrTaxAmount)}</span>
              </div>
            </div>

            <button
              type="button"
              className="calc-consult-action"
              onClick={() => {
                onClose();
                onBookConsultation(property?.id);
              }}
            >
              Book Advisory Consultation with Verified Broker
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
