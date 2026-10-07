import { Metadata } from "next";
import { HomeFinanceCalculator } from "@/components/HomeFinanceCalculator";
import { SiteHeader } from "@/components/SiteHeader";

export const metadata: Metadata = {
  title: "Home Finance & Mortgage Calculator | Awaaz Estate",
  description:
    "Calculate Islamic Diminishing Musharakah and conventional home financing installments, down payments, and taxes for verified Pakistani real estate.",
};

export default function CalculatorPage() {
  return (
    <>
      <SiteHeader />
      <main className="container" style={{ padding: "40px 0 80px" }}>
        <div style={{ maxWidth: 880, margin: "0 auto" }}>
          <div style={{ marginBottom: 32, textAlign: "center" }}>
            <span
              style={{
                fontSize: 12,
                textTransform: "uppercase",
                letterSpacing: 2,
                color: "#18523c",
                fontWeight: 700,
              }}
            >
              Financial Intelligence
            </span>
            <h1 style={{ marginTop: 8, marginBottom: 12, fontSize: "clamp(28px, 4vw, 42px)" }}>
              Home Finance & Mortgage Calculator
            </h1>
            <p style={{ color: "var(--muted, #566960)", fontSize: 16, maxWidth: 640, margin: "0 auto" }}>
              Evaluate Shariah-compliant Diminishing Musharakah vs. conventional mortgage structures with live FBR Advance Tax and Stamp Duty calculations.
            </p>
          </div>
          <HomeFinanceCalculator propertyPrice={50_000_000} propertyTitle="Prime Residential Asset" transactionType="sale" />
        </div>
      </main>
    </>
  );
}
