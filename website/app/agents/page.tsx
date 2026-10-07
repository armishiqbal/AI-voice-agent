import Link from "next/link";
import { agents, agencies } from "@/lib/marketplace";
import { metadata } from "@/lib/site";
import { AgentsDirectoryExplorer } from "@/components/AgentsDirectoryExplorer";

export const dynamic = "force-dynamic";

export const generateMetadata = () =>
  metadata(
    "Find Property Agents in Islamabad & Rawalpindi | Awaaz Estate",
    "Browse real estate agencies and property agents in Islamabad and Rawalpindi by area, language, and property specialty.",
    "/agents"
  );

export default async function AgentsPage() {
  const [people, orgs] = await Promise.all([
    agents().catch(() => []),
    agencies().catch(() => []),
  ]);

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
        <span style={{ color: "var(--ink)", fontWeight: 600 }}>
          Agents
        </span>
      </nav>

      {/* Editorial Header */}
      <section className="agents-hero-section">
        <span className="seller-page-kicker">People who know the local market</span>
        <h1 className="seller-page-title">
          Find the right local <em>property agent</em>
        </h1>
        <p className="seller-page-lede">
          Explore agencies and agents serving Islamabad and Rawalpindi. Compare their areas, property specialties, and languages, then contact a profile directly or ask the Awaaz assistant to help you find a property.
        </p>
        <div className="agents-hero-actions">
          <Link href="/properties" className="action-btn action-btn-primary">
            Browse properties
          </Link>
          <Link href="/assistant" className="action-btn action-btn-ghost">
            Ask the Awaaz assistant
          </Link>
        </div>
      </section>

      {/* Directory guidance */}
      <section className="directory-trust-strip" aria-label="Using the agent directory">
        <div className="trust-strip-item">
          <div className="trust-strip-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <path d="m9 12 2 2 4-4" />
            </svg>
          </div>
          <div>
            <h4 className="trust-strip-title">Choose an area</h4>
            <p className="trust-strip-desc">Find people covering the neighborhoods you have in mind.</p>
          </div>
        </div>

        <div className="trust-strip-item">
          <div className="trust-strip-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.2">
              <rect x="2" y="5" width="20" height="14" rx="2" />
              <line x1="2" y1="10" x2="22" y2="10" />
            </svg>
          </div>
          <div>
            <h4 className="trust-strip-title">Compare specialties</h4>
            <p className="trust-strip-desc">See the property types and services listed on each profile.</p>
          </div>
        </div>

        <div className="trust-strip-item">
          <div className="trust-strip-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.2">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
          </div>
          <div>
            <h4 className="trust-strip-title">Talk directly</h4>
            <p className="trust-strip-desc">Use the contact options shown on an agency or agent profile.</p>
          </div>
        </div>

        <div className="trust-strip-item">
          <div className="trust-strip-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.2">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
          </div>
          <div>
            <h4 className="trust-strip-title">Explore with Awaaz</h4>
            <p className="trust-strip-desc">Search published properties or ask our voice assistant for help.</p>
          </div>
        </div>
      </section>

      {/* Interactive Directory Explorer */}
      <AgentsDirectoryExplorer agencies={orgs} agents={people} />

      {/* Practical due diligence guidance */}
      <section className="directory-governance-section">
        <div className="governance-inner">
          <span className="directory-kicker">Before you decide</span>
          <h3 className="governance-heading">
            Keep your property search grounded
          </h3>
          <p className="governance-subheading">
            Agent profiles help you find someone to speak with. They are not proof of a property’s ownership, legal status, approvals, or current availability. Verify documents and claims independently before paying or signing.
          </p>

          <div className="governance-pillars-grid">
            <div className="gov-pillar">
              <div className="gov-num">01</div>
              <h4 className="gov-title">Check the documents</h4>
              <p className="gov-desc">
                Confirm ownership, transferability, dues, and approvals with the relevant authority and a qualified professional.
              </p>
            </div>

            <div className="gov-pillar">
              <div className="gov-num">02</div>
              <h4 className="gov-title">Visit the property</h4>
              <p className="gov-desc">
                Check the location, condition, access, and utilities yourself before making a commitment.
              </p>
            </div>

            <div className="gov-pillar">
              <div className="gov-num">03</div>
              <h4 className="gov-title">Agree on the terms</h4>
              <p className="gov-desc">
                Ask who the agent represents, confirm fees in writing, and keep receipts for every payment.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Institutional Partnership CTA */}
      <section className="directory-partner-cta">
        <div className="partner-cta-content">
          <span className="partner-kicker">For property professionals</span>
          <h3 className="partner-title">Help more people find your listings</h3>
          <p className="partner-desc">
            Agencies and agents serving Islamabad or Rawalpindi can contact our team about joining the directory and sharing their property listings.
          </p>
        </div>
        <div className="partner-cta-actions">
          <Link href="/contact" className="action-btn action-btn-primary">
            Contact our team →
          </Link>
          <Link href="/sell" className="action-btn action-btn-ghost">
            List Private Inventory
          </Link>
        </div>
      </section>
    </div>
  );
}
