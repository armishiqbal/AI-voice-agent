"use client";

import { useState } from "react";
import { formatPkrShort, price } from "@/lib/site";

interface HomeFinanceCalculatorProps {
  propertyPrice: number;
  propertyTitle: string;
  transactionType: "sale" | "rent";
  onInquireFinance?: () => void;
}

export function HomeFinanceCalculator({
  propertyPrice,
  propertyTitle,
  transactionType,
  onInquireFinance,
}: HomeFinanceCalculatorProps) {
  // If property is for rent, display a relevant rental affordability guideline
  if (transactionType === "rent") {
    const monthlyRent = propertyPrice;
    const recommendedIncome = monthlyRent * 3;

    return (
      <div className="finance-calculator-card">
        <div className="calc-header-strip">
          <div className="calc-title-box">
            <span className="calc-kicker">Executive Lease Advisory</span>
            <h3 className="calc-title">Rental Affordability Guideline</h3>
          </div>
          <span className="bank-partner-badge">Corporate Lease Terms</span>
        </div>

        <p className="calc-desc">
          For executive leasing in Islamabad &amp; Rawalpindi, corporate tenant guidelines recommend that monthly rent should not exceed 30–35% of gross verifiable household income.
        </p>

        <div className="calc-results-grid">
          <div className="result-tile highlight">
            <span className="tile-label">Monthly Lease Rate</span>
            <strong className="tile-val">{price(monthlyRent)}</strong>
            <span className="tile-sub">Per Month</span>
          </div>

          <div className="result-tile">
            <span className="tile-label">Recommended Monthly Income</span>
            <strong className="tile-val">{formatPkrShort(recommendedIncome)} PKR</strong>
            <span className="tile-sub">3x Monthly Rent Coverage</span>
          </div>

          <div className="result-tile">
            <span className="tile-label">Security Deposit Guideline</span>
            <strong className="tile-val">{formatPkrShort(monthlyRent * 3)} PKR</strong>
            <span className="tile-sub">Standard 3 Months Advance/Security</span>
          </div>
        </div>
      </div>
    );
  }

  // Sale Property Mortgage & Islamic Financing
  const [downPaymentPercent, setDownPaymentPercent] = useState<number>(30);
  const [tenureYears, setTenureYears] = useState<number>(15);
  const [profitRatePercent, setProfitRatePercent] = useState<number>(14.5);
  const [financeType, setFinanceType] = useState<"islamic" | "conventional">("islamic");

  const downPaymentAmount = (propertyPrice * downPaymentPercent) / 100;
  const loanAmount = Math.max(0, propertyPrice - downPaymentAmount);

  // Calculate Monthly Installment (EMI)
  const calculateEMI = () => {
    if (loanAmount <= 0) return 0;
    const monthlyRate = profitRatePercent / 100 / 12;
    const totalMonths = tenureYears * 12;
    if (monthlyRate === 0) return loanAmount / totalMonths;

    const emi =
      (loanAmount * monthlyRate * Math.pow(1 + monthlyRate, totalMonths)) /
      (Math.pow(1 + monthlyRate, totalMonths) - 1);
    return Math.round(emi);
  };

  const monthlyInstallment = calculateEMI();
  const totalRepayment = monthlyInstallment * tenureYears * 12;
  const totalProfit = Math.max(0, totalRepayment - loanAmount);
  const estimatedTaxStampDuty = Math.round(propertyPrice * 0.03); // 3% indicative for Filer stamp duty + FBR advance

  return (
    <div className="finance-calculator-card">
      <div className="calc-header-strip">
        <div className="calc-title-box">
          <span className="calc-kicker">Financial Planning</span>
          <h3 className="calc-title">Home Finance &amp; Mortgage Calculator</h3>
        </div>
        <div className="finance-toggle-group">
          <button
            type="button"
            className={`finance-toggle-btn ${financeType === "islamic" ? "active" : ""}`}
            onClick={() => {
              setFinanceType("islamic");
              setProfitRatePercent(14.5);
            }}
          >
            Islamic (Musharakah)
          </button>
          <button
            type="button"
            className={`finance-toggle-btn ${financeType === "conventional" ? "active" : ""}`}
            onClick={() => {
              setFinanceType("conventional");
              setProfitRatePercent(15.2);
            }}
          >
            Conventional
          </button>
        </div>
      </div>

      <p className="calc-desc">
        Calculate your indicative monthly installment based on prevailing financing rates from accredited partner banks including Meezan Bank, HBL Islamic, and Bank Alfalah.
      </p>

      {/* Interactive Sliders */}
      <div className="calc-controls-grid">
        {/* Down Payment */}
        <div className="calc-control-group">
          <div className="control-label-row">
            <span className="control-label">Down Payment ({downPaymentPercent}%)</span>
            <strong className="control-val">{formatPkrShort(downPaymentAmount)} PKR</strong>
          </div>
          <input
            type="range"
            min="15"
            max="60"
            step="5"
            value={downPaymentPercent}
            onChange={(e) => setDownPaymentPercent(Number(e.target.value))}
            className="calc-range-slider"
          />
          <div className="quick-presets-row">
            {[20, 30, 40, 50].map((pct) => (
              <button
                key={pct}
                type="button"
                className={`preset-pill ${downPaymentPercent === pct ? "active" : ""}`}
                onClick={() => setDownPaymentPercent(pct)}
              >
                {pct}%
              </button>
            ))}
          </div>
        </div>

        {/* Tenure */}
        <div className="calc-control-group">
          <div className="control-label-row">
            <span className="control-label">Financing Tenure</span>
            <strong className="control-val">{tenureYears} Years</strong>
          </div>
          <input
            type="range"
            min="5"
            max="25"
            step="1"
            value={tenureYears}
            onChange={(e) => setTenureYears(Number(e.target.value))}
            className="calc-range-slider"
          />
          <div className="quick-presets-row">
            {[5, 10, 15, 20, 25].map((yr) => (
              <button
                key={yr}
                type="button"
                className={`preset-pill ${tenureYears === yr ? "active" : ""}`}
                onClick={() => setTenureYears(yr)}
              >
                {yr} Yrs
              </button>
            ))}
          </div>
        </div>

        {/* Profit Rate */}
        <div className="calc-control-group">
          <div className="control-label-row">
            <span className="control-label">Annual Benchmark Rate</span>
            <strong className="control-val">{profitRatePercent.toFixed(1)}% p.a.</strong>
          </div>
          <input
            type="range"
            min="11"
            max="20"
            step="0.1"
            value={profitRatePercent}
            onChange={(e) => setProfitRatePercent(Number(e.target.value))}
            className="calc-range-slider"
          />
          <span className="calc-hint">
            {financeType === "islamic"
              ? "Based on Diminishing Musharakah (Rental + Unit Purchase)"
              : "Based on 1-Year KIBOR + Bank Margin spread"}
          </span>
        </div>
      </div>

      {/* Output Cards */}
      <div className="calc-results-grid">
        <div className="result-tile highlight">
          <span className="tile-label">Estimated Monthly Payment</span>
          <strong className="tile-val">{price(monthlyInstallment)}</strong>
          <span className="tile-sub">Per Month for {tenureYears} Years</span>
        </div>

        <div className="result-tile">
          <span className="tile-label">Principal Financing Required</span>
          <strong className="tile-val">{formatPkrShort(loanAmount)} PKR</strong>
          <span className="tile-sub">{100 - downPaymentPercent}% of Property Value</span>
        </div>

        <div className="result-tile">
          <span className="tile-label">Indicative FBR &amp; Stamp Duty</span>
          <strong className="tile-val">{formatPkrShort(estimatedTaxStampDuty)} PKR</strong>
          <span className="tile-sub">Approx. 3% for Active Tax Filers</span>
        </div>
      </div>

      <div className="calc-footer-action">
        <div className="bank-partner-logos">
          <span className="partner-label">Available through Accredited Mortgage Desks:</span>
          <span className="partner-tag">Meezan Bank</span>
          <span className="partner-tag">HBL Islamic</span>
          <span className="partner-tag">Bank Alfalah</span>
          <span className="partner-tag">Standard Chartered</span>
        </div>

        {onInquireFinance && (
          <button
            type="button"
            className="button primary finance-cta-btn"
            onClick={onInquireFinance}
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" style={{ marginRight: 8 }}>
              <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
            </svg>
            Inquire for Bank Pre-Approval
          </button>
        )}
      </div>
    </div>
  );
}
