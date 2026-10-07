"use client";

export function MarketMetricsBar() {
  const metrics = [
    {
      icon: (
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          <path d="m9 12 2 2 4-4" />
        </svg>
      ),
      value: "Direct",
      label: "Direct Agency Inventory",
      sub: "Exclusively managed listings, zero scraped ads",
    },
    {
      icon: (
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
          <circle cx="12" cy="10" r="3" />
        </svg>
      ),
      value: "Capital",
      label: "Prime Sector Focus",
      sub: "Active coverage in F-6, F-7, F-10, DHA & Bahria",
    },
    {
      icon: (
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
        </svg>
      ),
      value: "Bilingual",
      label: "Urdu & English Voice AI",
      sub: "Conversational property search & inquiries",
    },
    {
      icon: (
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <rect width="18" height="18" x="3" y="4" rx="2" ry="2" />
          <line x1="16" y1="2" x2="16" y2="6" />
          <line x1="8" y1="2" x2="8" y2="6" />
          <line x1="3" y1="10" x2="21" y2="10" />
        </svg>
      ),
      value: "Verified",
      label: "Accompanied Viewings",
      sub: "Direct slot reservation with email confirmation",
    },
  ];

  return (
    <div className="market-metrics-container">
      <div className="metrics-grid">
        {metrics.map((item, index) => (
          <div key={index} className="metric-cell">
            <div className="metric-icon-box">{item.icon}</div>
            <div className="metric-text-box">
              <div className="metric-value-row">
                <span className="metric-num">{item.value}</span>
              </div>
              <span className="metric-title">{item.label}</span>
              <p className="metric-desc">{item.sub}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
