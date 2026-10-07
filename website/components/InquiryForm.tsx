"use client";
import { useRef, useState, type FormEvent } from "react";

export function InquiryForm({ listingId, listingTitle, recipient = "Awaaz Estate" }: { listingId?: string; listingTitle?: string; recipient?: string }) {
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [complete, setComplete] = useState(false);
  const submission = useRef<{ fingerprint: string; key: string } | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!form.reportValidity()) return;
    setPending(true);
    setFeedback("");
    const data = new FormData(form);
    const contactEmail = String(data.get("contact_email") || "").trim();
    const contactPhone = String(data.get("contact_phone") || "").trim();
    const preference = String(data.get("contact_preference") || "email");
    const requestType = listingId ? "property" : String(data.get("request_type") || "general");
    if (
      (!contactEmail && !contactPhone) ||
      (preference === "email" && !contactEmail) ||
      (preference !== "email" && !contactPhone)
    ) {
      setPending(false);
      setFeedback("Please provide an email or phone number that matches your contact preference.");
      return;
    }
    const payload = {
      ...(listingId ? { property_id: listingId } : {}),
      request_type: requestType === "seller" ? "seller" : listingId ? "property" : "general",
      client_name: String(data.get("client_name") || "").trim(),
      contact_email: contactEmail || undefined,
      contact_phone: contactPhone || undefined,
      contact_preference: preference,
      message: String(data.get("message") || "").trim(),
      consent: data.get("consent") === "on",
      consent_version: "2026-10-03",
    };
    const fingerprint = JSON.stringify(payload);
    if (submission.current?.fingerprint !== fingerprint)
      submission.current = { fingerprint, key: crypto.randomUUID() };
    try {
      const response = await fetch("/api/inquiries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...payload, idempotency_key: submission.current.key }),
        signal: AbortSignal.timeout(12000),
      });
      if (!response.ok) {
        setFeedback(
          response.status === 422
            ? "Please check your contact details and consent, then try again."
            : response.status === 429
            ? "Too many requests. Please wait a moment and try again."
            : "Your inquiry could not be saved. Please try again later."
        );
        return;
      }
      setComplete(true);
      setFeedback("Your inquiry has been recorded. The team will follow up using your selected contact method. This does not reserve a viewing.");
    } catch {
      setFeedback("We could not confirm your inquiry was saved. You can retry safely with the same details.");
    } finally {
      setPending(false);
    }
  }

  if (complete) {
    return (
      <div className="inquiry-success-box" role="status">
        <div className="success-icon-wrap">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        </div>
        <h3 className="success-title">Inquiry recorded</h3>
        <p className="success-desc">{feedback}</p>
      </div>
    );
  }

  return (
    <form className="form-stack inquiry-form-stack" onSubmit={submit}>
      <p>Your request will be received by {recipient}.</p>
      {listingTitle && (
        <div className="inquiry-listing-tag">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
          </svg>
          <span>Property: <strong>{listingTitle}</strong></span>
        </div>
      )}

      <label className="field">
          <span className="field-label">Your name *</span>
        <input
          name="client_name"
          autoComplete="name"
          required
          minLength={2}
          maxLength={100}
          placeholder="e.g. Aisha Khan"
        />
      </label>

      <div className="form-grid-2col">
        <label className="field">
          <span className="field-label">Email address</span>
          <input
            name="contact_email"
            type="email"
            autoComplete="email"
            maxLength={254}
            placeholder="tariq@example.com"
          />
        </label>

        <label className="field">
          <span className="field-label">Phone or WhatsApp</span>
          <input
            name="contact_phone"
            type="tel"
            autoComplete="tel"
            maxLength={32}
            placeholder="+92 300 1234567"
          />
        </label>
      </div>

      {!listingId && (
        <label className="field">
          <span className="field-label">What can we help with?</span>
          <select name="request_type" defaultValue="general">
            <option value="general">Finding or asking about a property</option>
            <option value="seller">I’d like to sell a property</option>
          </select>
        </label>
      )}

      <label className="field">
        <span className="field-label">How should we contact you?</span>
        <select name="contact_preference" defaultValue="email">
          <option value="email">Email</option>
          <option value="phone">Phone call</option>
          <option value="whatsapp">WhatsApp</option>
        </select>
      </label>

      <label className="field">
        <span className="field-label">Your message *</span>
        <textarea
          name="message"
          rows={4}
          maxLength={1000}
          required
          placeholder={
            listingId
              ? "Tell us what you’d like to know about this property or when you’d like to view it."
              : "Share the area, budget, property type, or question you have in mind."
          }
        />
      </label>

      <label className="checkbox">
        <input name="consent" type="checkbox" required />
        <span>
          I agree to {recipient} and Awaaz Estate using these details to respond to my inquiry in accordance with the{" "}
          <a href="/privacy" className="text-link">Privacy notice</a>.
        </span>
      </label>

      <button className="button full-width" disabled={pending} type="submit">
        {pending ? (
          <span className="button-loading-content">
            <svg className="spinner-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M21 12a9 9 0 1 1-6.219-8.56" />
            </svg>
            Sending inquiry…
          </span>
        ) : (
          <span>Send inquiry <span aria-hidden="true">→</span></span>
        )}
      </button>

      {feedback && (
        <div className="form-error-alert" role="alert">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <span>{feedback}</span>
        </div>
      )}
    </form>
  );
}
