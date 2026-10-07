"use client";

import { useRef, useState, type FormEvent } from "react";
import { formatPkrShort } from "@/lib/site";

type SellerRequest = {
  client_name: string;
  contact_email?: string;
  contact_phone: string;
  contact_preference: "phone" | "email";
  request_type: "seller";
  message: string;
  consent: true;
  consent_version: "2026-10-03";
};

export function SellerSubmissionWizard() {
  const [transaction, setTransaction] = useState<"sale" | "rent">("sale");
  const [propertyType, setPropertyType] = useState("");
  const [city, setCity] = useState("");
  const [area, setArea] = useState("");
  const [size, setSize] = useState("");
  const [sizeUnit, setSizeUnit] = useState("marla");
  const [askingPrice, setAskingPrice] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [details, setDetails] = useState("");
  const [consent, setConsent] = useState(false);
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const submission = useRef<{ fingerprint: string; key: string } | null>(null);

  function resetForm() {
    setTransaction("sale");
    setPropertyType("");
    setCity("");
    setArea("");
    setSize("");
    setSizeUnit("marla");
    setAskingPrice("");
    setName("");
    setPhone("");
    setEmail("");
    setDetails("");
    setConsent(false);
    setSubmitted(false);
    submission.current = null;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setFeedback("");

    const price = Number(askingPrice);
    const propertySummary = [
      `Request: ${transaction === "sale" ? "sell" : "rent out"} a property`,
      `Property type: ${propertyType}`,
      `Location: ${area}, ${city}`,
      size ? `Size: ${size} ${sizeUnit}` : "",
      Number.isFinite(price) && price > 0
        ? `Expected ${transaction === "sale" ? "sale price" : "monthly rent"}: PKR ${price}`
        : "",
      details.trim() ? `Additional details: ${details.trim()}` : "",
    ].filter(Boolean).join("\n");

    const payload: SellerRequest = {
      client_name: name.trim(),
      contact_email: email.trim() || undefined,
      contact_phone: phone.trim(),
      contact_preference: "phone",
      request_type: "seller",
      message: propertySummary.slice(0, 1000),
      consent: true,
      consent_version: "2026-10-03",
    };
    const fingerprint = JSON.stringify(payload);
    if (submission.current?.fingerprint !== fingerprint) {
      submission.current = { fingerprint, key: crypto.randomUUID() };
    }

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
            ? "Please check the details and consent, then try again."
            : response.status === 429
              ? "Too many requests. Please wait a moment and try again."
              : "We couldn’t save your request. Please try again later."
        );
        return;
      }
      setSubmitted(true);
    } catch {
      setFeedback("We couldn’t confirm that your request was saved. You can retry safely with the same details.");
    } finally {
      setPending(false);
    }
  }

  if (submitted) {
    return (
      <section className="seller-form-panel seller-confirmation" role="status" aria-live="polite">
        <span className="seller-form-eyebrow">Request received</span>
        <h2>Thanks, {name.trim()}.</h2>
        <p>Your property inquiry has been recorded. The Awaaz Estate team can follow up by phone using the number you provided.</p>
        <button type="button" className="button secondary" onClick={resetForm}>
          Submit another property
        </button>
      </section>
    );
  }

  return (
    <section className="seller-form-panel" aria-labelledby="seller-form-title">
      <div className="seller-form-heading">
        <span className="seller-form-eyebrow">Property details</span>
        <h2 id="seller-form-title">Tell us what you’re selling</h2>
        <p>Share a few basics. You can add more detail when the team gets in touch.</p>
      </div>

      <form className="seller-request-form" onSubmit={handleSubmit}>
        <fieldset className="seller-form-group">
          <legend>What would you like to do?</legend>
          <div className="seller-transaction-options">
            <label className={transaction === "sale" ? "selected" : ""}>
              <input type="radio" name="transaction" value="sale" checked={transaction === "sale"} onChange={() => setTransaction("sale")} />
              <span>Sell a property</span>
            </label>
            <label className={transaction === "rent" ? "selected" : ""}>
              <input type="radio" name="transaction" value="rent" checked={transaction === "rent"} onChange={() => setTransaction("rent")} />
              <span>Rent out a property</span>
            </label>
          </div>
        </fieldset>

        <div className="seller-fields-grid">
          <label className="seller-field">
            <span>Property type <b aria-hidden="true">*</b></span>
            <select value={propertyType} onChange={(event) => setPropertyType(event.target.value)} required>
              <option value="" disabled>Select a property type</option>
              <option>House</option>
              <option>Apartment</option>
              <option>Plot</option>
              <option>Farmhouse</option>
              <option>Shop or office</option>
              <option>Other</option>
            </select>
          </label>
          <label className="seller-field">
            <span>City <b aria-hidden="true">*</b></span>
            <select value={city} onChange={(event) => setCity(event.target.value)} required>
              <option value="" disabled>Select a city</option>
              <option>Islamabad</option>
              <option>Rawalpindi</option>
              <option>Other</option>
            </select>
          </label>
          <label className="seller-field">
            <span>Area, sector, or society <b aria-hidden="true">*</b></span>
            <input value={area} onChange={(event) => setArea(event.target.value)} maxLength={120} placeholder="e.g. DHA Phase 2, F-10" required />
          </label>
          <div className="seller-field">
            <span>Approximate size <small>(optional)</small></span>
            <div className="seller-size-control">
              <input type="number" min="1" step="any" value={size} onChange={(event) => setSize(event.target.value)} placeholder="e.g. 10" aria-label="Approximate property size" />
              <select value={sizeUnit} onChange={(event) => setSizeUnit(event.target.value)} aria-label="Property size unit">
                <option value="marla">Marla</option>
                <option value="kanal">Kanal</option>
                <option value="sq ft">Sq ft</option>
              </select>
            </div>
          </div>
          <label className="seller-field seller-field-wide">
            <span>Expected {transaction === "sale" ? "price" : "monthly rent"} in PKR <small>(optional)</small></span>
            <input type="number" min="1" step="any" value={askingPrice} onChange={(event) => setAskingPrice(event.target.value)} placeholder="Leave blank if you’re unsure" />
            {Number(askingPrice) > 0 && <small className="seller-price-hint">About {formatPkrShort(Number(askingPrice))} PKR</small>}
          </label>
        </div>

        <div className="seller-form-divider" />
        <div className="seller-form-heading seller-contact-heading">
          <span className="seller-form-eyebrow">Your contact details</span>
          <h3>How can we reach you?</h3>
        </div>
        <div className="seller-fields-grid">
          <label className="seller-field">
            <span>Your name <b aria-hidden="true">*</b></span>
            <input value={name} onChange={(event) => setName(event.target.value)} autoComplete="name" minLength={2} maxLength={100} placeholder="Full name" required />
          </label>
          <label className="seller-field">
            <span>Phone or WhatsApp <b aria-hidden="true">*</b></span>
            <input type="tel" value={phone} onChange={(event) => setPhone(event.target.value)} autoComplete="tel" maxLength={32} pattern="[+]?[0-9 ()-]{7,32}" placeholder="+92 300 1234567" required />
          </label>
          <label className="seller-field seller-field-wide">
            <span>Email address <small>(optional)</small></span>
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" maxLength={254} placeholder="you@example.com" />
          </label>
          <label className="seller-field seller-field-wide">
            <span>Anything else we should know? <small>(optional)</small></span>
            <textarea value={details} onChange={(event) => setDetails(event.target.value)} rows={3} maxLength={600} placeholder="Condition, occupancy, or questions for the team" />
          </label>
        </div>

        <label className="seller-consent">
          <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} required />
          <span>I agree that Awaaz Estate may use these details to respond to my seller inquiry, as described in the <a href="/privacy">Privacy notice</a>.</span>
        </label>

        {feedback && <p className="seller-form-error" role="alert">{feedback}</p>}
        <div className="seller-form-submit-row">
          <button className="button primary" type="submit" disabled={pending || !consent}>
            {pending ? "Sending request…" : "Send property inquiry"}<span aria-hidden="true"> →</span>
          </button>
          <p>Your details are sent to the Awaaz Estate inquiry service.</p>
        </div>
      </form>
    </section>
  );
}
