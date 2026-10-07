"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { InquiryForm } from "@/components/InquiryForm";

type ViewingWidgetProps = {
  recipient?: string;
  propertyId: string;
  propertyTitle: string;
  isAvailable: boolean;
  initialSlots?: string[];
};

export function ViewingWidget({
  recipient = "Awaaz Estate",
  propertyId,
  propertyTitle,
  isAvailable,
  initialSlots = [],
}: ViewingWidgetProps) {
  const [activeTab, setActiveTab] = useState<"viewing" | "inquiry">(
    isAvailable ? "viewing" : "inquiry"
  );
  const [slots, setSlots] = useState<string[]>(initialSlots);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState<string>(initialSlots[0] || "");

  // Booking form state
  const [clientName, setClientName] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [consent, setConsent] = useState(false);

  // OTP state
  const [otpSent, setOtpSent] = useState(false);
  const [otpCode, setOtpCode] = useState("");
  const [debugOtp, setDebugOtp] = useState<string | null>(null);
  const [verificationToken, setVerificationToken] = useState<string | null>(null);

  // Status state
  const [pending, setPending] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [receipt, setReceipt] = useState<{
    reference: string;
    starts_at: string;
    delivery_status: string;
  } | null>(null);

  const idempotencyKey = useRef<string>(crypto.randomUUID());

  useEffect(() => {
    if (initialSlots.length === 0 && isAvailable) {
      setLoadingSlots(true);
      fetch(`/api/public/listings/${encodeURIComponent(propertyId)}/slots`)
        .then((res) => (res.ok ? res.json() : { data: [] }))
        .then((data) => {
          if (Array.isArray(data.data)) {
            setSlots(data.data);
            if (data.data.length > 0) setSelectedSlot(data.data[0]);
          }
        })
        .catch(() => {})
        .finally(() => setLoadingSlots(false));
    }
  }, [propertyId, isAvailable]);

  function formatSlot(isoString: string): string {
    const d = new Date(isoString);
    if (!Number.isFinite(d.getTime())) return isoString;
    return new Intl.DateTimeFormat("en-PK", {
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZone: "Asia/Karachi",
    }).format(d) + " PKT";
  }

  async function handleRequestOtp(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedSlot) {
      setErrorMessage("Please select an available viewing slot.");
      return;
    }
    if (!clientName.trim() || clientName.trim().length < 2) {
      setErrorMessage("Please enter your full name.");
      return;
    }
    if (!contactEmail.trim() || !contactEmail.includes("@")) {
      setErrorMessage("Please enter a valid email address.");
      return;
    }
    if (!consent) {
      setErrorMessage("Please agree to the privacy and booking consent.");
      return;
    }

    setPending(true);
    setErrorMessage("");
    try {
      const res = await fetch("/api/viewings/request-otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: contactEmail.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        setErrorMessage(data.error || "Could not send verification code.");
        return;
      }
      setOtpSent(true);
      if (data.debug_otp) {
        setDebugOtp(data.debug_otp);
        setOtpCode(data.debug_otp); // auto-populate for ease in development
      }
    } catch {
      setErrorMessage("Network error. Please try again.");
    } finally {
      setPending(false);
    }
  }

  async function handleVerifyAndBook(e: React.FormEvent) {
    e.preventDefault();
    if (!otpCode.trim() || otpCode.trim().length !== 6) {
      setErrorMessage("Enter the 6-digit verification code sent to your email.");
      return;
    }

    setPending(true);
    setErrorMessage("");
    try {
      // 1. Verify OTP to obtain verification token
      let token = verificationToken;
      if (!token) {
        const verifyRes = await fetch("/api/viewings/verify-otp", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: contactEmail.trim(), otp: otpCode.trim() }),
        });
        const verifyData = await verifyRes.json();
        if (!verifyRes.ok) {
          setErrorMessage(verifyData.error || "Invalid or expired verification code.");
          setPending(false);
          return;
        }
        token = verifyData.verification_token;
        setVerificationToken(token);
      }

      // 2. Book viewing with verified token
      const bookRes = await fetch("/api/viewings/book", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          property_id: propertyId,
          starts_at: selectedSlot,
          client_name: clientName.trim(),
          contact_email: contactEmail.trim(),
          contact_phone: contactPhone.trim() || undefined,
          verification_token: token,
          consent: true,
          consent_version: "2026-10-03",
          idempotency_key: idempotencyKey.current,
        }),
      });
      const bookData = await bookRes.json();
      if (!bookRes.ok) {
        setErrorMessage(bookData.error || "Reservation failed. Please try another slot.");
        return;
      }

      setReceipt({
        reference: bookData.reference,
        starts_at: bookData.starts_at,
        delivery_status: bookData.delivery_status,
      });
    } catch {
      setErrorMessage("An unexpected error occurred during booking. Please retry.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="inquiry-panel">
      {/* Tabs */}
      <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
        <button
          type="button"
          onClick={() => setActiveTab("viewing")}
          className={`button small ${activeTab === "viewing" ? "" : "secondary"}`}
          style={{ flex: 1 }}
        >
          Book a Viewing
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("inquiry")}
          className={`button small ${activeTab === "inquiry" ? "" : "secondary"}`}
          style={{ flex: 1 }}
        >
          Ask a Question
        </button>
      </div>

      {activeTab === "inquiry" ? (
        <div>
          <h2>Ask about this property</h2>
          <p className="quiet" style={{ marginBottom: 16 }}>
            Our team will reply with details or alternatives within 1 business day.
          </p>
          <InquiryForm recipient={recipient} listingId={propertyId} listingTitle={propertyTitle} />
        </div>
      ) : receipt ? (
        <div style={{ textAlign: "center", padding: "10px 0" }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: "50%",
              backgroundColor: "var(--soft)",
              color: "var(--green)",
              display: "grid",
              placeItems: "center",
              fontSize: 28,
              margin: "0 auto 16px",
              fontWeight: "bold",
            }}
          >
            <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </div>
          <h2>Viewing Reserved</h2>
          <p style={{ fontSize: 16, marginBottom: 14 }}>
            Your appointment has been confirmed for:
          </p>
          <p className="badge" style={{ fontSize: 15, padding: "8px 14px", marginBottom: 16 }}>
            {formatSlot(receipt.starts_at)}
          </p>
          <div
            style={{
              background: "var(--paper)",
              padding: 16,
              borderRadius: 8,
              border: "1px solid var(--line)",
              marginBottom: 16,
              textAlign: "left",
            }}
          >
            <p style={{ margin: "0 0 8px", fontSize: 14 }}>
              <strong>Reservation Reference:</strong>{" "}
              <code style={{ fontSize: 15, color: "var(--green)", fontWeight: 700 }}>{receipt.reference}</code>
            </p>
            <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--line)", fontSize: 13, display: "flex", flexDirection: "column", gap: 6 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span className="status-dot available" />
                <span><strong>Agency Reservation:</strong> Confirmed &amp; saved in staff dispatch roster.</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--muted)" }}>
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <rect width="18" height="18" x="3" y="4" rx="2" ry="2" />
                  <line x1="16" y1="2" x2="16" y2="6" />
                  <line x1="8" y1="2" x2="8" y2="6" />
                  <line x1="3" y1="10" x2="21" y2="10" />
                </svg>
                <span>
                  <strong>Calendar Sync:</strong>{" "}
                  {receipt.delivery_status === "delivered"
                    ? "Calendar invitation delivered to your email."
                    : "Calendar invitation queued for delivery (your on-site visit is held regardless of external sync)."}
                </span>
              </div>
            </div>
          </div>
          <button
            type="button"
            className="button secondary small"
            onClick={() => {
              setReceipt(null);
              setOtpSent(false);
              setOtpCode("");
              setVerificationToken(null);
              idempotencyKey.current = crypto.randomUUID();
            }}
          >
            Book Another Visit
          </button>
        </div>
      ) : !isAvailable ? (
        <div>
          <h2>Viewing unavailable</h2>
          <p className="quiet">
            This property is not currently confirmed for in-person viewings. You can send an
            inquiry to check for upcoming status changes or alternative listings.
          </p>
          <button
            type="button"
            className="button secondary small"
            onClick={() => setActiveTab("inquiry")}
          >
            Switch to inquiry
          </button>
        </div>
      ) : (
        <div>
          <h2>Schedule a Private Visit</h2>
          <p className="quiet" style={{ marginBottom: 16 }}>
            Choose an available time slot and verify your contact details to reserve.
          </p>

          {!otpSent ? (
            <form className="form-stack" onSubmit={handleRequestOtp}>
              <div>
                <label className="field" style={{ marginBottom: 8 }}>
                  Select an available slot
                </label>
                {loadingSlots ? (
                  <p className="quiet">Loading available slots…</p>
                ) : slots.length === 0 ? (
                  <p className="quiet">
                    No immediate slots open this week.{" "}
                    <button
                      type="button"
                      style={{ background: "none", border: "none", color: "var(--green)", textDecoration: "underline", padding: 0 }}
                      onClick={() => setActiveTab("inquiry")}
                    >
                      Send an inquiry
                    </button>{" "}
                    to request a custom time.
                  </p>
                ) : (
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr",
                      gap: 8,
                      maxHeight: 180,
                      overflowY: "auto",
                      padding: 4,
                      marginBottom: 8,
                    }}
                  >
                    {slots.map((slot) => {
                      const isSelected = selectedSlot === slot;
                      return (
                        <button
                          key={slot}
                          type="button"
                          onClick={() => setSelectedSlot(slot)}
                          style={{
                            textAlign: "left",
                            padding: "10px 14px",
                            borderRadius: 8,
                            fontSize: 14,
                            fontWeight: isSelected ? 600 : 400,
                            border: isSelected ? "2px solid var(--green)" : "1px solid var(--line)",
                            background: isSelected ? "var(--soft)" : "var(--white)",
                            color: isSelected ? "var(--green-dark)" : "var(--ink)",
                            cursor: "pointer",
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                          }}
                        >
                          <span>{formatSlot(slot)}</span>
                          {isSelected && (
                            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
                              <polyline points="20 6 9 17 4 12" />
                            </svg>
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              <label className="field">
                Your full name
                <input
                  name="client_name"
                  value={clientName}
                  onChange={(e) => setClientName(e.target.value)}
                  placeholder="e.g. Tariq Ahmed"
                  required
                  minLength={2}
                  maxLength={100}
                />
              </label>

              <label className="field">
                Email address (for verification & calendar invite)
                <input
                  name="contact_email"
                  type="email"
                  value={contactEmail}
                  onChange={(e) => setContactEmail(e.target.value)}
                  placeholder="name@example.com"
                  required
                  maxLength={254}
                />
              </label>

              <label className="field">
                Phone number (optional)
                <input
                  name="contact_phone"
                  type="tel"
                  value={contactPhone}
                  onChange={(e) => setContactPhone(e.target.value)}
                  placeholder="+92 300 1234567"
                  maxLength={32}
                />
              </label>

              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                  required
                />
                <span>
                  I agree to {recipient} and Awaaz Estate using my contact details to coordinate this visit and
                  deliver appointment reminders.{" "}
                  <Link href="/privacy" target="_blank">
                    Privacy notice
                  </Link>
                </span>
              </label>

              {errorMessage && (
                <p className="form-message" role="alert" style={{ color: "#b75537" }}>
                  {errorMessage}
                </p>
              )}

              <button
                className="button"
                type="submit"
                disabled={pending || slots.length === 0}
                style={{ width: "100%" }}
              >
                {pending ? "Sending code…" : "Verify Email & Book"}
              </button>
            </form>
          ) : (
            <form className="form-stack" onSubmit={handleVerifyAndBook}>
              <div
                style={{
                  background: "var(--soft)",
                  padding: 12,
                  borderRadius: 8,
                  fontSize: 14,
                  color: "var(--ink)",
                }}
              >
                A 6-digit code has been sent to <strong>{contactEmail}</strong>.
                {debugOtp && (
                  <div style={{ marginTop: 6, fontSize: 13, color: "var(--green)" }}>
                    <strong>Dev Code:</strong> <code>{debugOtp}</code>
                  </div>
                )}
              </div>

              <label className="field">
                Enter 6-digit verification code
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value)}
                  placeholder="123456"
                  required
                  autoFocus
                  style={{
                    letterSpacing: "4px",
                    fontSize: 20,
                    textAlign: "center",
                    fontWeight: "bold",
                  }}
                />
              </label>

              {errorMessage && (
                <p className="form-message" role="alert" style={{ color: "#b75537" }}>
                  {errorMessage}
                </p>
              )}

              <button
                className="button"
                type="submit"
                disabled={pending || otpCode.trim().length !== 6}
                style={{ width: "100%" }}
              >
                {pending ? "Confirming reservation…" : "Confirm & Reserve Slot"}
              </button>

              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
                <button
                  type="button"
                  onClick={() => setOtpSent(false)}
                  style={{
                    background: "none",
                    border: "none",
                    color: "var(--muted)",
                    fontSize: 13,
                    cursor: "pointer",
                    textDecoration: "underline",
                  }}
                >
                  ← Edit details
                </button>
                <button
                  type="button"
                  onClick={handleRequestOtp}
                  disabled={pending}
                  style={{
                    background: "none",
                    border: "none",
                    color: "var(--green)",
                    fontSize: 13,
                    cursor: "pointer",
                    textDecoration: "underline",
                  }}
                >
                  Resend code
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
