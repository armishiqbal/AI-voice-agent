import Link from "next/link";
import Image from "next/image";
import { listings, areaGuide } from "@/lib/catalog";
import { metadata } from "@/lib/site";
import { Notice } from "@/components/Notice";
import { ListingCard } from "@/components/ListingCard";
import { getSectorMetadata } from "@/lib/sectors";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ city: string; area: string }> };

export async function generateMetadata({ params }: Props) {
  const { city, area } = await params;
  const guide = await areaGuide(city, area);
  const meta = getSectorMetadata(city, area);
  const title = guide?.title || `${meta.area}, ${meta.city} | Architectural Sector Dossier`;
  const desc = guide?.overview_markdown
    ? guide.overview_markdown.slice(0, 160)
    : `${meta.description} Explore verified zoning records and luxury properties.`;

  return {
    ...metadata(title, desc, `/areas/${encodeURIComponent(city)}/${encodeURIComponent(area)}`),
    robots: { index: true, follow: true },
  };
}

export default async function AreaPage({ params }: Props) {
  const { city, area } = await params;
  const [guide, catalog] = await Promise.all([
    areaGuide(city, area),
    listings({ city, area, page_size: "12" }).catch(() => null),
  ]);

  const meta = getSectorMetadata(city, area);
  const formattedReviewDate = guide?.reviewed_at
    ? new Intl.DateTimeFormat("en-PK", { dateStyle: "long", timeZone: "Asia/Karachi" }).format(
        new Date(guide.reviewed_at)
      )
    : "October 2026";

  return (
    <div className="container">
      {/* Institutional Breadcrumbs */}
      <nav className="breadcrumbs" aria-label="Breadcrumb" style={{ marginTop: 24 }}>
        <Link href="/">Home</Link>
        <span>/</span>
        <Link href="/areas">Sector Guides</Link>
        <span>/</span>
        <span>{meta.city}</span>
        <span>/</span>
        <span aria-current="page">{meta.area}</span>
      </nav>

      {/* Sector Hero Section */}
      <section className="sector-dossier-hero">
        <div className="sector-dossier-hero-inner">
          <div className="sector-hero-content">
            <div className="sector-hero-badge-row">
              <span className="area-civic-badge">
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
                {meta.authority}
              </span>
              <span className="sector-noc-pill">
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                {meta.nocStatus}
              </span>
            </div>

            <h1 className="sector-dossier-title">
              {guide?.title || meta.title}
            </h1>

            <p className="sector-dossier-lead">
              {meta.description}
            </p>

            <div className="sector-hero-meta-row">
              <span className="sector-meta-tag">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M12 6v6l4 2" />
                </svg>
                Audited &amp; Certified: {formattedReviewDate}
              </span>
              <span className="sector-meta-tag">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                  <circle cx="12" cy="10" r="3" />
                </svg>
                {meta.zone}
              </span>
            </div>
          </div>

          <div className="sector-hero-media">
            <div className="sector-hero-img-wrap">
              <Image
                src={meta.img}
                alt={meta.title}
                fill
                priority
                sizes="(max-width: 768px) 100vw, 480px"
                style={{ objectFit: "cover" }}
              />
              <div className="sector-hero-media-overlay">
                <span className="sector-category-badge">{meta.categoryLabel}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 4-Metric Institutional Ribbon */}
      <section className="sector-metrics-ribbon" aria-label="Key Sector Indicators">
        <div className="sector-metric-card">
          <div className="sector-metric-icon">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <div className="sector-metric-info">
            <span className="sector-metric-label">Municipal Authority</span>
            <strong className="sector-metric-value">{meta.authority}</strong>
            <span className="sector-metric-sub">{meta.zone}</span>
          </div>
        </div>

        <div className="sector-metric-card">
          <div className="sector-metric-icon">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <line x1="12" y1="1" x2="12" y2="23" />
              <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
            </svg>
          </div>
          <div className="sector-metric-info">
            <span className="sector-metric-label">Valuation Benchmark</span>
            <strong className="sector-metric-value">{meta.priceRange}</strong>
            <span className="sector-metric-sub">{meta.priceBenchmarkMarla}</span>
          </div>
        </div>

        <div className="sector-metric-card">
          <div className="sector-metric-icon">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
              <polyline points="17 6 23 6 23 12" />
            </svg>
          </div>
          <div className="sector-metric-info">
            <span className="sector-metric-label">Projected Yield</span>
            <strong className="sector-metric-value text-green">{meta.rentalYield}</strong>
            <span className="sector-metric-sub">{meta.lifestyle}</span>
          </div>
        </div>

        <div className="sector-metric-card">
          <div className="sector-metric-icon">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <circle cx="12" cy="12" r="10" />
              <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" />
            </svg>
          </div>
          <div className="sector-metric-info">
            <span className="sector-metric-label">Capital Transit Radius</span>
            <strong className="sector-metric-value">{meta.airportCommute} to Airport</strong>
            <span className="sector-metric-sub">{meta.zeroPointCommute} to Zero Point</span>
          </div>
        </div>
      </section>

      {/* Main Dossier Content */}
      <div className="sector-dossier-body">
        {/* Left Column: Dossier Details */}
        <div className="sector-dossier-main">
          {/* Section 1: Master Plan Overview */}
          <article className="sector-content-card">
            <div className="sector-card-heading-wrap">
              <span className="seller-page-kicker">Section 01 · Planning Architecture</span>
              <h2 className="sector-card-heading">Master Plan &amp; Urban Morphology</h2>
            </div>
            <div className="sector-card-prose">
              <p style={{ whiteSpace: "pre-line" }}>
                {guide?.overview_markdown ||
                  `${meta.area} is a premier sector within the ${meta.city} metropolitan footprint. Governed under ${meta.zone}, it adheres to rigorous statutory setback rules, underground utility covenants, and demarcated commercial zones.`}
              </p>
            </div>

            {/* Sector Highlights Chips */}
            <div className="sector-highlights-box">
              <span className="sector-highlights-title">Key Sector Landmarks &amp; Features:</span>
              <div className="sector-highlights-tags">
                {meta.keyHighlights.map((item, idx) => (
                  <span key={idx} className="sector-tag-pill">
                    <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    {item}
                  </span>
                ))}
              </div>
            </div>
          </article>

          {/* Section 2: Amenities & Civic Infrastructure */}
          <article className="sector-content-card">
            <div className="sector-card-heading-wrap">
              <span className="seller-page-kicker">Section 02 · Urban Services</span>
              <h2 className="sector-card-heading">Amenities, Utilities &amp; Civic Profile</h2>
            </div>
            <div className="sector-card-prose">
              <p>
                {guide?.amenities_summary ||
                  "Comprehensive municipal utilities including underground electrification, pressurized water distribution, dedicated commercial centers, and fiber optic backbones."}
              </p>
            </div>

            <div className="sector-utility-grid">
              <div className="sector-utility-item">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                </svg>
                <span><strong>Power Grid:</strong> Standby substations &amp; underground 11kV distribution</span>
              </div>
              <div className="sector-utility-item">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" />
                </svg>
                <span><strong>Water Supply:</strong> Filtered CDA/DHA deep tube-well aquifer supply</span>
              </div>
              <div className="sector-utility-item">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
                <span><strong>Security:</strong> Perimeter security, surveillance &amp; rapid response</span>
              </div>
              <div className="sector-utility-item">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
                  <rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
                  <line x1="6" y1="6" x2="6.01" y2="6" />
                  <line x1="6" y1="18" x2="6.01" y2="18" />
                </svg>
                <span><strong>Telecommunications:</strong> Multi-provider high-capacity fiber backbone</span>
              </div>
            </div>
          </article>

          {/* Section 3: Transit & Capital Connectivity */}
          <article className="sector-content-card">
            <div className="sector-card-heading-wrap">
              <span className="seller-page-kicker">Section 03 · Arterial Connectivity</span>
              <h2 className="sector-card-heading">Transport Arteries &amp; Commute Corridor</h2>
            </div>
            <div className="sector-card-prose">
              <p>
                {guide?.transport_info ||
                  "Direct access to principal capital expressways, providing seamless transit across Zero Point, Blue Area, and Islamabad International Airport."}
              </p>
            </div>

            <div className="sector-commute-benchmarks">
              <div className="sector-benchmark-pill">
                <span className="benchmark-time">{meta.airportCommute}</span>
                <span className="benchmark-dest">Islamabad International Airport</span>
              </div>
              <div className="sector-benchmark-pill">
                <span className="benchmark-time">{meta.zeroPointCommute}</span>
                <span className="benchmark-dest">Zero Point Capital Interchange</span>
              </div>
              <div className="sector-benchmark-pill">
                <span className="benchmark-time">Signal-Free</span>
                <span className="benchmark-dest">Capital Expressway Arteries</span>
              </div>
            </div>
          </article>

          {/* Section 4: Investment Outlook & Capital Preservation */}
          <article className="sector-content-card">
            <div className="sector-card-heading-wrap">
              <span className="seller-page-kicker">Section 04 · Wealth Preservation</span>
              <h2 className="sector-card-heading">Investment Outlook &amp; Rental Demand</h2>
            </div>
            <div className="sector-card-prose">
              <p>
                {guide?.investment_outlook ||
                  "Strong capital preservation driven by limited supply, high overseas Pakistani acquisition, and sustained foreign diplomat and corporate rental demand."}
              </p>
            </div>
          </article>

          {/* Section 5: Statutory Authority & Verification Sources */}
          {guide?.sources && guide.sources.length > 0 && (
            <article className="sector-content-card sector-sources-card">
              <div className="sector-card-heading-wrap">
                <span className="seller-page-kicker">Section 05 · Regulatory Authority</span>
                <h2 className="sector-card-heading">Statutory References &amp; Official Records</h2>
              </div>
              <p className="sector-sources-note">
                Dossier compiled from official municipal publications, master plan gazettes, and verified title registries.
              </p>
              <ul className="sector-sources-list">
                {guide.sources.map((src, idx) => (
                  <li key={idx} className="sector-source-item">
                    <a
                      href={src.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="sector-source-link"
                    >
                      <span>{src.title || src.url}</span>
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                        <polyline points="15 3 21 3 21 9" />
                        <line x1="10" y1="14" x2="21" y2="3" />
                      </svg>
                    </a>
                  </li>
                ))}
              </ul>
            </article>
          )}
        </div>

        {/* Right Column: Advisory Sidebar */}
        <aside className="sector-dossier-sidebar">
          {/* Voice Advisor Card */}
          <div className="sector-sidebar-card sector-advisor-box">
            <div className="sector-advisor-badge">
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="23" />
                <line x1="8" y1="23" x2="16" y2="23" />
              </svg>
              Live Voice Advisor
            </div>
            <h3 className="sector-advisor-title">Consult our AI Advisory Desk</h3>
            <p className="sector-advisor-desc">
              Request real-time mortgage calculations, transfer duty audits under FBR Section 236C, or arrange private viewings in {meta.area}.
            </p>
            <Link href="/assistant" className="btn-primary" style={{ width: "100%", justifyContent: "center" }}>
              Launch Voice Desk for {meta.area}
            </Link>
          </div>

          {/* Due Diligence Checklist */}
          <div className="sector-sidebar-card">
            <h4 className="sector-sidebar-title">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
                <polyline points="9 11 12 14 22 4" />
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
              </svg>
              {meta.area} Verification Checklist
            </h4>
            <ul className="sector-checklist">
              <li>
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                <span>Allotment Letter authenticated with {meta.authority}</span>
              </li>
              <li>
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                <span>No Demand Certificate (NDC) dues verified</span>
              </li>
              <li>
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                <span>Site demarcation &amp; physical boundaries inspected</span>
              </li>
              <li>
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                <span>FBR CPR challans prepared (Sections 236C / 236K)</span>
              </li>
            </ul>
          </div>

          {/* Quick Nav to other sectors */}
          <div className="sector-sidebar-card">
            <h4 className="sector-sidebar-title">Explore Other Capital Sectors</h4>
            <div className="sector-nav-links">
              <Link href="/areas" className="text-link" style={{ fontSize: "14px" }}>
                ← Browse All 6 Sector Guides
              </Link>
            </div>
          </div>
        </aside>
      </div>

      {/* Available Verified Properties in this Sector */}
      <section className="sector-properties-section">
        <div className="sector-section-header">
          <div>
            <span className="seller-page-kicker">Verified Real Estate Catalog</span>
            <h2 className="areas-section-heading">
              Available Properties in {meta.area}
            </h2>
          </div>
          <p className="areas-section-sub">
            Inspected properties with confirmed civic titles, physical demarcations, and licensed agency representation.
          </p>
        </div>

        {catalog?.data.length ? (
          <div className="listing-grid">
            {catalog.data.map((property) => (
              <ListingCard key={property.id} property={property} />
            ))}
          </div>
        ) : (
          <Notice
            error={!catalog}
            title={catalog ? `No published listings currently active in ${meta.area}` : "Property service temporarily unavailable"}
          >
            <p>
              {catalog
                ? `Our advisory desk frequently manages confidential off-market mandates in ${meta.area}. Contact our partners to register your requirements.`
                : "The property catalog service is momentarily updating. Please check back shortly."}
            </p>
            <Link className="text-link" href="/contact">
              Contact Senior Advisory Partner
            </Link>
          </Notice>
        )}

        {catalog && catalog.pagination.total > 12 && (
          <div style={{ marginTop: 28, textAlign: "center" }}>
            <Link
              className="btn-secondary"
              href={`/properties?city=${encodeURIComponent(city)}&area=${encodeURIComponent(area)}`}
            >
              View all {catalog.pagination.total} properties in {meta.area} →
            </Link>
          </div>
        )}
      </section>
    </div>
  );
}
