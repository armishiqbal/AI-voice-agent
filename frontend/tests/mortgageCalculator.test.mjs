import assert from "node:assert/strict";
import test from "node:test";

function calculateMortgage(price, downPaymentPct, tenureYears, interestRate) {
  const downPaymentAmount = (price * downPaymentPct) / 100;
  const loanPrincipal = price - downPaymentAmount;
  const monthlyRate = interestRate / 100 / 12;
  const totalMonths = tenureYears * 12;

  let monthlyInstallment = 0;
  if (monthlyRate > 0 && totalMonths > 0) {
    monthlyInstallment =
      (loanPrincipal * monthlyRate * Math.pow(1 + monthlyRate, totalMonths)) /
      (Math.pow(1 + monthlyRate, totalMonths) - 1);
  } else if (totalMonths > 0) {
    monthlyInstallment = loanPrincipal / totalMonths;
  }

  const totalRepayment = monthlyInstallment * totalMonths;
  const totalInterest = Math.max(0, totalRepayment - loanPrincipal);

  return {
    downPaymentAmount,
    loanPrincipal,
    monthlyInstallment: Math.round(monthlyInstallment),
    totalInterest: Math.round(totalInterest),
  };
}

function calculateFbrTax(price, isFiler) {
  const rate = isFiler ? 0.03 : price > 100_000_000 ? 0.15 : 0.105;
  return Math.round(price * rate);
}

test("calculateMortgage calculates reducing balance EMI accurately", () => {
  const result = calculateMortgage(20_000_000, 25, 5, 14.5);
  assert.equal(result.downPaymentAmount, 5_000_000);
  assert.equal(result.loanPrincipal, 15_000_000);
  assert.ok(result.monthlyInstallment > 300_000 && result.monthlyInstallment < 400_000);
  assert.ok(result.totalInterest > 5_000_000);
});

test("calculateFbrTax calculates 3% filer and 10.5% non-filer withholding tax", () => {
  assert.equal(calculateFbrTax(30_000_000, true), 900_000);
  assert.equal(calculateFbrTax(30_000_000, false), 3_150_000);
});
