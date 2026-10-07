"use client";

import { useState } from "react";

type AgencyInquiryFormProps = {
  targetName: string;
  targetType: "agency" | "advisor";
  contactPhone?: string | null;
  contactEmail?: string | null;
  whatsapp?: string | null;
};

export function AgencyInquiryForm({
  targetName,
  targetType,
  contactPhone,
  contactEmail,
  whatsapp,
}: AgencyInquiryFormProps) {
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [referenceId, setReferenceId] = useState("");
  const [formData, setFormData] = useState({
    fullName: "",
    phone: "",
    email: "",
    mandateType: "acquisition",
    sector: "All Sectors",
    budgetBracket: "50m_100m",
    confidentialNotes: "",
    ndaRequested: true,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);

    // Simulate verified dispatch
    setTimeout(() => {
      const randomCode = Math.floor(1000 + Math.random() * 9000);
      setReferenceId(`AWA-${targetName.slice(0, 3).toUpperCase()}-${randomCode}`);
      setSubmitting(false);
      setSubmitted(true);
    }, 700);
  };

  const cleanPhone = (phone?: string | null) => {
    if (!phone) return "";
    return phone.replace(/[^0-9]/g, "");
  };

  return (
    <div className="agency-inquiry-card">
      <div className="agency-inquiry-header">
        <div className="inquiry-header-badge">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            <path d="m9 12 2 2 4-4" />
          </svg>
          Direct Mandate Protocol
        </div>
        <h3 className="agency-inquiry-title">
          {targetType === "agency"
            ? `Engage ${targetName}`
            : `Consult With ${targetName}`}
        </h3>
        <p className="agency-inquiry-subtitle">
          Submit confidential acquisition, divestment, or due diligence instructions directly to senior partners.
        </p>
      </div>

      {submitted ? (
        <div className="inquiry-success-receipt" role="alert">
          <div className="inquiry-success-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>
          <h4 className="inquiry-success-title">Mandate Registered</h4>
          <p className="inquiry-success-desc">
            Your confidential brief has been logged with reference{" "}
            <strong>{referenceId}</strong>. A designated senior advisory partner from{" "}
            <strong>{targetName}</strong> will contact you within 4 business hours.
          </p>

          <div className="inquiry-direct-links">
            {whatsapp && (
              <a
                href={`https://wa.me/${cleanPhone(whatsapp)}?text=Ref%20${referenceId}:%20Inquiring%20about%20real%20estate%20mandate`}
                target="_blank"
                rel="noopener noreferrer"
                className="inquiry-wa-btn"
              >
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
                </svg>
                Connect on WhatsApp Desk
              </a>
            )}
            {contactPhone && (
              <a href={`tel:${contactPhone}`} className="inquiry-call-btn">
                Call Direct ({contactPhone})
              </a>
            )}
          </div>

          <button
            type="button"
            onClick={() => setSubmitted(false)}
            className="inquiry-reset-btn"
          >
            Submit Another Instruction
          </button>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="agency-inquiry-form">
          <div className="inquiry-form-grid">
            <div className="inquiry-field">
              <label htmlFor="inquiry-name" className="inquiry-label">
                Full Name <span className="req">*</span>
              </label>
              <input
                id="inquiry-name"
                type="text"
                required
                placeholder="e.g. Tariq Mehmood"
                value={formData.fullName}
                onChange={(e) => setFormData({ ...formData, fullName: e.target.value })}
                className="inquiry-input"
              />
            </div>

            <div className="inquiry-field">
              <label htmlFor="inquiry-phone" className="inquiry-label">
                Phone Number (WhatsApp) <span className="req">*</span>
              </label>
              <input
                id="inquiry-phone"
                type="tel"
                required
                placeholder="+92 300 1234567"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="inquiry-input"
              />
            </div>
          </div>

          <div className="inquiry-form-grid">
            <div className="inquiry-field">
              <label htmlFor="inquiry-email" className="inquiry-label">
                Email Address <span className="req">*</span>
              </label>
              <input
                id="inquiry-email"
                type="email"
                required
                placeholder="tariq@example.com"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="inquiry-input"
              />
            </div>

            <div className="inquiry-field">
              <label htmlFor="inquiry-type" className="inquiry-label">
                Mandate Type
              </label>
              <select
                id="inquiry-type"
                value={formData.mandateType}
                onChange={(e) => setFormData({ ...formData, mandateType: e.target.value })}
                className="inquiry-select"
              >
                <option value="acquisition">Private Asset Acquisition</option>
                <option value="divestment">Seller Representation / Divestment</option>
                <option value="commercial">Commercial Tower / Floor Lease</option>
                <option value="diligence">Title Due Diligence &amp; Verification</option>
              </select>
            </div>
          </div>

          <div className="inquiry-form-grid">
            <div className="inquiry-field">
              <label htmlFor="inquiry-sector" className="inquiry-label">
                Target Jurisdiction
              </label>
              <select
                id="inquiry-sector"
                value={formData.sector}
                onChange={(e) => setFormData({ ...formData, sector: e.target.value })}
                className="inquiry-select"
              >
                <option value="All Sectors">All Islamabad / Rawalpindi</option>
                <option value="DHA Phase 2">DHA Phase 2</option>
                <option value="Blue Area">Blue Area Financial Center</option>
                <option value="Gulberg Greens">Gulberg Greens Agro-Farmhouses</option>
                <option value="F-6 / F-7 / F-8">Sector F-6 / F-7 / F-8</option>
                <option value="F-10 / F-11">Sector F-10 / F-11</option>
                <option value="Bahria Town">Bahria Town Phase 7 / 8</option>
              </select>
            </div>

            <div className="inquiry-field">
              <label htmlFor="inquiry-budget" className="inquiry-label">
                Estimated Capital Allocation
              </label>
              <select
                id="inquiry-budget"
                value={formData.budgetBracket}
                onChange={(e) => setFormData({ ...formData, budgetBracket: e.target.value })}
                className="inquiry-select"
              >
                <option value="under_50m">Under PKR 50 Million</option>
                <option value="50m_100m">PKR 50 Million – PKR 100 Million</option>
                <option value="100m_250m">PKR 100 Million – PKR 250 Million</option>
                <option value="above_250m">PKR 250 Million+ (Institutional)</option>
              </select>
            </div>
          </div>

          <div className="inquiry-field">
            <label htmlFor="inquiry-notes" className="inquiry-label">
              Confidential Instruction / Specific Requirements
            </label>
            <textarea
              id="inquiry-notes"
              rows={3}
              placeholder="Outline specific property criteria, plot size, floor preferences, or legal covenants..."
              value={formData.confidentialNotes}
              onChange={(e) => setFormData({ ...formData, confidentialNotes: e.target.value })}
              className="inquiry-textarea"
            />
          </div>

          <div className="inquiry-checkbox-row">
            <label className="inquiry-checkbox-label">
              <input
                type="checkbox"
                checked={formData.ndaRequested}
                onChange={(e) => setFormData({ ...formData, ndaRequested: e.target.checked })}
              />
              <span>Request confidential non-disclosure execution prior to site inspections</span>
            </label>
          </div>

          <div className="inquiry-submit-row">
            <button
              type="submit"
              disabled={submitting}
              className="inquiry-submit-btn"
            >
              {submitting ? (
                <span>Dispatching Mandate...</span>
              ) : (
                <>
                  <span>Dispatch Mandate to {targetName}</span>
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <line x1="5" y1="12" x2="19" y2="12" />
                    <polyline points="12 5 19 12 12 19" />
                  </svg>
                </>
              )}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
