import Link from "next/link";

export function HowAwaazWorks() {
  const steps = [
    {
      number: "01",
      icon: (
        <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          <line x1="12" y1="19" x2="12" y2="22" />
        </svg>
      ),
      title: "Discover or Speak",
      description:
        "Filter verified inventory by sector and budget, or speak your requirements naturally in Urdu or English to our conversational AI assistant.",
      highlight: "Real-time speech pipeline & live sector intelligence",
    },
    {
      number: "02",
      icon: (
        <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          <polyline points="9 12 11 14 15 10" />
        </svg>
      ),
      title: "Inspect Title & Compare",
      description:
        "Every listing includes physical site audit timestamps, verified CDA allotment scrutiny, and high-resolution photo mosaics without fake broker bait.",
      highlight: "Documented title reviews & physical photography",
    },
    {
      number: "03",
      icon: (
        <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="2">
          <rect width="18" height="18" x="3" y="4" rx="2" ry="2" />
          <line x1="16" y1="2" x2="16" y2="6" />
          <line x1="8" y1="2" x2="8" y2="6" />
          <line x1="3" y1="10" x2="21" y2="10" />
        </svg>
      ),
      title: "Instant Private Viewing",
      description:
        "Select an available appointment time slot, authenticate with a 6-digit email OTP, and your site visit is instantly booked with an assigned certified agent.",
      highlight: "Zero telemarketer spam & transactional calendar lock",
    },
  ];

  return (
    <div className="how-it-works-section">
      <div className="how-header-row">
        <div>
          <span className="section-eyebrow">A Better Real Estate Standard</span>
          <h2 className="how-main-title">How Awaaz Estate Works</h2>
          <p className="how-sub">
            Built from the ground up to eliminate the frustration, phantom listings, and high-pressure agent spam standard across traditional classifieds portals.
          </p>
        </div>
        <Link className="button secondary" href="/about">
          Learn Our Legal Standards →
        </Link>
      </div>

      <div className="how-steps-grid">
        {steps.map((step, idx) => (
          <div key={step.number} className="how-step-card">
            <div className="step-card-header">
              <span className="step-number-pill">{step.number}</span>
              <div className="step-icon-box">{step.icon}</div>
            </div>

            <h3 className="step-card-title">{step.title}</h3>
            <p className="step-card-desc">{step.description}</p>

            <div className="step-card-footer">
              <span className="step-highlight-tag">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true" style={{ display: "inline-block", verticalAlign: "middle", marginRight: 5 }}>
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                {step.highlight}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
