import Link from "next/link";

export function AdvisoryCovenantSection() {
  return (
    <div className="covenant-section-luxury">
      <div className="covenant-section-header">
        <span className="section-eyebrow">Institutional Transparency</span>
        <h2 className="covenant-section-title">The Awaaz Estate Verification Standard</h2>
        <p className="covenant-section-sub">
          Unlike unvetted classifieds portals, Awaaz Estate operates under strict evidence-based protocols to protect buyers, tenants, and overseas investors.
        </p>
      </div>

      <div className="covenant-cards-grid">
        <div className="covenant-feature-card">
          <div className="covenant-icon-box" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
              <circle cx="12" cy="13" r="4" />
            </svg>
          </div>
          <h3 className="covenant-card-title">Physical On-Ground Audits</h3>
          <p className="covenant-card-desc">
            Every published property is physically surveyed by our property inspection engineers. Photographs and specs reflect verified on-site conditions.
          </p>
        </div>

        <div className="covenant-feature-card">
          <div className="covenant-icon-box" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>
          </div>
          <h3 className="covenant-card-title">Title &amp; Civic Documentation Scrutiny</h3>
          <p className="covenant-card-desc">
            Allotment records and civic documentation are scrutinized against official development authority registers, with individual review scopes published for complete buyer transparency.
          </p>
        </div>

        <div className="covenant-feature-card">
          <div className="covenant-icon-box" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2">
              <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
          </div>
          <h3 className="covenant-card-title">Direct Client Privacy</h3>
          <p className="covenant-card-desc">
            We never distribute or sell inquiry data to third-party commission brokers. All interactions are handled directly by our licensed advisory team.
          </p>
        </div>
      </div>

      {/* Direct Company Contacts Panel */}
      <div className="covenant-contacts-card">
        <div className="contacts-card-header">
          <div>
            <span className="section-eyebrow">Direct Representation</span>
            <h3 className="contacts-card-title">Awaaz Estate Corporate Advisory Desk</h3>
            <p className="contacts-card-sub">
              Visit our Islamabad offices or speak directly to a licensed portfolio consultant.
            </p>
          </div>
          <Link className="button small primary" href="/contact">
            Open Inquiry Dossier &rarr;
          </Link>
        </div>

        <div className="contacts-grid">
          <div className="contact-info-cell">
            <div className="contact-cell-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
                <circle cx="12" cy="10" r="3" />
              </svg>
            </div>
            <div>
              <span className="contact-cell-label">Headquarters</span>
              <p className="contact-cell-val">Sector F-7 Markaz &amp; Blue Area Corridor, Islamabad, Pakistan</p>
            </div>
          </div>

          <div className="contact-info-cell">
            <div className="contact-cell-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
              </svg>
            </div>
            <div>
              <span className="contact-cell-label">Telephone Advisory</span>
              <a href="tel:+92518840000" className="contact-cell-val text-link">+92 (51) 884-0000</a>
            </div>
          </div>

          <div className="contact-info-cell">
            <div className="contact-cell-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
              </svg>
            </div>
            <div>
              <span className="contact-cell-label">WhatsApp Concierge</span>
              <a href="https://wa.me/923008550000" target="_blank" rel="noopener noreferrer" className="contact-cell-val text-link">+92 300 855-0000</a>
            </div>
          </div>

          <div className="contact-info-cell">
            <div className="contact-cell-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
                <rect width="20" height="16" x="2" y="4" rx="2" />
                <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
              </svg>
            </div>
            <div>
              <span className="contact-cell-label">Official Inquiries</span>
              <a href="mailto:advisory@awaazestate.pk" className="contact-cell-val text-link">advisory@awaazestate.pk</a>
            </div>
          </div>
        </div>
      </div>

      <div className="covenant-cta-row">
        <Link className="button secondary small" href="/about">
          Learn More About Our Methodology &rarr;
        </Link>
        <Link className="button secondary small" href="/contact">
          Consult With An Advisor
        </Link>
      </div>
    </div>
  );
}
