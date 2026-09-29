export function calculateInstallment(price, downPaymentPct, tenureYears, annualRatePct) {
  if (![price, downPaymentPct, tenureYears, annualRatePct].every(Number.isFinite)) {
    throw new TypeError("Financing inputs must be finite numbers");
  }
  if (price < 0 || price > 5_000_000_000) throw new RangeError("Property price is outside the supported range");
  if (downPaymentPct < 0 || downPaymentPct >= 100) throw new RangeError("Down payment must be from 0% to less than 100%");
  if (tenureYears <= 0 || tenureYears > 40) throw new RangeError("Tenure must be between 1 and 40 years");
  if (annualRatePct < 0 || annualRatePct > 100) throw new RangeError("Annual rate must be between 0% and 100%");

  const downPaymentAmount = (price * downPaymentPct) / 100;
  const loanPrincipal = price - downPaymentAmount;
  const totalMonths = tenureYears * 12;
  const monthlyRate = annualRatePct / 100 / 12;
  const monthlyInstallment = price === 0
    ? 0
    : monthlyRate > 0
      ? (loanPrincipal * monthlyRate * Math.pow(1 + monthlyRate, totalMonths))
        / (Math.pow(1 + monthlyRate, totalMonths) - 1)
      : loanPrincipal / totalMonths;
  const totalRepayment = monthlyInstallment * totalMonths;

  return {
    downPaymentAmount,
    loanPrincipal,
    monthlyInstallment,
    totalInterest: Math.max(0, totalRepayment - loanPrincipal),
    totalMonths,
    totalPaid: downPaymentAmount + totalRepayment,
  };
}
