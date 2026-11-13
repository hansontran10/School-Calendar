// Thin wrapper around the FastAPI routes. Vite proxies these paths in dev.

async function request(path, options = {}) {
  const r = await fetch(path, options);
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? "");
    throw new Error(`${r.status}: ${detail || r.statusText}`);
  }
  return r.status === 204 ? null : r.json();
}

const json = (method, body) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const browserTimezone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;

// <input type="datetime-local"> has no offset. Attach the browser's offset for that moment.
export function localInputToIso(value) {
  const offset = -new Date(value).getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const hh = String(Math.floor(Math.abs(offset) / 60)).padStart(2, "0");
  const mm = String(Math.abs(offset) % 60).padStart(2, "0");
  return `${value}:00${sign}${hh}:${mm}`;
}

export const listCourses = () => request("/courses");
export const createCourse = (course) => request("/courses", json("POST", course));

export const listDeadlines = (status) =>
  request(status ? `/deadlines?status=${encodeURIComponent(status)}` : "/deadlines");

export const createDeadline = ({ title, kind, startsAt, courseId }) =>
  request(
    "/deadlines",
    json("POST", {
      title,
      kind,
      starts_at: localInputToIso(startsAt),
      timezone: browserTimezone(),
      course_id: courseId || null,
    }),
  );

export const updateDeadline = (id, changes) => request(`/deadlines/${id}`, json("PATCH", changes));
export const confirmDeadline = (id) => request(`/deadlines/${id}/confirm`, { method: "POST" });
export const rejectDeadline = (id) => request(`/deadlines/${id}/reject`, { method: "POST" });
export const deleteDeadline = (id) => request(`/deadlines/${id}`, { method: "DELETE" });

export function uploadSyllabus({ courseId, file, provider, noClassDates }) {
  const form = new FormData();
  form.append("course_id", courseId);
  form.append("file", file);
  form.append("timezone", browserTimezone());
  if (provider) form.append("provider", provider);
  if (noClassDates) form.append("no_class_dates", noClassDates);
  return request("/syllabi", { method: "POST", body: form });
}
