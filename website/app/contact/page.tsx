import { metadata } from "@/lib/site";
import { InquiryForm } from "@/components/InquiryForm";
export const generateMetadata = () => metadata("Contact our team", "Ask about a listing, share your property requirements or request a callback.", "/contact");
export default function Contact() {
  const email = process.env.CONTACT_EMAIL || process.env.NEXT_PUBLIC_CONTACT_EMAIL;
  const phone = process.env.CONTACT_PHONE || process.env.NEXT_PUBLIC_CONTACT_PHONE;
  return <section className="section container"><p className="eyebrow">Let’s find your next place</p><h1>Contact Awaaz Estate</h1><div className="detail-layout"><div><h2>Tell us what you need</h2><p>Share your preferred area, budget and property type. For a specific property, send an inquiry from its listing page.</p><p>Inquiry requests are reviewed by our team. Sending a message does not confirm a viewing or reserve a property.</p><div className="contact-options">{email && <a className="button secondary" href={`mailto:${email}`}>Email our team</a>}{phone && <a className="button secondary" href={`tel:${phone}`}>Call our team</a>}</div>{!email && !phone && <p className="quiet">Direct contact details have not yet been published.</p>}</div><div className="inquiry-panel"><h2>Your requirements</h2><InquiryForm /></div></div></section>;
}
