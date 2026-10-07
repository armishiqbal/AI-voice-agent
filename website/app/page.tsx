import Link from "next/link";
import { listings } from "@/lib/catalog";
import { metadata } from "@/lib/site";
import { ModernSearchConsole } from "@/components/ModernSearchConsole";
import { MarketMetricsBar } from "@/components/MarketMetricsBar";
import { FeaturedInventoryTabs } from "@/components/FeaturedInventoryTabs";
import { NeighborhoodExplorer } from "@/components/NeighborhoodExplorer";
import { HowAwaazWorks } from "@/components/HowAwaazWorks";
import { VoiceAssistantBanner } from "@/components/VoiceAssistantBanner";
import { SellerConciergeBanner } from "@/components/SellerConciergeBanner";
import { AdvisoryCovenantSection } from "@/components/AdvisoryCovenantSection";

export const dynamic = "force-dynamic";

export const generateMetadata = () =>
  metadata(
    "Awaaz Estate · Verified Real Estate in Islamabad & Rawalpindi",
    "Explore physical on-site audited villas, luxury apartments, and corporate offices across Islamabad & Rawalpindi with transparent title scrutiny and direct licensed representation.",
    "/"
  );

export default async function Home() {
  const catalog = await listings({ page_size: "12", sort: "newest" }).catch(() => null);

  return (
    <>
      {/* 1. Hero & Modern Search Console */}
      <section className="modern-hero">
        <div className="container">
          <div className="hero-text-block">
            <span className="hero-pill-badge">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              Pakistan&apos;s Premier Verified Real Estate Exchange
            </span>
            <h1 className="hero-main-title">
              Find your <span className="hero-gradient-text">next chapter</span> in verified luxury.
            </h1>
            <p className="hero-subtitle">
              Explore rigorously audited residential and commercial properties across Islamabad and Rawalpindi. Transparent title provenance, physical on-site surveys, and direct licensed representation.
            </p>
          </div>

          <ModernSearchConsole />
        </div>
      </section>

      {/* 2. Institutional Operational Indicators */}
      <MarketMetricsBar />

      {/* 3. Actual Properties: Featured Inventory Tabs */}
      <section className="section container">
        <div className="section-heading-modern">
          <div>
            <span className="section-eyebrow">Direct Agency Inventory</span>
            <h2 className="section-title">Featured Real Estate in Islamabad &amp; Rawalpindi</h2>
            <p className="section-subtitle">Every active listing is physically inspected with confirmed civic documentation.</p>
          </div>
        </div>

        <FeaturedInventoryTabs properties={catalog?.data ?? []} />
      </section>

      {/* 4. Covered Areas: Neighborhood Explorer */}
      <section className="section container">
        <div className="section-heading">
          <div>
            <span className="section-eyebrow">Prime Locations</span>
            <h2>Architectural Neighborhood Guides</h2>
            <p>Explore master-planned gated enclaves, diplomatic sectors, and investment corridors.</p>
          </div>
          <Link className="button secondary small" href="/areas">
            Explore All Areas →
          </Link>
        </div>

        <NeighborhoodExplorer />
      </section>

      {/* 5. How It Works: Clear Institutional Process */}
      <section className="section container">
        <HowAwaazWorks />
      </section>

      {/* 6. Optional Voice Assistant Banner */}
      <section className="section container">
        <VoiceAssistantBanner />
      </section>

      {/* 7. Seller Concierge: Developer & Owner Submission */}
      <section className="section container">
        <SellerConciergeBanner />
      </section>

      {/* 8. Company Contacts & Verification Covenant */}
      <section className="section container">
        <AdvisoryCovenantSection />
      </section>
    </>
  );
}
