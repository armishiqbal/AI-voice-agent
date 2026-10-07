import Link from "next/link";
import { metadata } from "@/lib/site";

export const generateMetadata = () =>
  metadata(
    "Privacy notice",
    "What Awaaz Estate collects when you browse, inquire, create an account, or use the property assistant.",
    "/privacy"
  );

export default function Privacy() {
  return (
    <div className="legal-page-wrapper">
      <div className="container">
        <article className="legal-document-card">
          <header className="legal-header">
            <div className="legal-badge"><span>Privacy · Website and marketplace</span></div>
            <h1 className="legal-title">Privacy notice</h1>
            <p className="legal-meta">Review this notice with the operating team before public launch.</p>
          </header>
          <div className="prose legal-prose">
            <section className="legal-section">
              <h2>Information you provide</h2>
              <p>When you send an inquiry or request a viewing, the site asks for contact details, a preferred contact method, a message, and consent to handle the request. Verified accounts can also store favorites, searches, viewing records, and separate consent for listing email alerts.</p>
            </section>
            <section className="legal-section">
              <h2>Who receives a property inquiry</h2>
              <p>A request about an agency listing is routed to that listing’s approved agency and assigned agent. General questions and seller requests go to Awaaz Estate for review. Contact details are used to process and follow up on the request; they are not a public part of a listing.</p>
            </section>
            <section className="legal-section">
              <h2>Assistant and external services</h2>
              <p>The property assistant accepts text and, when enabled, microphone input. Conversation text may be retained in redacted form for up to 30 days to support the conversation service. Speech, identity, storage, email, and Calendar features may use the providers configured by the operator. Their active providers and terms must be confirmed before launch. The website does not promise that an external notification was delivered merely because a request was saved.</p>
            </section>
            <section className="legal-section">
              <h2>Retention and account controls</h2>
              <p>Public inquiries expire after one year; the background worker then removes their encrypted contact fields and inquiry message. Contact fields for canceled or completed viewing records are removed one year after closure. Delivered notification events have contact payloads removed after 30 days. The worker must be running for cleanup to occur. Active bookings and customer account profiles remain available for their current service purpose; their end-of-service deletion schedule and backup retention require operator review before launch.</p>
            </section>
            <section className="legal-section">
              <h2>Questions and requests</h2>
              <p>Use the <Link href="/contact">contact form</Link> to ask about the information associated with your request. The operator must publish verified business contact details and confirm the process for access, correction, deletion, and privacy requests before launch.</p>
            </section>
          </div>
        </article>
      </div>
    </div>
  );
}
