import { metadata } from "@/lib/site";
export const generateMetadata = () => ({ ...metadata("Ask Awaaz", "Use the optional Awaaz Estate conversational assistant to explore your property requirements.", "/assistant"), robots: { index: false, follow: true } });
export default function Assistant() {
  const configured = process.env.ASSISTANT_URL || process.env.NEXT_PUBLIC_ASSISTANT_URL || "/assistant/";
  let url: string | null = null;
  try { if (configured) { if (configured.startsWith("/") && !configured.startsWith("//")) url = configured; else { const parsed = new URL(configured); if (["https:", "http:"].includes(parsed.protocol)) url = parsed.toString(); } } } catch { /* Invalid deployment configuration is displayed as unavailable. */ }
  return <section className="section container assistant-intro"><p className="eyebrow">A conversation about your next place</p><h1>Ask Awaaz</h1><p>Talk through your location, budget and property requirements in the existing multilingual assistant. You can also type your questions there.</p>{url ? <a className="button" href={url}>Open the assistant</a> : <p className="available-note">The assistant connection has not yet been configured. You can browse listings and send an inquiry.</p>}<p className="quiet">Microphone access starts only when you choose to begin a voice conversation. Inquiries and appointments require their own confirmation.</p></section>;
}
