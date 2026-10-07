import Link from "next/link";
import { metadata } from "@/lib/site";
import { InquiryForm } from "@/components/InquiryForm";

export const dynamic = "force-dynamic";

export const generateMetadata = () =>
  metadata(
    "Contact Awaaz Estate",
    "Ask about a company property listing, arrange a viewing, or contact Awaaz Estate about selling your property.",
    "/contact"
  );

function cleanPhone(value: string): string {
  return value.replace(/[^0-9+]/g, "");
}

function whatsappNumber(value: string): string {
  return value.replace(/[^0-9]/g, "");
}

export default function Contact() {
  const email = process.env.CONTACT_EMAIL?.trim() || "";
  const phone = process.env.CONTACT_PHONE?.trim() || "";
  const whatsapp = process.env.CONTACT_WHATSAPP?.trim() || "";
  const hasDirectContact = Boolean(email || phone || whatsapp);

  return (
    <section className="contact-page">
      <div className="container">
        <nav className="contact-breadcrumbs" aria-label="Breadcrumb">
          <Link href="/">Home</Link><span aria-hidden="true">/</span><span aria-current="page">Contact</span>
        </nav>

        <header className="contact-hero">
          <div className="contact-hero-copy">
            <p className="contact-kicker"><span aria-hidden="true" /> Awaaz Estate · Pakistan</p>
            <h1>Let’s talk about <em>property.</em></h1>
            <p className="contact-lede">Ask about a listing, arrange a viewing, or tell us what you’re looking for. Choose the contact route that works for you.</p>
            <div className="contact-hero-actions">
              <a className="contact-primary-link" href="#contact-form">Send an inquiry <span aria-hidden="true">↘</span></a>
              <Link className="contact-secondary-link" href="/properties">Browse properties <span aria-hidden="true">→</span></Link>
            </div>
          </div>
          <aside className="contact-region-card" aria-label="Awaaz Estate service area">
            <span className="contact-region-index">SERVICE AREA / PK</span>
            <div className="contact-region-names"><span>Find your area</span></div>
            <div className="contact-region-rule" /><Link href="/service-area">See current coverage →</Link>
            <p>Explore approved agency coverage and published inventory.</p>
          </aside>
        </header>

        <div className="contact-main-grid">
          <aside className="contact-side-column" aria-label="Ways to contact Awaaz Estate">
            <div className="contact-section-heading">
              <span>01 / REACH OUR TEAM</span>
              <h2>Choose your route</h2>
            </div>

            <div className="contact-channel-list">
              {phone && (
                <a className="contact-channel-card" href={`tel:${cleanPhone(phone)}`}>
                  <span className="contact-channel-icon" aria-hidden="true">↗</span>
                  <span className="contact-channel-copy"><small>PHONE</small><strong>{phone}</strong><span>Call the team</span></span>
                  <span className="contact-channel-arrow" aria-hidden="true">↗</span>
                </a>
              )}
              {email && (
                <a className="contact-channel-card" href={`mailto:${email}`}>
                  <span className="contact-channel-icon" aria-hidden="true">@</span>
                  <span className="contact-channel-copy"><small>EMAIL</small><strong>{email}</strong><span>Write to the team</span></span>
                  <span className="contact-channel-arrow" aria-hidden="true">↗</span>
                </a>
              )}
              {whatsapp && (
                <a className="contact-channel-card" href={`https://wa.me/${whatsappNumber(whatsapp)}`} target="_blank" rel="noopener noreferrer">
                  <span className="contact-channel-icon" aria-hidden="true">W</span>
                  <span className="contact-channel-copy"><small>WHATSAPP</small><strong>{whatsapp}</strong><span>Start a conversation</span></span>
                  <span className="contact-channel-arrow" aria-hidden="true">↗</span>
                </a>
              )}
              {!hasDirectContact && (
                <div className="contact-channel-empty">
                  <span className="contact-channel-empty-mark" aria-hidden="true">i</span>
                  <p><strong>Use the inquiry form to reach us.</strong> Direct phone, email, and WhatsApp details aren’t configured for this site yet.</p>
                </div>
              )}
            </div>

            <div className="contact-note-card">
              <span className="contact-note-mark" aria-hidden="true">↳</span>
              <div><strong>Looking at a specific property?</strong><p>Open its listing to check the current availability and request a viewing.</p><Link href="/properties">Explore the catalog <span aria-hidden="true">→</span></Link></div>
            </div>

            <p className="contact-availability-note">Sending an inquiry does not reserve a viewing. We’ll confirm viewing availability separately.</p>
          </aside>

          <section className="contact-form-panel" id="contact-form" aria-labelledby="contact-form-title">
            <div className="contact-form-heading">
              <div><span>02 / YOUR MESSAGE</span><h2 id="contact-form-title">How can we help?</h2></div>
              <span className="contact-form-index" aria-hidden="true">AE</span>
            </div>
            <p className="contact-form-intro">Share a few details and tell us how you’d like the team to follow up.</p>
            <InquiryForm />
            <p className="contact-privacy-note">Your contact details are used to respond to this inquiry. See our <Link href="/privacy">Privacy notice</Link>.</p>
          </section>
        </div>
      </div>
    </section>
  );
}
