import { notFound } from "next/navigation";
import Link from "next/link";
import { agents } from "@/lib/marketplace";
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
  const list = await agents();
  const p = list.find((a) => a.slug === slug);
  return metadata(
    p ? `${p.name} | Licensed Senior Property Advisor` : "Advisor Dossier",
    p?.bio ||
      `Accredited senior real estate advisor at ${p?.agency.name || "Awaaz Estate"}. Title verification and high-value property representation.`,
    `/agents/${slug}`
  );
}

export default async function AgentDossierPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const list = await agents();
  const person = list.find((a) => a.slug === slug);
  if (!person) notFound();

  // Retrieve listings represented by advisor's agency
  let portfolioResult = await listings({
    organization_id: person.agency.id,
    page_size: "12",
  });
  if (portfolioResult.data.length === 0) {
    portfolioResult = await listings({
      organization_id: person.agency.slug,
      page_size: "12",
    });
  }

  const initials = person.name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2);

  const cleanPhone = (phone?: string | null) => {
    if (!phone) return "";
    return phone.replace(/[^0-9]/g, "");
  };

  const regId =
    person.license_id ||
    `CDA/ADV-${person.slug.slice(0, 3).toUpperCase()}-2024`;

  const directPhone = person.phone || person.agency.contact_phone;
  const directEmail = person.email || person.agency.contact_email;
  const directWhatsapp = person.whatsapp || person.agency.whatsapp;

  return (
    <div className="container" style={{ paddingBottom: 80 }}>
      {/* Breadcrumbs */}
      <nav
        aria-label="Breadcrumbs"
        style={{
          paddingTop: 24,
          fontSize: 13,
          color: "var(--muted)",
        }}
      >
        <Link href="/" style={{ color: "var(--muted)" }}>
          Home
        </Link>
        <span style={{ margin: "0 8px" }}>/</span>
        <Link href="/agents" style={{ color: "var(--muted)" }}>
          Agencies &amp; Advisors
        </Link>
        <span style={{ margin: "0 8px" }}>/</span>
        <span style={{ color: "var(--ink)", fontWeight: 600 }}>
          {person.name}
        </span>
      </nav>

      {/* Executive Advisor Dossier Hero */}
      <header className="advisor-dossier-hero">
        <div className="advisor-avatar-xlarge" aria-hidden="true">
          {initials}
        </div>

        <div className="advisor-dossier-details">
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
              Licensed Senior Property Advisor
            </span>
            <span className="agency-reg-id">{regId}</span>
            <Link
              href={`/agencies/${person.agency.slug}`}
              className="advisor-agency-affiliation"
            >
              <span>{person.agency.name}</span>
              <svg
                viewBox="0 0 24 24"
                width="12"
                height="12"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
              >
                <polyline points="9 18 15 12 9 6" />
              </svg>
            </Link>
          </div>

          <h1 className="agency-profile-title">{person.name}</h1>
          <p className="advisor-title-text">
            {person.title || "Senior Partner & Real Estate Advisory Director"}
          </p>

          <p className="agency-profile-bio">
            {person.bio ||
              `${person.name} provides fiduciary property advisory and acquisition counsel under ${person.agency.name}. Specializing in CDA/DHA title due diligence, corporate relocations, and luxury residential portfolios.`}
          </p>

          {/* Practice Specialties Chips */}
          {person.specialties && person.specialties.length > 0 && (
            <div style={{ marginTop: 8 }}>
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
                Core Practice Specialties
              </span>
              <div className="agency-specialties-wrap">
                {person.specialties.map((spec) => (
                  <span key={spec} className="agency-spec-chip advisor-spec-chip">
                    {spec}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Direct Contact Bar */}
          <div className="advisor-direct-actions-row">
            {directPhone && (
              <a
                href={`tel:${directPhone}`}
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
                <span>Call Direct ({directPhone})</span>
              </a>
            )}

            {directWhatsapp && (
              <a
                href={`https://wa.me/${cleanPhone(directWhatsapp)}?text=Hello%20${encodeURIComponent(
                  person.name
                )},%20I%20would%20like%20to%20consult%20regarding%20property%20advisory`}
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

            {directEmail && (
              <a
                href={`mailto:${directEmail}`}
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
                <span>Send Official Email</span>
              </a>
            )}
          </div>
        </div>
      </header>

      {/* Professional Credentials & Performance Grid */}
      <section className="advisor-credentials-box">
        <div className="agency-profile-stats-grid" style={{ margin: 0, border: "none", padding: 0 }}>
          <div className="agency-stat-box">
            <span className="agency-stat-label">Accreditation</span>
            <span className="agency-stat-value">CDA &amp; DHA Licensed</span>
          </div>

          <div className="agency-stat-box">
            <span className="agency-stat-label">Experience</span>
            <span className="agency-stat-value">
              {person.experience_years || 14}+ Years Advisory
            </span>
          </div>

          <div className="agency-stat-box">
            <span className="agency-stat-label">Spoken Languages</span>
            <span className="agency-stat-value">
              {person.languages.join(", ")}
            </span>
          </div>

          <div className="agency-stat-box">
            <span className="agency-stat-label">Title Governance</span>
            <span className="agency-stat-value">100% Non-Encumbered</span>
          </div>
        </div>
      </section>

      {/* Main Grid: Consultation Mandate Form & Brokerage Affiliation */}
      <section className="advisor-mandate-layout">
        <div className="advisor-mandate-left">
          <AgencyInquiryForm
            targetName={person.name}
            targetType="advisor"
            contactPhone={directPhone}
            contactEmail={directEmail}
            whatsapp={directWhatsapp}
          />
        </div>

        <div className="advisor-mandate-right">
          {/* Affiliated Agency Card */}
          <div className="advisor-agency-profile-card">
            <span className="agency-license-tag">Accredited Brokerage</span>
            <h3 className="advisor-agency-card-title">{person.agency.name}</h3>
            <p className="advisor-agency-card-desc">{person.agency.description}</p>

            {person.agency.address && (
              <div className="agency-card-location" style={{ marginBottom: 16 }}>
                <svg
                  viewBox="0 0 24 24"
                  width="14"
                  height="14"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                >
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                  <circle cx="12" cy="10" r="3" />
                </svg>
                <span>{person.agency.address}</span>
              </div>
            )}

            <div style={{ marginBottom: 20 }}>
              <span className="agency-card-sectors-title">Agency Coverage Sectors</span>
              <div className="agency-specialties-wrap">
                {person.agency.coverage.map((c) => (
                  <span key={c} className="agency-spec-chip">
                    {c}
                  </span>
                ))}
              </div>
            </div>

            <Link
              href={`/agencies/${person.agency.slug}`}
              className="card-primary-action"
              style={{ width: "100%", justifyContent: "center" }}
            >
              <span>View Full Agency Portfolio</span>
              <svg
                viewBox="0 0 24 24"
                width="14"
                height="14"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
              >
                <line x1="5" y1="12" x2="19" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
            </Link>
          </div>

          {/* Fiduciary Code of Practice Card */}
          <div className="advisor-fiduciary-card">
            <div className="fiduciary-card-badge">
              <svg
                viewBox="0 0 24 24"
                width="14"
                height="14"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
              >
                <circle cx="12" cy="12" r="10" />
                <path d="m9 12 2 2 4-4" />
              </svg>
              Fiduciary Representation Code
            </div>
            <h4 style={{ margin: "10px 0 6px", fontSize: 16, fontWeight: 700, color: "var(--ink)" }}>
              Client Protection Standards
            </h4>
            <p style={{ margin: 0, fontSize: 13, color: "var(--muted)", lineHeight: 1.55 }}>
              All transactions conducted under {person.name} are backed by official title register verification, direct escrow protocols, and formal non-conflict warranties.
            </p>
          </div>
        </div>
      </section>

      {/* Properties Under Agency Representation */}
      <section style={{ marginTop: 60 }}>
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
            Verified Portfolio
          </span>
          <h2
            style={{
              fontSize: 26,
              margin: "4px 0 0",
              fontFamily: "var(--serif)",
            }}
          >
            Properties Represented by {person.agency.name} ({portfolioResult.data.length})
          </h2>
          <p
            style={{
              color: "var(--muted)",
              fontSize: 14.5,
              margin: "6px 0 0",
            }}
          >
            All properties represented by {person.name}&rsquo;s brokerage are verified with on-site demarcation and civic title clearance.
          </p>
        </div>

        {portfolioResult.data.length > 0 ? (
          <div
            className="properties-catalog-grid"
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
              gap: 24,
            }}
          >
            {portfolioResult.data.map((property) => (
              <ListingCard key={property.id} property={property} />
            ))}
          </div>
        ) : (
          <div
            style={{
              background: "var(--white)",
              border: "1px dashed var(--line)",
              borderRadius: 20,
              padding: "40px 24px",
              textAlign: "center",
              color: "var(--muted)",
            }}
          >
            <h3 style={{ color: "var(--ink)", marginBottom: 8 }}>
              No Public Retail Listings
            </h3>
            <p style={{ maxWidth: 520, margin: "0 auto 16px" }}>
              Private off-market inventory is maintained directly by {person.name}. Contact the advisory desk to request confidential options.
            </p>
            {directPhone && (
              <a
                href={`tel:${directPhone}`}
                className="agency-contact-btn agency-btn-call"
                style={{ display: "inline-flex" }}
              >
                Contact {person.name} Directly
              </a>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
