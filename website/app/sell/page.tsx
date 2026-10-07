import Link from "next/link";
import { SellerSubmissionWizard } from "@/components/SellerSubmissionWizard";
import { metadata } from "@/lib/site";

export const generateMetadata = () =>
  metadata(
    "Sell or Rent Out Your Property",
    "Tell Awaaz Estate about a property you would like to sell or rent out in Islamabad or Rawalpindi. Share the basics and request a follow-up.",
    "/sell"
  );

const sellerSteps = [
  { number: "01", title: "Share the basics", description: "Tell us the property type, location, and how you want to proceed." },
  { number: "02", title: "We review your inquiry", description: "Our team reviews the details you send and follows up by phone." },
  { number: "03", title: "Discuss next steps", description: "Talk through pricing, documents, and representation before deciding how to proceed." },
];

export default function SellPage() {
  return (
    <main className="seller-page container">
      <nav className="breadcrumbs" aria-label="Breadcrumb">
        <Link href="/">Home</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">Sell</span>
      </nav>

      <section className="seller-intro" aria-labelledby="seller-page-title">
        <div className="seller-intro-copy">
          <span className="seller-page-kicker">For property owners</span>
          <h1 className="seller-page-title" id="seller-page-title">
            A clear next step for <em>your property.</em>
          </h1>
          <p className="seller-page-lede">
            Thinking of selling or renting out in Islamabad or Rawalpindi? Share a few details and the Awaaz Estate team can get in touch to discuss what comes next.
          </p>
          <a className="button primary seller-intro-cta" href="#seller-inquiry">Tell us about your property <span aria-hidden="true">↓</span></a>
        </div>

        <aside className="seller-process-card" aria-labelledby="seller-process-title">
          <span className="seller-form-eyebrow">A straightforward process</span>
          <h2 id="seller-process-title">From inquiry to conversation</h2>
          <ol>
            {sellerSteps.map((step) => (
              <li key={step.number}>
                <span className="seller-process-number">{step.number}</span>
                <div><strong>{step.title}</strong><p>{step.description}</p></div>
              </li>
            ))}
          </ol>
          <p className="seller-process-note">Sending an inquiry does not publish your property or commit you to representation.</p>
        </aside>
      </section>

      <div id="seller-inquiry" className="seller-inquiry-layout">
        <div className="seller-form-aside">
          <span className="seller-form-eyebrow">Start here</span>
          <h2>Give us the essentials.</h2>
          <p>Price and size are optional. If you are still working those out, send the request anyway and discuss them with the team.</p>
          <div className="seller-aside-links">
            <Link href="/properties">Browse current properties <span aria-hidden="true">↗</span></Link>
            <Link href="/assistant">Ask the property assistant <span aria-hidden="true">↗</span></Link>
          </div>
        </div>
        <SellerSubmissionWizard />
      </div>
    </main>
  );
}
