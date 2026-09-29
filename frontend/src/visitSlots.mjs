const PAKISTAN_OFFSET_MS = 5 * 60 * 60 * 1000;

export function defaultVisitSlot(now = new Date()) {
  const pakistanNow = new Date(now.getTime() + PAKISTAN_OFFSET_MS);
  const nextDay = new Date(Date.UTC(
    pakistanNow.getUTCFullYear(),
    pakistanNow.getUTCMonth(),
    pakistanNow.getUTCDate() + 1,
  ));
  while (nextDay.getUTCDay() === 0) nextDay.setUTCDate(nextDay.getUTCDate() + 1);
  return `${nextDay.toISOString().slice(0, 10)}T11:00`;
}

export function visitSlotError(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) {
    return "Choose a visit date and time.";
  }
  const [date, time] = value.split("T");
  const day = new Date(`${date}T12:00:00Z`).getUTCDay();
  const [hours, minutes] = time.split(":").map(Number);
  if (day === 0 || hours < 10 || hours >= 18 || ![0, 30].includes(minutes)) {
    return "Visits are available Monday–Saturday, 10:00–17:30 Pakistan time, in 30-minute slots.";
  }
  return null;
}

export function visitSlotToIso(value) {
  const error = visitSlotError(value);
  if (error) throw new RangeError(error);
  return new Date(`${value}:00+05:00`).toISOString();
}
