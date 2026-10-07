"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";

type Tab = "listings" | "inquiries" | "viewings" | "areas";

type StaffListingItem = {
  id: string;
  slug: string | null;
  title: string;
  city: string;
  area: string;
  price_pkr: number;
  transaction_type: string;
  property_type: string;
  bedrooms: number;
  publication_status: string;
  availability_status: string;
  availability_confirmed_at: string | null;
  assigned_staff_id: string | null;
  edit_version: number;
};

type StaffInquiryItem = {
  inquiry_id: string;
  property_id: string | null;
  request_type: string;
  client_name: string;
  contact_email: string | null;
  contact_phone: string | null;
  contact_preference: string;
  message: string;
  workflow_status: string;
  delivery_status: string;
  assigned_staff_id: string | null;
  edit_version: number;
  created_at: string;
};

type StaffViewingItem = {
  id: string;
  reference: string;
  property_id: string;
  property_title: string | null;
  employee: string;
  starts_at: string;
  client_name: string;
  contact_email: string;
  contact_phone: string | null;
  status: string;
  delivery_status: string;
};

type StaffAreaGuideItem = {
  id: string;
  city_slug: string;
  area_slug: string;
  title: string;
  overview_markdown: string;
  publication_status: string;
  reviewed_at: string | null;
};

const DEV_PERSONAS = [
  { id: "dev-staff-manager-ali", label: "Ali (Manager)", role: "manager" },
  { id: "dev-staff-agent-fatima", label: "Fatima (Agent)", role: "agent" },
  { id: "dev-staff-admin-ayesha", label: "Ayesha (Admin)", role: "administrator" },
];

export default function DevelopmentStaffPanel() {
  const [token, setToken] = useState<string>("dev-staff-manager-ali");
  const [customToken, setCustomToken] = useState<string>("");
  const [activeTab, setActiveTab] = useState<Tab>("listings");

  const [listings, setListings] = useState<StaffListingItem[]>([]);
  const [inquiries, setInquiries] = useState<StaffInquiryItem[]>([]);
  const [viewings, setViewings] = useState<StaffViewingItem[]>([]);
  const [areas, setAreas] = useState<StaffAreaGuideItem[]>([]);

  const [loading, setLoading] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string>("");
  const [error, setError] = useState<string>("");

  // Area guide form modal state
  const [showAreaModal, setShowAreaModal] = useState<boolean>(false);
  const [areaForm, setAreaForm] = useState({
    city_slug: "",
    area_slug: "",
    title: "",
    overview_markdown: "",
    amenities_summary: "",
    transport_info: "",
    investment_outlook: "",
  });

  const activeHeaders = useCallback((): HeadersInit => {
    return {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    };
  }, [token]);

  const loadData = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError("");
    try {
      if (activeTab === "listings") {
        const res = await fetch("/api/staff/listings", { headers: activeHeaders() });
        if (res.ok) {
          const data = await res.json();
          setListings(data.data || []);
        } else {
          setError(`Could not load listings (${res.status}). Verify staff authorization.`);
        }
      } else if (activeTab === "inquiries") {
        const res = await fetch("/api/staff/inquiries", { headers: activeHeaders() });
        if (res.ok) {
          const data = await res.json();
          setInquiries(data.data || []);
        } else {
          setError(`Could not load inquiries (${res.status}). Verify staff authorization.`);
        }
      } else if (activeTab === "viewings") {
        const res = await fetch("/api/staff/viewings", { headers: activeHeaders() });
        if (res.ok) {
          const data = await res.json();
          setViewings(data.data || []);
        } else {
          setError(`Could not load viewings (${res.status}). Verify staff authorization.`);
        }
      } else if (activeTab === "areas") {
        const res = await fetch("/api/staff/areas", { headers: activeHeaders() });
        if (res.ok) {
          const data = await res.json();
          setAreas(Array.isArray(data) ? data : []);
        } else {
          setError(`Could not load area guides (${res.status}). Verify staff authorization.`);
        }
      }
    } catch {
      setError("Network error communicating with the staff API.");
    } finally {
      setLoading(false);
    }
  }, [token, activeTab, activeHeaders]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Actions
  async function handleConfirmAvailability(item: StaffListingItem) {
    setLoading(true);
    setFeedback("");
    try {
      const res = await fetch(`/api/staff/listings/${item.id}/confirm-availability`, {
        method: "POST",
        headers: activeHeaders(),
        body: JSON.stringify({ edit_version: item.edit_version, availability_status: "available" }),
      });
      if (res.ok) {
        setFeedback(`Confirmed availability for ${item.title}`);
        loadData();
      } else {
        const data = await res.json();
        setError(data.detail || "Could not confirm availability.");
      }
    } catch {
      setError("Failed to update availability.");
    } finally {
      setLoading(false);
    }
  }

  async function handleUpdateInquiryStatus(item: StaffInquiryItem, newStatus: string) {
    setLoading(true);
    setFeedback("");
    try {
      const res = await fetch(`/api/staff/inquiries/${item.inquiry_id}`, {
        method: "PATCH",
        headers: activeHeaders(),
        body: JSON.stringify({
          edit_version: item.edit_version,
          workflow_status: newStatus,
          note: `Status changed to ${newStatus} via staff portal`,
        }),
      });
      if (res.ok) {
        setFeedback(`Inquiry status updated to ${newStatus}`);
        loadData();
      } else {
        const data = await res.json();
        setError(data.detail || "Could not update inquiry status.");
      }
    } catch {
      setError("Failed to update inquiry.");
    } finally {
      setLoading(false);
    }
  }

  async function handleCancelViewing(ref: string) {
    const reason = prompt("Enter cancellation reason for the client:", "Schedule conflict");
    if (reason === null) return;
    setLoading(true);
    setFeedback("");
    try {
      const res = await fetch(`/api/staff/viewings/${encodeURIComponent(ref)}/cancel`, {
        method: "POST",
        headers: activeHeaders(),
        body: JSON.stringify({ idempotency_key: crypto.randomUUID(), reason }),
      });
      if (res.ok) {
        setFeedback(`Viewing ${ref} cancelled.`);
        loadData();
      } else {
        const data = await res.json();
        setError(data.detail || "Could not cancel viewing.");
      }
    } catch {
      setError("Failed to cancel viewing.");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateAreaGuide(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setFeedback("");
    setError("");
    try {
      const res = await fetch("/api/staff/areas", {
        method: "POST",
        headers: activeHeaders(),
        body: JSON.stringify(areaForm),
      });
      if (res.ok) {
        setFeedback(`Published neighborhood guide for ${areaForm.title}`);
        setShowAreaModal(false);
        setAreaForm({
          city_slug: "",
          area_slug: "",
          title: "",
          overview_markdown: "",
          amenities_summary: "",
          transport_info: "",
          investment_outlook: "",
        });
        loadData();
      } else {
        const data = await res.json();
        setError(data.detail || "Could not publish area guide.");
      }
    } catch {
      setError("Failed to publish area guide.");
    } finally {
      setLoading(false);
    }
  }

  function formatPktDate(iso: string | null | undefined): string {
    if (!iso) return "—";
    const d = new Date(iso);
    return Number.isFinite(d.getTime())
      ? new Intl.DateTimeFormat("en-PK", { dateStyle: "short", timeStyle: "short", timeZone: "Asia/Karachi" }).format(d)
      : "—";
  }

  return (
    <section className="section container">
      {/* Top Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 16, marginBottom: 24 }}>
        <div>
          <p className="eyebrow" style={{ margin: "0 0 6px" }}>Staff Portal</p>
          <h1 style={{ fontSize: 32, margin: 0 }}>Business Operations Workspace</h1>
        </div>

        {/* Auth Switcher */}
        <div style={{ background: "var(--white)", border: "1px solid var(--line)", padding: "12px 16px", borderRadius: "var(--radius)", fontSize: 14 }}>
          <div style={{ fontWeight: 600, marginBottom: 8, color: "var(--ink)" }}>Session Persona (Dual Mode):</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            {DEV_PERSONAS.map((p) => (
              <button
                key={p.id}
                type="button"
                className={`button small ${token === p.id ? "" : "secondary"}`}
                style={{ padding: "6px 12px", minHeight: 34, fontSize: 13 }}
                onClick={() => setToken(p.id)}
              >
                {p.label}
              </button>
            ))}
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <input
                type="text"
                placeholder="Or Supabase JWT / custom token"
                value={customToken}
                onChange={(e) => setCustomToken(e.target.value)}
                style={{ minHeight: 34, padding: "4px 8px", fontSize: 13, width: 200 }}
              />
              <button
                type="button"
                className="button small secondary"
                style={{ padding: "6px 12px", minHeight: 34, fontSize: 13 }}
                onClick={() => {
                  if (customToken.trim()) setToken(customToken.trim());
                }}
              >
                Apply
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 12, borderBottom: "1px solid var(--line)", marginBottom: 24, overflowX: "auto" }}>
        {(["listings", "inquiries", "viewings", "areas"] as Tab[]).map((t) => {
          const isActive = activeTab === t;
          const labels: Record<Tab, string> = {
            listings: "Property Inventory",
            inquiries: "Inquiries Inbox",
            viewings: "Viewing Visits",
            areas: "Area Guides",
          };
          return (
            <button
              key={t}
              type="button"
              onClick={() => setActiveTab(t)}
              style={{
                background: "none",
                border: "none",
                borderBottom: isActive ? "3px solid var(--green)" : "3px solid transparent",
                padding: "12px 18px",
                fontSize: 16,
                fontWeight: isActive ? 700 : 500,
                color: isActive ? "var(--green)" : "var(--muted)",
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              {labels[t]}
            </button>
          );
        })}
      </div>

      {/* Alerts */}
      {feedback && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 16px", borderRadius: 8, background: "var(--soft)", color: "var(--green-dark)", marginBottom: 16, fontWeight: 600 }}>
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <span>{feedback}</span>
        </div>
      )}
      {error && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 16px", borderRadius: 8, background: "#fdf2f2", color: "#b75537", marginBottom: 16, fontWeight: 600 }}>
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <span>{error}</span>
        </div>
      )}

      {/* Tab Contents */}
      {loading ? (
        <p className="quiet">Loading workspace records…</p>
      ) : activeTab === "listings" ? (
        <div className="comparison-wrap">
          <table style={{ minWidth: 800 }}>
            <thead>
              <tr>
                <th>Property</th>
                <th>Location</th>
                <th>Price</th>
                <th>Publication</th>
                <th>Availability</th>
                <th>Confirmed Age</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {listings.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: "center", color: "var(--muted)" }}>
                    No listings found.
                  </td>
                </tr>
              ) : (
                listings.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <strong>{item.title}</strong>
                      <div className="quiet" style={{ fontSize: 13 }}>
                        {item.property_type} · {item.bedrooms} bed
                      </div>
                    </td>
                    <td>{item.area}, {item.city}</td>
                    <td>PKR {item.price_pkr.toLocaleString("en-PK")}</td>
                    <td>
                      <span className="badge" style={{ textTransform: "capitalize" }}>
                        {item.publication_status}
                      </span>
                    </td>
                    <td>
                      <span
                        className="badge"
                        style={{
                          background: item.availability_status === "available" ? "var(--soft)" : "#fee2e2",
                          color: item.availability_status === "available" ? "var(--green)" : "#991b1b",
                        }}
                      >
                        {item.availability_status}
                      </span>
                    </td>
                    <td style={{ fontSize: 13 }}>{formatPktDate(item.availability_confirmed_at)}</td>
                    <td>
                      <button
                        type="button"
                        className="button small secondary"
                        style={{ fontSize: 12, padding: "4px 8px", minHeight: 30 }}
                        onClick={() => handleConfirmAvailability(item)}
                      >
                        Confirm Availability
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : activeTab === "inquiries" ? (
        <div className="comparison-wrap">
          <table style={{ minWidth: 900 }}>
            <thead>
              <tr>
                <th>Client Name</th>
                <th>Contact Details</th>
                <th>Message</th>
                <th>Status</th>
                <th>Received</th>
                <th>Workflow Action</th>
              </tr>
            </thead>
            <tbody>
              {inquiries.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", color: "var(--muted)" }}>
                    No inquiries in the inbox.
                  </td>
                </tr>
              ) : (
                inquiries.map((item) => (
                  <tr key={item.inquiry_id}>
                    <td>
                      <strong>{item.client_name}</strong>
                      <div className="quiet" style={{ fontSize: 12 }}>Pref: {item.contact_preference}</div>
                    </td>
                    <td>
                      <div>{item.contact_email || "—"}</div>
                      <div className="quiet" style={{ fontSize: 13 }}>{item.contact_phone || ""}</div>
                    </td>
                    <td style={{ maxWidth: 280, fontSize: 14 }}>{item.message || "—"}</td>
                    <td>
                      <span className="badge" style={{ textTransform: "capitalize" }}>
                        {item.workflow_status.replace("_", " ")}
                      </span>
                    </td>
                    <td style={{ fontSize: 13 }}>{formatPktDate(item.created_at)}</td>
                    <td>
                      <select
                        value={item.workflow_status}
                        onChange={(e) => handleUpdateInquiryStatus(item, e.target.value)}
                        style={{ padding: "4px 8px", minHeight: 32, fontSize: 13 }}
                      >
                        <option value="new">New</option>
                        <option value="contacted">Contacted</option>
                        <option value="qualified">Qualified</option>
                        <option value="viewing_scheduled">Viewing Scheduled</option>
                        <option value="closed">Closed</option>
                      </select>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : activeTab === "viewings" ? (
        <div className="comparison-wrap">
          <table style={{ minWidth: 900 }}>
            <thead>
              <tr>
                <th>Reference</th>
                <th>Visit Time (PKT)</th>
                <th>Client</th>
                <th>Assigned Agent</th>
                <th>Status</th>
                <th>Delivery</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {viewings.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: "center", color: "var(--muted)" }}>
                    No scheduled viewings found.
                  </td>
                </tr>
              ) : (
                viewings.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <code style={{ color: "var(--green)", fontWeight: 700 }}>{item.reference}</code>
                      {item.property_title && (
                        <div className="quiet" style={{ fontSize: 12 }}>{item.property_title}</div>
                      )}
                    </td>
                    <td>
                      <strong>{formatPktDate(item.starts_at)}</strong>
                    </td>
                    <td>
                      <div>{item.client_name}</div>
                      <div className="quiet" style={{ fontSize: 12 }}>{item.contact_email}</div>
                    </td>
                    <td>{item.employee}</td>
                    <td>
                      <span
                        className="badge"
                        style={{
                          background: item.status === "booked" ? "var(--soft)" : "#fee2e2",
                          color: item.status === "booked" ? "var(--green)" : "#991b1b",
                        }}
                      >
                        {item.status}
                      </span>
                    </td>
                    <td>
                      <span className="badge" style={{ textTransform: "capitalize", fontSize: 11 }}>
                        {item.delivery_status}
                      </span>
                    </td>
                    <td>
                      {item.status === "booked" && (
                        <button
                          type="button"
                          className="button small secondary"
                          style={{ fontSize: 12, padding: "4px 8px", minHeight: 30, color: "#b75537" }}
                          onClick={() => handleCancelViewing(item.reference)}
                        >
                          Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <h2 style={{ fontSize: 22, margin: 0 }}>Reviewed Neighborhood Guides</h2>
            <button
              type="button"
              className="button small"
              onClick={() => setShowAreaModal(true)}
            >
              + Create Guide
            </button>
          </div>

          <div className="comparison-wrap">
            <table style={{ minWidth: 700 }}>
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Location Slugs</th>
                  <th>Overview Excerpt</th>
                  <th>Status</th>
                  <th>Reviewed</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {areas.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ textAlign: "center", color: "var(--muted)" }}>
                      No area guides published yet. Click &quot;+ Create Guide&quot; above to create one.
                    </td>
                  </tr>
                ) : (
                  areas.map((a) => (
                    <tr key={a.id}>
                      <td><strong>{a.title}</strong></td>
                      <td><code>/{a.city_slug}/{a.area_slug}</code></td>
                      <td style={{ maxWidth: 300, fontSize: 14 }}>
                        {a.overview_markdown ? a.overview_markdown.slice(0, 100) + "…" : "—"}
                      </td>
                      <td><span className="badge">{a.publication_status}</span></td>
                      <td style={{ fontSize: 13 }}>{formatPktDate(a.reviewed_at)}</td>
                      <td>
                        <Link
                          className="text-link"
                          href={`/areas/${encodeURIComponent(a.city_slug)}/${encodeURIComponent(a.area_slug)}`}
                          target="_blank"
                        >
                          View Public →
                        </Link>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {showAreaModal && (
            <div
              style={{
                position: "fixed",
                inset: 0,
                backgroundColor: "rgba(0,0,0,0.5)",
                display: "grid",
                placeItems: "center",
                zIndex: 100,
                padding: 16,
              }}
            >
              <div
                style={{
                  background: "var(--white)",
                  borderRadius: "var(--radius)",
                  padding: 28,
                  width: "min(640px, 100%)",
                  maxHeight: "90vh",
                  overflowY: "auto",
                }}
              >
                <h2 style={{ fontSize: 24, marginBottom: 16 }}>Create & Publish Area Guide</h2>
                <form className="form-stack" onSubmit={handleCreateAreaGuide}>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    <label className="field">
                      City Slug
                      <input
                        placeholder="karachi"
                        required
                        value={areaForm.city_slug}
                        onChange={(e) => setAreaForm({ ...areaForm, city_slug: e.target.value.toLowerCase().trim() })}
                      />
                    </label>
                    <label className="field">
                      Area Slug
                      <input
                        placeholder="clifton"
                        required
                        value={areaForm.area_slug}
                        onChange={(e) => setAreaForm({ ...areaForm, area_slug: e.target.value.toLowerCase().trim() })}
                      />
                    </label>
                  </div>
                  <label className="field">
                    Display Title
                    <input
                      placeholder="e.g. Clifton, Karachi"
                      required
                      value={areaForm.title}
                      onChange={(e) => setAreaForm({ ...areaForm, title: e.target.value })}
                    />
                  </label>
                  <label className="field">
                    Overview Markdown
                    <textarea
                      rows={3}
                      required
                      placeholder="High-level overview of the neighborhood and resident profile..."
                      value={areaForm.overview_markdown}
                      onChange={(e) => setAreaForm({ ...areaForm, overview_markdown: e.target.value })}
                    />
                  </label>
                  <label className="field">
                    Amenities & Lifestyle
                    <textarea
                      rows={2}
                      placeholder="Schools, hospitals, shopping malls, recreational facilities..."
                      value={areaForm.amenities_summary}
                      onChange={(e) => setAreaForm({ ...areaForm, amenities_summary: e.target.value })}
                    />
                  </label>
                  <label className="field">
                    Transport & Connectivity
                    <textarea
                      rows={2}
                      placeholder="Key arterial roads, highway access, commute times..."
                      value={areaForm.transport_info}
                      onChange={(e) => setAreaForm({ ...areaForm, transport_info: e.target.value })}
                    />
                  </label>
                  <label className="field">
                    Investment Outlook
                    <textarea
                      rows={2}
                      placeholder="Rental yields, capital appreciation trends, infrastructure projects..."
                      value={areaForm.investment_outlook}
                      onChange={(e) => setAreaForm({ ...areaForm, investment_outlook: e.target.value })}
                    />
                  </label>

                  <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 12 }}>
                    <button
                      type="button"
                      className="button secondary small"
                      onClick={() => setShowAreaModal(false)}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="button small"
                      disabled={loading}
                    >
                      Publish Area Guide
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
