// Thin wrapper around the FastAPI routes. Vite proxies these paths in dev.
export async function listDeadlines() {
  const r = await fetch("/deadlines");
  if (!r.ok) throw new Error(`load failed: ${r.status}`);
  return r.json();
}

export async function createDeadline({ title, kind, startsAt }) {
  // startsAt comes from <input type="datetime-local">, which has no offset.
  // Send it with the browser's offset so the server gets a timezone-aware value.
  const local = new Date(startsAt);
  const offset = -local.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const hh = String(Math.floor(Math.abs(offset) / 60)).padStart(2, "0");
  const mm = String(Math.abs(offset) % 60).padStart(2, "0");
  const iso = `${startsAt}:00${sign}${hh}:${mm}`;
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const r = await fetch("/deadlines", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, kind, starts_at: iso, timezone }),
  });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `save failed: ${r.status}`);
  }
  return r.json();
}

export async function deleteDeadline(id) {
  const r = await fetch(`/deadlines/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`delete failed: ${r.status}`);
}
