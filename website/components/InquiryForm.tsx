"use client";
import { useRef, useState, type FormEvent } from "react";
export function InquiryForm({ listingId, listingTitle }: { listingId?: string; listingTitle?: string }) {
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [complete, setComplete] = useState(false);
  const submission = useRef<{ fingerprint: string; key: string } | null>(null);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!form.reportValidity()) return;
    setPending(true); setFeedback("");
    const data = new FormData(form);
    const contactEmail = String(data.get("contact_email") || "").trim();
    const contactPhone = String(data.get("contact_phone") || "").trim();
    const preference = String(data.get("contact_preference") || "email");
    if ((!contactEmail && !contactPhone) || (preference === "email" && !contactEmail) || (preference !== "email" && !contactPhone)) { setPending(false); setFeedback("Add an email or phone number that matches your contact preference."); return; }
    const payload = { ...(listingId ? { property_id: listingId } : {}), request_type: listingId ? "property" : "general", client_name: String(data.get("client_name") || "").trim(), contact_email: contactEmail || undefined, contact_phone: contactPhone || undefined, contact_preference: preference, message: String(data.get("message") || "").trim(), consent: data.get("consent") === "on", consent_version: "2026-10-03" };
    const fingerprint = JSON.stringify(payload);
    if (submission.current?.fingerprint !== fingerprint) submission.current = { fingerprint, key: crypto.randomUUID() };
    try {
      const response = await fetch("/api/inquiries", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...payload, idempotency_key: submission.current.key }), signal: AbortSignal.timeout(12000) });
      if (!response.ok) { setFeedback(response.status === 422 ? "Please check your contact details and consent, then try again." : response.status === 429 ? "Too many requests. Please wait a moment and try again." : "Your inquiry could not be saved. Please try again later or use the contact details below."); return; }
      setComplete(true); setFeedback("Your inquiry has been recorded. Our team will review your requirements. A viewing is confirmed separately.");
    } catch { setFeedback("We could not confirm your inquiry was saved. You can retry safely with the same details."); }
    finally { setPending(false); }
  }
  if (complete) return <p className="available-note" role="status">{feedback}</p>;
  return <form className="form-stack" onSubmit={submit}>
    {listingTitle && <p className="quiet">About: {listingTitle}</p>}
    <label className="field">Your name<input name="client_name" autoComplete="name" required minLength={2} maxLength={100} /></label>
    <p className="quiet">Provide at least one contact method.</p>
    <label className="field">Email address<input name="contact_email" type="email" autoComplete="email" maxLength={254} /></label>
    <label className="field">Phone number<input name="contact_phone" type="tel" autoComplete="tel" maxLength={32} placeholder="+92…" /></label>
    <label className="field">Contact preference<select name="contact_preference"><option value="email">Email</option><option value="phone">Phone call</option><option value="whatsapp">WhatsApp</option></select></label>
    <label className="field">How can we help?<textarea name="message" rows={4} maxLength={1000} required placeholder={listingId ? "Ask a question or tell us your preferred viewing time." : "Tell us your location, budget and property requirements."} /></label>
    <label className="checkbox"><input name="consent" type="checkbox" required /><span>I agree to Awaaz Estate using these details to respond to this inquiry. <a href="/privacy">Privacy notice</a></span></label>
    <button className="button" disabled={pending} type="submit">{pending ? "Sending inquiry…" : "Send inquiry"}</button>
    {feedback && <p className="form-message" role="alert">{feedback}</p>}
  </form>;
}
