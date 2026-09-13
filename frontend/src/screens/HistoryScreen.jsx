import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function HistoryScreen({ token, onSelectInterview, onStartNew }) {
  const [interviews, setInterviews] = useState(null);
  const [listError, setListError] = useState(null);
  const [openingId, setOpeningId] = useState(null);
  const [openError, setOpenError] = useState(null);

  useEffect(() => {
    api
      .listInterviews(token)
      .then(setInterviews)
      .catch((err) => setListError(err.message));
  }, [token]);

  async function handleOpen(id) {
    setOpeningId(id);
    setOpenError(null);
    try {
      // Reopening a completed interview shows it read-only, and an
      // in-progress one resumes live from wherever it left off — both are
      // just "load the current document," no special resume logic, since
      // ChatScreen already renders either state from the same interview
      // object it uses for a freshly created one.
      const detail = await api.getInterview(token, id);
      onSelectInterview(detail);
    } catch (err) {
      setOpenError(err.message);
    } finally {
      setOpeningId(null);
    }
  }

  return (
    <div className="panel panel--wide">
      <h2>Your interviews</h2>
      <button type="button" className="primary-button" onClick={onStartNew}>
        Start a new interview
      </button>

      {listError && <p className="error-box">{listError}</p>}

      {interviews === null && !listError && <p className="history-status">Loading…</p>}

      {interviews && interviews.length === 0 && (
        <p className="history-status">No interviews yet — start your first one above.</p>
      )}

      {interviews && interviews.length > 0 && (
        <ul className="history-list">
          {interviews.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className="history-item"
                onClick={() => handleOpen(item.id)}
                disabled={openingId === item.id}
              >
                <span>
                  <span className="history-role">{item.config.role}</span>
                  <span className="history-meta">
                    {item.config.difficulty} · {item.question_count} question{item.question_count === 1 ? "" : "s"} ·{" "}
                    {item.status === "completed" ? "Completed" : "In progress"}
                  </span>
                </span>
                <span className="history-date">{new Date(item.created_at).toLocaleDateString()}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {openError && <p className="error-box">{openError}</p>}
    </div>
  );
}
