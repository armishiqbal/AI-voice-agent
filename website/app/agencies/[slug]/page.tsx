import { notFound } from "next/navigation";
import Link from "next/link";
import { agencies, agents } from "@/lib/marketplace";
import { listings } from "@/lib/catalog";
import { ListingCard } from "@/components/ListingCard";
import { AgencyInquiryForm } from "@/components/AgencyInquiryForm";
import { metadata } from "@/lib/site";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const orgList = await agencies();
  const o = orgList.find((org) => org.slug === slug || org.id === slug);
  return metadata(
    o?.name ? `${o.name} | Accredited Agency Portfolio` : "Agency Portfolio",
    o?.description ||
      "Civic approved publisher profile and verified published listings across Islamabad and Rawalpindi.",
    `/agencies/${slug}`
  );
}

export default async function AgencyPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const [orgList, allAgents] = await Promise.all([
    agencies(),
    agents().catch(() => []),
  ]);

  const org = orgList.find((o) => o.slug === slug || o.id === slug);
  if (!org) notFound();

  // Retrieve published listings for this agency (resilient by id and slug)
  let result = await listings({ organization_id: org.id, page_size: "24" });
  if (result.data.length === 0) {
    result = await listings({ organization_id: org.slug, page_size: "24" });
  }

  // Filter associated senior advisors
  const agencyAdvisors = allAgents.filter(
    (a) => a.agency.slug === org.slug || a.agency.id === org.id
  );

  const initials = org.name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2);

  const regId =
    org.license_number || `CDA/REG-${org.slug.slice(0, 3).toUpperCase()}-2024`;

  const cleanPhone = (phone?: string | null) => {
    if (!phone) return "";
    return phone.replace(/[^0-9]/g, "");
  };

  return (
    <div className="container" style={{ paddingBottom: 80 }}>
      {/* Breadcrumbs */}
      <nav
        aria-label="Breadcrumbs"
        style={{ paddingTop: 24, fontSize: 13, color: "var(--muted)" }}
      >
        <Link href="/" style={{ color: "var(--muted)" }}>
          Home
        </Link>
        <span style={{ margin: "0 8px" }}>/</span>
        <Link href="/agents" style={{ color: "var(--muted)" }}>
          Agencies &amp; Advisors
        </Link>
        <span style={{ margin: "0 8px" }}>/</span>
        <span style={{ color: "var(--ink)", fontWeight: 600 }}>{org.name}</span>
      </nav>

      {/* Institutional Hero Showcase */}
      <header className="agency-profile-hero">
        <div className="agency-profile-header-row">
          <div className="agency-profile-avatar-large" aria-hidden="true">
            {initials}
          </div>

          <div className="agency-profile-details">
            <div className="agency-profile-kicker-row">
              <span className="agency-accreditation-pill">
                <svg
                  viewBox="0 0 24 24"
                  width="13"
                  height="13"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                >
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  <path d="m9 12 2 2 4-4" />
                </svg>
                Civic Authority Accredited Brokerage
              </span>
              <span className="agency-reg-id">{regId}</span>
              {org.established && (
                <span className="agency-established-pill">
                  Est. {org.established}
                </span>
              )}
            </div>

            <h1 className="agency-profile-title">{org.name}</h1>
            <p className="agency-profile-bio">{org.description}</p>
          </div>
        </div>

        {/* Corporate Credentials & Key Metrics Grid */}
        <div className="agency-profile-stats-grid">
          <div className="agency-stat-box">
            <span className="agency-stat-label">Active Portfolio</span>
            <span className="agency-stat-value">
              {result.data.length} Verified Assets
            </span>
          </div>

          <div className="agency-stat-box">
            <span className="agency-stat-label">Accreditation</span>
            <span className="agency-stat-value">CDA &amp; DHA Licensed</span>
          </div>

          <div className="agency-stat-box">
            <span className="agency-stat-label">Title Governance</span>
            <span className="agency-stat-value">100% Non-Encumbrance</span>
          </div>

          <div className="agency-stat-box">
            <span className="agency-stat-label">Tax Compliance</span>
            <span className="agency-stat-value">FBR Active Withholding</span>
          </div>
        </div>

        {/* Coverage Sectors Chips */}
        <div>
          <span
            style={{
              display: "block",
              fontSize: 11,
              fontWeight: 750,
              textTransform: "uppercase",
              letterSpacing: "0.5px",
              color: "var(--muted)",
              marginBottom: 8,
            }}
          >
            Core Jurisdiction &amp; Coverage Sectors
          </span>
          <div className="agency-specialties-wrap">
            {org.coverage.map((c) => (
              <span key={c} className="agency-spec-chip">
                {c}
              </span>
            ))}
          </div>
        </div>

        {/* Direct Contact & Action Bar */}
        <div className="agency-profile-contact-bar">
          <div className="agency-contact-buttons">
            {org.contact_phone && (
              <a
                href={`tel:${org.contact_phone}`}
                className="agency-contact-btn agency-btn-call"
              >
                <svg
                  viewBox="0 0 24 24"
                  width="16"
                  height="16"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                >
                  <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
                </svg>
                <span>Call Desk ({org.contact_phone})</span>
              </a>
            )}

            {org.whatsapp && (
              <a
                href={`https://wa.me/${cleanPhone(org.whatsapp)}?text=Hello%20${encodeURIComponent(
                  org.name
                )},%20I%20would%20like%20to%20inquire%20about%20your%20verified%20portfolio`}
                target="_blank"
                rel="noopener noreferrer"
                className="agency-contact-btn agency-btn-wa"
              >
                <svg
                  viewBox="0 0 24 24"
                  width="16"
                  height="16"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
                </svg>
                <span>WhatsApp Desk</span>
              </a>
            )}

            {org.contact_email && (
              <a
                href={`mailto:${org.contact_email}`}
                className="agency-contact-btn agency-btn-email"
              >
                <svg
                  viewBox="0 0 24 24"
                  width="16"
                  height="16"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                >
                  <rect x="2" y="4" width="20" height="16" rx="2" />
                  <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
                </svg>
                <span>Email Official Desk</span>
              </a>
            )}
          </div>

          <a href="#mandate-desk" className="action-btn action-btn-ghost" style={{ fontSize: 13 }}>
            Submit Acquisition Mandate ↓
          </a>
        </div>
      </header>

      {/* Corporate Headquarters & Chamber Details */}
      <section className="agency-chambers-box">
        <div className="chambers-grid">
          <div className="chambers-item">
            <span className="chambers-label">Corporate Headquarters</span>
            <span className="chambers-value">
              {org.address || "ISE Towers, Jinnah Avenue, Blue Area, Islamabad"}
            </span>
          </div>
          <div className="chambers-item">
            <span className="chambers-label">Operating Hours</span>
            <span className="chambers-value">Monday – Saturday: 09:30 – 18:30 PKT</span>
          </div>
          <div className="chambers-item">
            <span className="chambers-label">Statutory Affiliation</span>
            <span className="chambers-value">Capital Development Authority (CDA) &amp; DHA</span>
          </div>
          <div className="chambers-item">
            <span className="chambers-label">Escrow Trust Oversight</span>
            <span className="chambers-value">Habib Bank / Meezan Bank Corporate Trust Desk</span>
          </div>
        </div>
      </section>

      {/* Associated Senior Advisors Section */}
      {agencyAdvisors.length > 0 && (
        <section style={{ marginBottom: 54 }}>
          <div style={{ marginBottom: 20 }}>
            <span
              style={{
                fontSize: 11,
                fontWeight: 750,
                textTransform: "uppercase",
                letterSpacing: 1.5,
                color: "var(--green)",
              }}
            >
              Advisory Leadership
            </span>
            <h2
              style={{
                fontSize: 24,
                margin: "4px 0 0",
                fontFamily: "var(--serif)",
              }}
            >
              Accredited Senior Advisors at {org.name} ({agencyAdvisors.length})
            </h2>
          </div>

          <div className="agencies-main-grid" style={{ marginBottom: 0 }}>
            {agencyAdvisors.map((advisor) => {
              const advInitials = advisor.name
                .split(" ")
                .map((w) => w[0])
                .join("")
                .slice(0, 2);

              return (
                <article key={advisor.slug} className="agency-dossier-card advisor-card">
                  <div className="agency-card-top">
                    <div
                      className="agency-avatar"
                      style={{
                        background:
                          "linear-gradient(135deg, #0d2920 0%, #153c30 100%)",
                      }}
                    >
                      {advInitials}
                    </div>
                    <div className="agency-info-heading">
                      <h3 className="agency-name">
                        <Link href={`/agents/${advisor.slug}`}>
                          {advisor.name}
                        </Link>
                      </h3>
                      <span className="agency-license-tag">
                        {advisor.title || "Senior Advisor"}
                      </span>
                    </div>
                  </div>

                  <p className="agency-bio">
                    {advisor.bio ||
                      "Dedicated property consultant managing high-value acquisition and seller representation under official agency fiduciary oversight."}
                  </p>

                  {advisor.specialties && advisor.specialties.length > 0 && (
                    <div>
                      <span className="agency-card-sectors-title">Specialties</span>
                      <div className="agency-specialties-wrap">
                        {advisor.specialties.map((s) => (
                          <span key={s} className="agency-spec-chip advisor-spec-chip">
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="advisor-lang-row">
                    <span className="advisor-lang-label">Languages:</span>
                    <span className="advisor-lang-val">
                      {advisor.languages.join(", ")}
                    </span>
                  </div>

                  <div className="agency-actions-footer">
                    <Link
                      href={`/agents/${advisor.slug}`}
                      className="card-primary-action"
                    >
                      <span>Advisor Dossier</span>
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <line x1="5" y1="12" x2="19" y2="12" />
                        <polyline points="12 5 19 12 12 19" />
                      </svg>
                    </Link>

                    <div className="card-quick-actions">
                      {advisor.whatsapp && (
                        <a
                          href={`https://wa.me/${cleanPhone(advisor.whatsapp)}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="card-quick-btn card-wa-btn"
                          aria-label={`WhatsApp ${advisor.name}`}
                          title="WhatsApp Direct"
                        >
                          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
                          </svg>
                        </a>
                      )}
                      {(advisor.phone || org.contact_phone) && (
                        <a
                          href={`tel:${advisor.phone || org.contact_phone}`}
                          className="card-secondary-action"
                          aria-label={`Call ${advisor.name}`}
                        >
                          Call Direct
                        </a>
                      )}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}

      {/* Published Verified Portfolio */}
      <section style={{ marginBottom: 60 }}>
        <div style={{ marginBottom: 24 }}>
          <span
            style={{
              fontSize: 11,
              fontWeight: 750,
              textTransform: "uppercase",
              letterSpacing: 1.5,
              color: "var(--green)",
            }}
          >
            Verified Inventory
          </span>
          <h2
            style={{
              fontSize: 26,
              margin: "4px 0 0",
              fontFamily: "var(--serif)",
            }}
          >
            Properties Represented by {org.name} ({result.data.length})
          </h2>
          <p
            style={{
              color: "var(--muted)",
              fontSize: 14.5,
              margin: "6px 0 0",
            }}
          >
            Each property below has completed Awaaz Estate on-site physical demarcation and legal authority register verification.
          </p>
        </div>

        {result.data.length > 0 ? (
          <div
            className="properties-catalog-grid"
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
              gap: 24,
            }}
          >
            {result.data.map((property) => (
              <ListingCard key={property.id} property={property} />
            ))}
          </div>
        ) : (
          <div
            style={{
              background: "var(--white)",
              border: "1px dashed var(--line)",
              borderRadius: 20,
              padding: "48px 24px",
              textAlign: "center",
              color: "var(--muted)",
            }}
          >
            <h3 style={{ color: "var(--ink)", marginBottom: 8 }}>
              No Active Public Listings Displayed
            </h3>
            <p style={{ maxWidth: 520, margin: "0 auto 20px" }}>
              {org.name} currently has no retail listings on public display.
              Contact their corporate desk directly to request private off-market portfolios.
            </p>
            {org.contact_phone && (
              <a
                href={`tel:${org.contact_phone}`}
                className="agency-contact-btn agency-btn-call"
                style={{ display: "inline-flex" }}
              >
                Contact Corporate Desk
              </a>
            )}
          </div>
        )}
      </section>

      {/* Interactive Mandate Submission Section */}
      <section id="mandate-desk" style={{ marginBottom: 60 }}>
        <AgencyInquiryForm
          targetName={org.name}
          targetType="agency"
          contactPhone={org.contact_phone}
          contactEmail={org.contact_email}
          whatsapp={org.whatsapp}
        />
      </section>

      {/* Institutional Due Diligence Covenant */}
      <section className="agency-covenant-box">
        <span
          style={{
            fontSize: 11,
            fontWeight: 750,
            textTransform: "uppercase",
            letterSpacing: 1.5,
            color: "var(--green)",
          }}
        >
          Fiduciary Governance
        </span>
        <h3
          style={{
            fontSize: 21,
            margin: "6px 0 12px",
            fontFamily: "var(--serif)",
          }}
        >
          Awaaz Estate Institutional Agency Covenant
        </h3>
        <p
          style={{
            color: "var(--muted)",
            fontSize: 14,
            margin: 0,
            maxWidth: 840,
          }}
        >
          {org.name} adheres to the 2026 Awaaz Estate Trust Covenant. As a verified brokerage partner, all published inventory undergoes mandatory 5-point due diligence before reaching the public market.
        </p>

        <div className="agency-covenant-grid">
          <div className="covenant-pillar">
            <div className="covenant-icon" aria-hidden="true">
              <svg
                viewBox="0 0 24 24"
                width="18"
                height="18"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
              >
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
              </svg>
            </div>
            <h4 className="covenant-title">Title Register Authentication</h4>
            <p className="covenant-desc">
              Allotment registers, transfer letters, and mutation records confirmed directly with CDA, DHA, and RDA registrars.
            </p>
          </div>

          <div className="covenant-pillar">
            <div className="covenant-icon" aria-hidden="true">
              <svg
                viewBox="0 0 24 24"
                width="18"
                height="18"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
              >
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
            </div>
            <h4 className="covenant-title">Zero Liens &amp; Encumbrances</h4>
            <p className="covenant-desc">
              Guaranteed clearance of bank hypothecation charges, excise liabilities, or active judicial stay orders prior to booking.
            </p>
          </div>

          <div className="covenant-pillar">
            <div className="covenant-icon" aria-hidden="true">
              <svg
                viewBox="0 0 24 24"
                width="18"
                height="18"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
              >
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            </div>
            <h4 className="covenant-title">Punctual Viewing Coordination</h4>
            <p className="covenant-desc">
              Direct access coordination with licensed property keys, on-site engineer reports, and verified floor plans.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
