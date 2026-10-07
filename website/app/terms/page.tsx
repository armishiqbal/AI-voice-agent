import Link from "next/link";
import { metadata } from "@/lib/site";

export const generateMetadata = () =>
  metadata(
    "Website terms",
    "Terms for browsing published listings, contacting agencies, and requesting a property viewing.",
    "/terms"
  );

export default function Terms() {
  return (
    <div className="legal-page-wrapper">
      <div className="container">
        <article className="legal-document-card">
          <header className="legal-header">
            <div className="legal-badge"><span>Website use · Property marketplace</span></div>
            <h1 className="legal-title">Terms of use</h1>
            <p className="legal-meta">Have the operating company review and approve these terms before launch.</p>
          </header>
          <div className="prose legal-prose">
            <section className="legal-section">
              <h2>Listings and property information</h2>
              <p>Listings are submitted by agencies and published after Awaaz Estate’s review. Availability, asking prices, descriptions, sizes, photos, publisher details, and verification labels are provided for property discovery and can change. Review labels describe only the evidence and date shown with that listing; they are not a guarantee of title, planning approval, condition, value, or legal status.</p>
            </section>
            <section className="legal-section">
              <h2>Inquiries and viewing requests</h2>
              <p>An inquiry asks the listed agency or Awaaz Estate to follow up. A saved viewing reservation records a requested time against the agent’s configured schedule. It is not a sale, lease, or proof of external email or Calendar delivery. The reservation and delivery status are shown separately.</p>
            </section>
            <section className="legal-section">
              <h2>Prices and comparisons</h2>
              <p>Published prices are asking prices, not completed transaction prices or formal valuations. Property comparisons use information present in the published listings. Check the unit, rental period, availability, and details with the publisher before making a decision.</p>
            </section>
            <section className="legal-section">
              <h2>Accounts and alerts</h2>
              <p>Account features depend on their availability in this environment. Daily listing emails require a verified email address and separate consent. You can unsubscribe from an alert at any time; a message already accepted by an email provider may still be in transit.</p>
            </section>
            <section className="legal-section">
              <h2>Questions</h2>
              <p>For a listing, inquiry, or viewing question, use the <Link href="/contact">contact page</Link> or the contact details shown on the listing’s approved publisher profile.</p>
            </section>
          </div>
        </article>
      </div>
    </div>
  );
}
