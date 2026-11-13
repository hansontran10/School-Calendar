import { useEffect, useState } from "react";
import * as api from "./api.js";

const KINDS = ["assignment", "exam", "quiz", "project", "reading", "other"];

const FLAG_TEXT = {
  no_date: "No date found. Set one before confirming.",
  before_term: "Date is before the term starts.",
  after_term: "Date is after the term ends.",
  weekday_mismatch: "The weekday in the syllabus doesn't match this date.",
  on_no_class_date: "Falls on a no-class date.",
  low_confidence: "The model was unsure about this one.",
};

function formatWhen(d) {
  if (!d.starts_at) return "No date";
  const when = new Date(d.starts_at);
  return d.all_day
    ? when.toLocaleDateString(undefined, { timeZone: d.timezone })
    : when.toLocaleString(undefined, { timeZone: d.timezone });
}

function CourseForm({ onCreated, onError }) {
  const [form, setForm] = useState({ code: "", name: "", term_start: "", term_end: "" });
  async function submit(e) {
    e.preventDefault();
    try {
      await api.createCourse({
        code: form.code,
        name: form.name || null,
        term_start: form.term_start || null,
        term_end: form.term_end || null,
      });
      setForm({ code: "", name: "", term_start: "", term_end: "" });
      onCreated();
    } catch (err) {
      onError(err.message);
    }
  }
  return (
    <form onSubmit={submit}>
      <h2>Add a course</h2>
      <input placeholder="Code (e.g. BIO 101)" value={form.code} required
        onChange={(e) => setForm({ ...form, code: e.target.value })} />
      <input placeholder="Name (optional)" value={form.name}
        onChange={(e) => setForm({ ...form, name: e.target.value })} />
      <label>Term start <input type="date" value={form.term_start}
        onChange={(e) => setForm({ ...form, term_start: e.target.value })} /></label>
      <label>Term end <input type="date" value={form.term_end}
        onChange={(e) => setForm({ ...form, term_end: e.target.value })} /></label>
      <button type="submit">Add course</button>
    </form>
  );
}

function UploadForm({ courses, onUploaded, onError }) {
  const [courseId, setCourseId] = useState("");
  const [file, setFile] = useState(null);
  const [provider, setProvider] = useState("");
  const [noClassDates, setNoClassDates] = useState("");
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setSummary(null);
    try {
      const result = await api.uploadSyllabus({ courseId, file, provider, noClassDates });
      setSummary(result);
      onUploaded();
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h2>Upload a syllabus</h2>
      <select value={courseId} onChange={(e) => setCourseId(e.target.value)} required>
        <option value="">Choose a course</option>
        {courses.map((c) => <option key={c.id} value={c.id}>{c.code}</option>)}
      </select>
      <input type="file" accept="application/pdf" required onChange={(e) => setFile(e.target.files[0])} />
      <select value={provider} onChange={(e) => setProvider(e.target.value)}>
        <option value="">Default AI provider</option>
        <option value="claude">Claude</option>
        <option value="openai">OpenAI</option>
        <option value="gemini">Gemini</option>
      </select>
      <input placeholder="No-class dates, e.g. 2027-03-08,2027-03-09 (optional)" value={noClassDates}
        onChange={(e) => setNoClassDates(e.target.value)} />
      <button type="submit" disabled={busy}>{busy ? "Reading syllabus..." : "Extract deadlines"}</button>
      {summary && (
        <p>
          {summary.provider} found {summary.items_found} items. {summary.created.length} added for review
          {summary.skipped_duplicates.length > 0 && `, ${summary.skipped_duplicates.length} already known`}.
        </p>
      )}
    </form>
  );
}

function ReviewItem({ item, onChange, onError }) {
  const [date, setDate] = useState("");
  async function act(fn) {
    try {
      await fn();
      onChange();
    } catch (err) {
      onError(err.message);
    }
  }
  return (
    <li className="review">
      <strong>{item.title}</strong> ({item.kind}) · {formatWhen(item)}
      {item.raw_text && <blockquote>{item.raw_text}</blockquote>}
      {item.review_flags.map((f) => <p key={f} className="flag">{FLAG_TEXT[f] ?? f}</p>)}
      <div className="actions">
        <input type="datetime-local" value={date} onChange={(e) => setDate(e.target.value)} />
        <button disabled={!date}
          onClick={() => act(() => api.updateDeadline(item.id, { starts_at: api.localInputToIso(date), all_day: false }))}>
          Set date
        </button>
        <button disabled={!item.starts_at} onClick={() => act(() => api.confirmDeadline(item.id))}>Confirm</button>
        <button onClick={() => act(() => api.rejectDeadline(item.id))}>Reject</button>
      </div>
    </li>
  );
}

export default function App() {
  const [courses, setCourses] = useState([]);
  const [pending, setPending] = useState([]);
  const [confirmed, setConfirmed] = useState([]);
  const [error, setError] = useState(null);
  const [form, setForm] = useState({ title: "", kind: "assignment", startsAt: "", courseId: "" });

  async function refresh() {
    try {
      const [c, p, d] = await Promise.all([
        api.listCourses(),
        api.listDeadlines("pending_review"),
        api.listDeadlines("confirmed"),
      ]);
      setCourses(c);
      setPending(p);
      setConfirmed(d);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function addManual(e) {
    e.preventDefault();
    try {
      await api.createDeadline(form);
      setForm({ ...form, title: "", startsAt: "" });
      await refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  const courseCode = (id) => courses.find((c) => c.id === id)?.code ?? "";

  return (
    <main>
      <h1>Deadline Sync</h1>
      {error && <p className="error">{error}</p>}

      <CourseForm onCreated={refresh} onError={setError} />
      <UploadForm courses={courses} onUploaded={refresh} onError={setError} />

      <section>
        <h2>Needs review ({pending.length})</h2>
        {pending.length === 0 ? <p>Nothing to review.</p> : (
          <ul className="review-list">
            {pending.map((d) => <ReviewItem key={d.id} item={d} onChange={refresh} onError={setError} />)}
          </ul>
        )}
      </section>

      <form onSubmit={addManual}>
        <h2>Add a deadline by hand</h2>
        <input placeholder="Title (e.g. Exam 1)" value={form.title} required
          onChange={(e) => setForm({ ...form, title: e.target.value })} />
        <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
          {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
        <select value={form.courseId} onChange={(e) => setForm({ ...form, courseId: e.target.value ? Number(e.target.value) : "" })}>
          <option value="">No course</option>
          {courses.map((c) => <option key={c.id} value={c.id}>{c.code}</option>)}
        </select>
        <input type="datetime-local" value={form.startsAt} required
          onChange={(e) => setForm({ ...form, startsAt: e.target.value })} />
        <button type="submit">Add deadline</button>
      </form>

      <section>
        <h2>Confirmed ({confirmed.length})</h2>
        <p><a href="/export/ics" download>Download .ics</a></p>
        <table>
          <thead><tr><th>When</th><th>Course</th><th>Title</th><th>Kind</th><th></th></tr></thead>
          <tbody>
            {confirmed.length === 0 && <tr><td colSpan={5}>No deadlines yet.</td></tr>}
            {confirmed.map((d) => (
              <tr key={d.id}>
                <td>{formatWhen(d)}</td>
                <td>{courseCode(d.course_id)}</td>
                <td>{d.title}</td>
                <td>{d.kind}</td>
                <td><button onClick={async () => {
                  try { await api.deleteDeadline(d.id); await refresh(); } catch (err) { setError(err.message); }
                }}>Delete</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
