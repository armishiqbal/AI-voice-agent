import { NextRequest, NextResponse } from "next/server";
import { apiJson, CatalogError } from "@/lib/catalog";

export async function POST(request: NextRequest) {
  const origin = request.headers.get("origin");
  const configured = process.env.SITE_URL || process.env.NEXT_PUBLIC_SITE_URL;
  const expectedOrigin = configured ? new URL(configured).origin : request.nextUrl.origin;
  if (!origin || origin !== expectedOrigin) return NextResponse.json({ error: "Request origin rejected." }, { status: 403 });
  if (!request.headers.get("content-type")?.includes("application/json")) return NextResponse.json({ error: "JSON is required." }, { status: 415 });
  const text = await request.text();
  if (new TextEncoder().encode(text).length > 8192) return NextResponse.json({ error: "Request is too large." }, { status: 413 });
  let payload: unknown;
  try { payload = JSON.parse(text); } catch { return NextResponse.json({ error: "Invalid JSON." }, { status: 422 }); }
  if (typeof payload !== "object" || payload === null) return NextResponse.json({ error: "Invalid inquiry." }, { status: 422 });
  const data = payload as Record<string, unknown>;
  const emailValid = typeof data.contact_email === "string" && data.contact_email.length <= 254 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.contact_email);
  const phoneValid = typeof data.contact_phone === "string" && /^\+?[0-9 ()-]{7,32}$/.test(data.contact_phone);
  if (typeof data.client_name !== "string" || data.client_name.trim().length < 2 || data.client_name.length > 100 || (!emailValid && !phoneValid) || (data.contact_email !== undefined && !emailValid) || (data.contact_phone !== undefined && !phoneValid) || !["email", "phone", "whatsapp"].includes(String(data.contact_preference)) || (data.contact_preference === "email" && !emailValid) || (data.contact_preference !== "email" && !phoneValid) || !["property", "callback", "seller", "general"].includes(String(data.request_type)) || typeof data.message !== "string" || !data.message.trim() || data.message.length > 1000 || data.consent !== true || data.consent_version !== "2026-10-03" || typeof data.idempotency_key !== "string" || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(data.idempotency_key) || (data.property_id !== undefined && (typeof data.property_id !== "string" || data.property_id.length > 128))) return NextResponse.json({ error: "Check inquiry fields and consent." }, { status: 422 });
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    // The private website service is reached only through a gateway that overwrites these headers.
    const forwardedFor = request.headers.get("x-forwarded-for");
    const requestId = request.headers.get("x-request-id");
    if (forwardedFor) headers["X-Forwarded-For"] = forwardedFor;
    if (requestId) headers["X-Request-ID"] = requestId;
    await apiJson("/v1/public/inquiries", { method: "POST", headers, body: JSON.stringify({ property_id: data.property_id, request_type: data.request_type, client_name: data.client_name, contact_email: data.contact_email, contact_phone: data.contact_phone, contact_preference: data.contact_preference, message: data.message, consent: data.consent, consent_version: data.consent_version, idempotency_key: data.idempotency_key }) });
    return NextResponse.json({ recorded: true }, { status: 201 });
  } catch (error) {
    const status = error instanceof CatalogError && [422, 429, 409].includes(error.status) ? error.status : 503;
    return NextResponse.json({ error: "Inquiry service could not record this request." }, { status });
  }
}
