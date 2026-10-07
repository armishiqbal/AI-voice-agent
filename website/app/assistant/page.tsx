import Link from "next/link";
import { metadata } from "@/lib/site";
import { LuxuryVoiceStudioClient } from "@/components/LuxuryVoiceStudioClient";

export const dynamic = "force-dynamic";

export const generateMetadata = () => ({
  ...metadata(
    "Property Assistant",
    "Search published Awaaz Estate listings by voice or text in English, Urdu, or Roman Urdu. Ask about buying, renting, financing, or viewings.",
    "/assistant"
  ),
  robots: { index: false, follow: true },
});

export default function AssistantPage() {
  const assistantUrl =
    process.env.ASSISTANT_URL ||
    process.env.NEXT_PUBLIC_ASSISTANT_URL ||
    (process.env.NODE_ENV === "production" ? "/assistant/" : "http://127.0.0.1:8000/assistant/");
  const conciergeEnabled = process.env.ASSISTANT_CONCIERGE_ENABLED === "true" || process.env.NODE_ENV !== "production";

  return (
    <section className="section container voice-studio-page-root">
      {/* Breadcrumb Navigation */}
      <nav className="breadcrumbs-modern" aria-label="Breadcrumb">
        <Link href="/">Home</Link>
        <span className="bc-sep">/</span>
        <span className="bc-current">Property assistant</span>
      </nav>

      {/* Modern Studio Hero Header */}
      <div className="voice-studio-hero">
        <div className="hero-eyebrow-pill">
          <span className="hero-eyebrow-dot" aria-hidden="true" />
          <span>Real estate help, in your language</span>
        </div>
        <h1 className="voice-studio-title">
          Tell Awaaz what you&rsquo;re looking for.
        </h1>
        <p className="voice-studio-subtitle">
          Search published listings in English, Urdu, or Roman Urdu. Mention your city, area, budget in PKR, and whether you want to buy or rent. Voice starts only when you choose it.
        </p>
      </div>

      {conciergeEnabled ? (
        <LuxuryVoiceStudioClient assistantUrl={assistantUrl} />
      ) : (
        <div className="assistant-rollout-message" role="status">
          <h2>Property assistance is being prepared</h2>
          <p>Browse published listings while the assistant service is unavailable in this environment.</p>
          <Link className="button" href="/properties">Browse properties</Link>
        </div>
      )}
    </section>
  );
}
