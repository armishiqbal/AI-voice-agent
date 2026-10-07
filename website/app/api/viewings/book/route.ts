import { NextRequest, NextResponse } from "next/server";
import { apiJson, CatalogError } from "@/lib/catalog";

export async function POST(request: NextRequest) {
  const origin = request.headers.get("origin");
  const configured = process.env.SITE_URL || process.env.NEXT_PUBLIC_SITE_URL;
  const expectedOrigin = configured ? new URL(configured).origin : request.nextUrl.origin;
  if (!origin || origin !== expectedOrigin) return NextResponse.json({ error: "Request origin rejected." }, { status: 403 });
  if (!request.headers.get("content-type")?.includes("application/json")) return NextResponse.json({ error: "JSON is required." }, { status: 415 });

  let payload: unknown;
  try { payload = await request.json(); } catch { return NextResponse.json({ error: "Invalid JSON." }, { status: 422 }); }
  if (typeof payload !== "object" || payload === null) return NextResponse.json({ error: "Invalid request." }, { status: 422 });
  const data = payload as Record<string, unknown>;

  const emailValid = typeof data.contact_email === "string" && data.contact_email.length <= 254 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.contact_email);
  const nameValid = typeof data.client_name === "string" && data.client_name.trim().length >= 2 && data.client_name.length <= 100;
  const phoneValid = data.contact_phone === undefined || data.contact_phone === "" || (typeof data.contact_phone === "string" && /^\+?[0-9 ()-]{7,32}$/.test(data.contact_phone));
  const tokenValid = typeof data.verification_token === "string" && data.verification_token.length >= 10;
  const propValid = typeof data.property_id === "string" && data.property_id.length > 0;
  const slotValid = typeof data.starts_at === "string" && Number.isFinite(new Date(data.starts_at).getTime());
  const idempValid = typeof data.idempotency_key === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(data.idempotency_key);

  if (!emailValid || !nameValid || !phoneValid || !tokenValid || !propValid || !slotValid || !idempValid || data.consent !== true || data.consent_version !== "2026-10-03") {
    return NextResponse.json({ error: "Check viewing booking fields and consent." }, { status: 422 });
  }

  try {
    const res = await apiJson("/v1/public/viewings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        property_id: data.property_id,
        starts_at: data.starts_at,
        client_name: data.client_name,
        contact_email: data.contact_email,
        contact_phone: data.contact_phone || null,
        verification_token: data.verification_token,
        consent: data.consent,
        consent_version: data.consent_version,
        idempotency_key: data.idempotency_key,
      }),
    });
    return NextResponse.json(res, { status: 201 });
  } catch (error) {
    const status = error instanceof CatalogError && [400, 403, 404, 409, 422, 429].includes(error.status) ? error.status : 503;
    const msg = error instanceof CatalogError && error.status === 409 ? "This slot is already booked. Please choose another time." : "Viewing reservation could not be completed.";
    return NextResponse.json({ error: msg }, { status });
  }
}
