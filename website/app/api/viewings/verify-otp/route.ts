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
  const emailValid = typeof data.email === "string" && data.email.length <= 254 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email);
  const otpValid = typeof data.otp === "string" && /^[0-9]{6}$/.test(data.otp.trim());
  if (!emailValid || !otpValid) return NextResponse.json({ error: "A valid email address and 6-digit code are required." }, { status: 422 });

  try {
    const res = await apiJson("/v1/public/viewings/verify-otp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: data.email, otp: (data.otp as string).trim() }),
    });
    return NextResponse.json(res, { status: 200 });
  } catch (error) {
    const status = error instanceof CatalogError && [400, 422, 429].includes(error.status) ? error.status : 503;
    return NextResponse.json({ error: "Verification code is incorrect or expired." }, { status });
  }
}
