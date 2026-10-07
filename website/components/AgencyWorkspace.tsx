"use client";

import { useEffect, useState, type FormEvent } from "react";
import { sessionRequest } from "@/lib/session";
import { isObject } from "@/lib/marketplace";
import styles from "./Portal.module.css";

type Tab = "listings" | "inquiries" | "viewings" | "schedules" | "members";
const tabs: Tab[] = ["listings", "inquiries", "viewings", "schedules", "members"];
const cities = ["Islamabad", "Rawalpindi", "Lahore", "Karachi"];

function pkTime(value: unknown): string {
  const date = new Date(String(value));
  return Number.isFinite(date.getTime())
    ? date.toLocaleString("en-PK", { timeZone: "Asia/Karachi" })
    : "Time unavailable";
}

export function AgencyWorkspace({ organizationId }: { organizationId: string }) {
  const [tab, setTab] = useState<Tab>("listings");
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const base = `agency/${encodeURIComponent(organizationId)}`;

  async function refresh() {
    try {
      const result = await sessionRequest(`${base}/${tab}`);
      if (isObject(result) && Array.isArray(result.data)) {
        setRows(result.data.filter(isObject));
        setStatus("");
      } else {
        setRows([]);
        setStatus("The workspace returned an unexpected response.");
      }
    } catch (error) {
      setRows([]);
      setStatus(error instanceof Error ? error.message : "Unable to load workspace");
    }
  }

  useEffect(() => {
    setRows([]);
    void refresh();
  }, [tab, organizationId]);

  async function act(path: string, body: unknown, method = "POST") {
    setBusy(true);
    try {
      await sessionRequest(`${base}/${path}`, {
        method,
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      setStatus("Change recorded. External delivery, if required, is tracked separately.");
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  function createListing(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) || "");
    void act("listings", {
      title: text("title"),
      description: text("description"),
      city: text("city"),
      area: text("area"),
      transaction_type: text("transaction_type"),
      property_type: text("property_type"),
      classification: text("classification"),
      rental_period: text("transaction_type") === "rent" ? text("rental_period") : null,
      assigned_subject: text("assigned_subject"),
      price_pkr: Number(form.get("price_pkr")),
      size_sqft: Number(form.get("size_sqft")),
      bedrooms: Number(form.get("bedrooms")),
      bathrooms: Number(form.get("bathrooms")),
      amenities: [],
      developer: text("developer"),
      payment_plan: text("payment_plan"),
    });
  }

  return (
    <div className={styles.portal}>
      <h1>Agency workspace</h1>
      <p>Agency submissions are reviewed by Awaaz before publication. Accepted viewings keep their recorded agent and agency.</p>
      <div className={styles.links} role="tablist" aria-label="Agency tools">
        {tabs.map((name) => (
          <button key={name} role="tab" aria-selected={tab === name} onClick={() => setTab(name)}>{name}</button>
        ))}
      </div>
      <p role="status" aria-live="polite">{status}</p>

      {tab === "listings" && (
        <details>
          <summary>Create a listing draft</summary>
          <form className={styles.search} onSubmit={createListing}>
            {(["title", "description", "area", "assigned_subject", "developer", "payment_plan"] as const).map((name) => (
              <label key={name}>{name.replaceAll("_", " ")}
                {name === "description" ? <textarea name={name} required maxLength={5000} /> : <input name={name} required maxLength={128} />}
              </label>
            ))}
            <label>City<select name="city">{cities.map((city) => <option key={city}>{city}</option>)}</select></label>
            <label>Transaction<select name="transaction_type"><option value="sale">Sale</option><option value="rent">Rent</option></select></label>
            <label>Rental period<select name="rental_period"><option value="monthly">Monthly</option><option value="yearly">Yearly</option></select></label>
            <label>Property type<select name="property_type">{["house", "apartment", "plot", "shop", "office", "warehouse", "other"].map((value) => <option key={value}>{value}</option>)}</select></label>
            <label>Classification<select name="classification"><option>residential</option><option>commercial</option></select></label>
            {(["price_pkr", "size_sqft", "bedrooms", "bathrooms"] as const).map((name) => (
              <label key={name}>{name.replaceAll("_", " ")}<input name={name} required type="number" min={name === "bedrooms" || name === "bathrooms" ? 0 : 1} /></label>
            ))}
            <button disabled={busy}>Create draft</button>
          </form>
        </details>
      )}

      {tab === "schedules" && (
        <form className={styles.search} onSubmit={(event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          void act("schedules", {
            subject: form.get("subject"),
            weekday: Number(form.get("weekday")),
            start_minute: Number(form.get("start_minute")),
            end_minute: Number(form.get("end_minute")),
            exception_date: form.get("exception_date") || null,
            unavailable: form.get("unavailable") === "on",
          });
        }}>
          <label>Agent identity<input name="subject" required /></label>
          <label>Weekday<select name="weekday">{["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map((day, index) => <option key={day} value={index}>{day}</option>)}</select></label>
          <label>Start minute after midnight<input name="start_minute" type="number" step="30" min="0" max="1410" defaultValue="600" required /></label>
          <label>End minute<input name="end_minute" type="number" step="30" min="30" max="1440" defaultValue="1080" required /></label>
          <label>Exception date<input name="exception_date" type="date" /></label>
          <label><input name="unavailable" type="checkbox" />Unavailable on exception date</label>
          <button disabled={busy}>Save availability in Pakistan time</button>
        </form>
      )}

      <div className={styles.grid}>
        {rows.map((row, index) => {
          const recordId = String(row.id || row.reference || index);
          return (
            <section className={styles.panel} key={recordId}>
              <h2>{String(row.title || row.client_name || row.name || row.reference || row.subject || "Record")}</h2>
              <p>{String(row.publication_status || row.workflow_status || row.status || row.role || "")}</p>

              {tab === "listings" && <>
                <p>Version {String(row.edit_version)} · Availability {String(row.availability_status)}</p>
                <form onSubmit={(event) => {
                  event.preventDefault();
                  const form = new FormData(event.currentTarget);
                  const lat = String(form.get("latitude") || ""), lon = String(form.get("longitude") || "");
                  void act(`listings/${row.id}/submit`, {
                    edit_version: row.edit_version,
                    title: form.get("title"),
                    description: form.get("description"),
                    ...(lat && lon ? { latitude: Number(lat), longitude: Number(lon) } : {}),
                  });
                }}>
                  <label>Proposed title<input name="title" defaultValue={String(row.title)} required /></label>
                  <label>Proposed description<textarea name="description" defaultValue={String(row.description)} required maxLength={5000} /></label>
                  <label>Latitude proposal<input name="latitude" type="number" step="any" min="-90" max="90" /></label>
                  <label>Longitude proposal<input name="longitude" type="number" step="any" min="-180" max="180" /></label>
                  <button disabled={busy}>Submit for platform review</button>
                </form>
                <button disabled={busy} onClick={() => void act(`listings/${row.id}/availability`, { edit_version: row.edit_version, status: "available", content_permission: true }, "PATCH")}>Confirm availability and photo permission</button>
                <button disabled={busy} onClick={() => void act(`listings/${row.id}/availability`, { edit_version: row.edit_version, status: "unavailable" }, "PATCH")}>Mark unavailable now</button>
                <form onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); void act(`listings/${row.id}/assignment`, { subject: form.get("subject"), edit_version: row.edit_version }, "PATCH"); }}>
                  <label>Assigned agent identity<input name="subject" required defaultValue={String(row.assigned_staff_id || "")} /></label>
                  <button disabled={busy}>Change assignment</button>
                </form>
                <button disabled={busy} onClick={() => void act(`listings/${row.id}/archive`, { edit_version: row.edit_version })}>Archive listing</button>
                <p>Upload a permitted real photo (8 MB maximum); platform staff must approve it before publication.</p>
                <input type="file" accept="image/jpeg,image/png,image/webp" aria-label="Upload listing photo" onChange={async (event) => {
                  const file = event.target.files?.[0];
                  if (!file) return;
                  try {
                    const token = await sessionRequest("auth/csrf");
                    if (!isObject(token)) throw new Error("Session protection is unavailable");
                    const response = await fetch(`/api/media/${encodeURIComponent(organizationId)}/${encodeURIComponent(String(row.id))}`, {
                      method: "POST",
                      headers: { "x-csrf-token": String(token.csrf_token), "content-type": file.type },
                      body: file,
                    });
                    if (!response.ok) throw new Error("Photo upload could not be queued");
                    setStatus("Photo queued for processing and platform review.");
                  } catch (error) {
                    setStatus(error instanceof Error ? error.message : "Photo upload failed");
                  }
                }} />
              </>}

              {tab === "inquiries" && <>
                <p>Preferred contact: {String(row.contact_preference || "not provided")} · {String(row.contact_email || row.contact_phone || "contact detail unavailable")}</p>
                <form onSubmit={(event) => {
                  event.preventDefault();
                  const form = new FormData(event.currentTarget);
                  const followUp = String(form.get("follow_up") || "");
                  void act(`inquiries/${row.inquiry_id}`, {
                    edit_version: row.edit_version,
                    workflow_status: form.get("workflow_status"),
                    closing_outcome: form.get("outcome") || undefined,
                    note: form.get("note") || undefined,
                    assigned_staff_id: form.get("assignee") || undefined,
                    follow_up_at: followUp ? new Date(followUp).toISOString() : undefined,
                  }, "PATCH");
                }}>
                  <label>Status<select name="workflow_status" defaultValue={String(row.workflow_status)}>{["new", "contacted", "qualified", "viewing_scheduled", "closed"].map((value) => <option key={value}>{value}</option>)}</select></label>
                  <label>Closing outcome<input name="outcome" maxLength={64} /></label>
                  <label>Assign to active member identity<input name="assignee" /></label>
                  <label>Follow-up time on this device<input name="follow_up" type="datetime-local" /></label>
                  <label>Internal note<textarea name="note" maxLength={1000} /></label>
                  <button disabled={busy}>Record follow-up</button>
                </form>
              </>}

              {tab === "schedules" && <>
                <p>{String(row.subject)} · weekday {String(row.weekday)} · {String(row.start_minute)}–{String(row.end_minute)} PKT minutes</p>
                {row.exception_date && <p>{String(row.exception_date)} · {row.unavailable ? "Unavailable" : "Availability exception"}</p>}
                <button disabled={busy} onClick={() => void act(`schedules/${row.id}`, undefined, "DELETE")}>Remove schedule</button>
              </>}

              {tab === "viewings" && <>
                <p>Assigned agent: {String(row.agent_subject || "Unassigned")}</p>
                <p>{pkTime(row.starts_at)} · Status: {String(row.status)} · External delivery is tracked separately.</p>
                {row.status !== "cancelled" && row.status !== "completed" && <>
                  <form onSubmit={(event) => {
                    event.preventDefault();
                    const value = String(new FormData(event.currentTarget).get("new_starts_at") || "");
                    if (!value) return;
                    const startsAt = new Date(`${value}+05:00`);
                    if (!Number.isFinite(startsAt.getTime())) return;
                    void act(`viewings/${row.reference}/reschedule`, {
                      new_starts_at: startsAt.toISOString(),
                      idempotency_key: crypto.randomUUID(),
                    });
                  }}>
                    <label>New time (Pakistan time)<input name="new_starts_at" type="datetime-local" required /></label>
                    <button disabled={busy}>Reschedule viewing</button>
                  </form>
                  <button disabled={busy} onClick={() => void act(`viewings/${row.reference}/cancel`, { reason: "Cancelled by agency", idempotency_key: crypto.randomUUID() })}>Cancel viewing</button>
                  {new Date(String(row.starts_at)).getTime() < Date.now() && <button disabled={busy} onClick={() => void act(`viewings/${row.reference}/complete`, undefined)}>Mark viewing completed</button>}
                </>}
              </>}

              {tab === "members" && <>
                <p>Provider identity: {String(row.subject)}</p>
                <form onSubmit={(event) => {
                  event.preventDefault();
                  const form = new FormData(event.currentTarget);
                  void act(`members/${row.id}`, { active: form.get("active") === "on", role: form.get("role") }, "PATCH");
                }}>
                  <label>Role<select name="role" defaultValue={String(row.role)}>{["administrator", "manager", "agent"].map((value) => <option key={value}>{value}</option>)}</select></label>
                  <label><input name="active" type="checkbox" defaultChecked={row.active === true} />Active member</label>
                  <button disabled={busy}>Update member</button>
                </form>
              </>}
            </section>
          );
        })}
      </div>
      {!rows.length && !status && <p>No {tab} found for this agency.</p>}
    </div>
  );
}
