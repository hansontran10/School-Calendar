import { useEffect, useState } from "react";
import { createDeadline, deleteDeadline, listDeadlines } from "./api.js";

const KINDS = ["assignment", "exam", "quiz", "project", "reading", "other"];

export default function App() {
  const [deadlines, setDeadlines] = useState([]);
  const [error, setError] = useState(null);
  const [form, setForm] = useState({ title: "", kind: "assignment", startsAt: "" });

  async function refresh() {
    try {
      setDeadlines(await listDeadlines());
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function onSubmit(event) {
    event.preventDefault();
    try {
      await createDeadline(form);
      setForm({ title: "", kind: form.kind, startsAt: "" });
      await refresh();
    } catch (e) {
      setError(e.message);
    }
  }

  async function onDelete(id) {
    try {
      await deleteDeadline(id);
      await refresh();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <main>
      <h1>Deadline Sync</h1>
      {error && <p className="error">{error}</p>}

      <form onSubmit={onSubmit}>
        <input
          placeholder="Title (e.g. Exam 1)"
          value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
          required
        />
        <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
          {KINDS.map((k) => (
            <option key={k} value={k}>{k}</option>
          ))}
        </select>
        <input
          type="datetime-local"
          value={form.startsAt}
          onChange={(e) => setForm({ ...form, startsAt: e.target.value })}
          required
        />
        <button type="submit">Add deadline</button>
      </form>

      <p><a href="/export/ics" download>Download .ics</a></p>

      <table>
        <thead>
          <tr><th>When</th><th>Title</th><th>Kind</th><th></th></tr>
        </thead>
        <tbody>
          {deadlines.length === 0 && (
            <tr><td colSpan={4}>No deadlines yet.</td></tr>
          )}
          {deadlines.map((d) => (
            <tr key={d.id}>
              <td>{new Date(d.starts_at).toLocaleString()}</td>
              <td>{d.title}</td>
              <td>{d.kind}</td>
              <td><button onClick={() => onDelete(d.id)}>Delete</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
