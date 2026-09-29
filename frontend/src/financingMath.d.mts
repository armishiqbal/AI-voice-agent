export type InstallmentEstimate = {
  downPaymentAmount: number;
  loanPrincipal: number;
  monthlyInstallment: number;
  totalInterest: number;
  totalMonths: number;
  totalPaid: number;
};
export declare function calculateInstallment(
  price: number,
  downPaymentPct: number,
  tenureYears: number,
  annualRatePct: number,
): InstallmentEstimate;
