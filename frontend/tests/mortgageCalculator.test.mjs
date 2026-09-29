import assert from "node:assert/strict";
import test from "node:test";
import { calculateInstallment } from "../src/financingMath.mjs";

test("installment estimate calculates reducing-balance payments from user assumptions", () => {
  const result = calculateInstallment(20_000_000, 25, 5, 14.5);
  assert.equal(result.downPaymentAmount, 5_000_000);
  assert.equal(result.loanPrincipal, 15_000_000);
  assert.ok(result.monthlyInstallment > 300_000 && result.monthlyInstallment < 400_000);
  assert.ok(result.totalInterest > 5_000_000);
  assert.equal(result.totalMonths, 60);
  assert.equal(result.totalPaid, result.downPaymentAmount + result.loanPrincipal + result.totalInterest);
});

test("zero-rate estimate divides principal evenly across the selected term", () => {
  const result = calculateInstallment(12_000_000, 25, 5, 0);
  assert.equal(result.monthlyInstallment, 150_000);
  assert.equal(result.totalInterest, 0);
});

test("invalid calculator input is rejected instead of yielding misleading totals", () => {
  assert.throws(() => calculateInstallment(-1, 25, 5, 14.5), RangeError);
  assert.throws(() => calculateInstallment(1_000_000, 100, 5, 14.5), RangeError);
  assert.throws(() => calculateInstallment(1_000_000, 25, 5, Number.NaN), TypeError);
});
