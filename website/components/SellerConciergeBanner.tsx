import Link from "next/link";

export function SellerConciergeBanner() {
  return (
    <div className="seller-concierge-card">
      <div className="concierge-glow-overlay" aria-hidden="true" />

      <div className="concierge-content-wrap">
        <div className="concierge-text-side">
          <div className="concierge-badge">
            <span>VIP Property Owner Advisory</span>
          </div>

          <h2 className="concierge-heading">
            Selling or Leasing Your Residence in the Capital?
          </h2>

          <p className="concierge-sub">
            Partner with Awaaz Estate for certified representation. We physically audit your property, capture high-definition architectural media, and showcase your listing directly to vetted local and overseas buyers—without spamming public broker groups.
          </p>

          <div className="concierge-perks-row">
            <div className="concierge-perk">
              <span className="perk-check" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </span>
              <span>Professional Photography & Floorplans</span>
            </div>
            <div className="concierge-perk">
              <span className="perk-check" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </span>
              <span>CDA Allotment & Title Scrutiny</span>
            </div>
            <div className="concierge-perk">
              <span className="perk-check" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </span>
              <span>AI Voice Recommendations</span>
            </div>
            <div className="concierge-perk">
              <span className="perk-check" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </span>
              <span>Direct Representation &amp; Licensed Advisory</span>
            </div>
          </div>
        </div>

        <div className="concierge-action-side">
          <div className="concierge-action-box">
            <h3 className="action-box-title">List With Awaaz Estate</h3>
            <p className="action-box-sub">
              Submit your property details for our review team. We respond within 24 business hours.
            </p>

            <Link href="/contact" className="button primary concierge-btn">
              <span>Submit Property for Review →</span>
            </Link>

            <p className="action-box-footnote">
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" style={{ display: "inline-block", verticalAlign: "middle", marginRight: 5 }}>
                <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
              All owner identities and title documentation are kept strictly confidential.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
