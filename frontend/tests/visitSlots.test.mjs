import assert from "node:assert/strict";
import test from "node:test";
import { defaultVisitSlot, visitSlotError, visitSlotToIso } from "../src/visitSlots.mjs";

test("visit slot validation matches the backend's Pakistan-time weekday and half-hour rules", () => {
  assert.equal(visitSlotError("2026-09-28T10:00"), null);
  assert.equal(visitSlotError("2026-09-28T17:30"), null);
  assert.match(visitSlotError("2026-09-27T11:00") ?? "", /Monday/);
  assert.match(visitSlotError("2026-09-28T18:00") ?? "", /Monday/);
  assert.match(visitSlotError("2026-09-28T10:15") ?? "", /30-minute/);
});

test("Pakistan wall-clock slots convert to the correct UTC instant for the API", () => {
  assert.equal(visitSlotToIso("2026-09-28T11:00"), "2026-09-28T06:00:00.000Z");
  assert.throws(() => visitSlotToIso("2026-09-27T11:00"), RangeError);
});

test("default visit time skips Sunday in Pakistan", () => {
  assert.equal(defaultVisitSlot(new Date("2026-09-26T20:00:00.000Z")), "2026-09-28T11:00");
});
