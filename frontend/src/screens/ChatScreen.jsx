import { useState } from "react";
import { api } from "../api.js";

// Must match app/services/interview_service.py's MAX_TURNS. Not exposed by
// the API since it's a fixed constant both sides agree on, not per-request
// config -- flagging the duplication here rather than hiding it.
const MAX_TURNS = 6;

export default function ChatScreen({ token, interview, setInterview, onStartNew }) {
  const [answerText, setAnswerText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  const isCompleted = interview.status === "completed";
  const currentTurn = isCompleted ? null : interview.turns[interview.current_question_index];
  // A turn with a saved answer that never got resolved means a previous AI
  // call failed -- see the answer/retry state machine. The saved answer is
  // shown read-only; retrying resends it rather than letting it be edited,
  // since a fresh answer would defeat the point of "the answer is safe."
  const awaitingRetry = Boolean(currentTurn && currentTurn.answer !== null && !currentTurn.resolved);

  async function submit(questionIndex, text) {
    setSubmitting(true);
    setErrorMessage(null);
    try {
      const updated = await api.submitAnswer(token, interview.id, questionIndex, text);
      setInterview(updated);
      setAnswerText("");
    } catch (err) {
      if (err.status === 409 && err.detail?.currentState) {
        // Our local view was stale (e.g. a lost success response from an
        // earlier request) -- reconcile to the server's real state instead
        // of showing this as a hard failure.
        setInterview(err.detail.currentState);
      } else {
        setErrorMessage(err.message);
      }
    } finally {
      setSubmitting(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (!answerText.trim()) return;
    submit(currentTurn.index, answerText.trim());
  }

  function handleRetry() {
    submit(currentTurn.index, currentTurn.answer);
  }

  const doneCount = isCompleted ? MAX_TURNS : interview.turns.length - 1;

  return (
    <div className="panel panel--wide">
      <div className="progress" aria-hidden="true">
        {Array.from({ length: MAX_TURNS }).map((_, i) => (
          <div key={i} className={`progress-dot ${i < doneCount ? "progress-dot--done" : ""}`} />
        ))}
      </div>

      <div className="transcript">
        {interview.turns.map((turn) => (
          <div className="turn" key={turn.index}>
            <p className="turn-question-label">Interviewer</p>
            <p className="turn-question">{turn.question}</p>
            {turn.answer !== null && (
              <>
                <p className="turn-answer-label">You</p>
                <p className="turn-answer">{turn.answer}</p>
              </>
            )}
          </div>
        ))}
      </div>

      {isCompleted && interview.feedback && (
        <section className="feedback">
          <h3>Feedback</h3>
          <div className="rating">
            <span className="rating-value">{interview.feedback.rating}</span>
            <span className="rating-scale">/ 5</span>
          </div>
          <p>{interview.feedback.rating_explanation}</p>

          <div className="feedback-section">
            <h4>Strengths</h4>
            <ul>
              {interview.feedback.strengths.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </div>
          <div className="feedback-section">
            <h4>Weaknesses</h4>
            <ul>
              {interview.feedback.weaknesses.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </div>
          <div className="feedback-section">
            <h4>Suggestions</h4>
            <ul>
              {interview.feedback.suggestions.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </div>

          <button type="button" className="primary-button" style={{ marginTop: "1.5rem" }} onClick={onStartNew}>
            Start another interview
          </button>
        </section>
      )}

      {awaitingRetry && (
        <div className="retry-box">
          <p>Your answer was saved, but the interviewer hit a snag generating the next question.</p>
          <button type="button" className="primary-button" onClick={handleRetry} disabled={submitting}>
            {submitting ? "Retrying…" : "Retry"}
          </button>
        </div>
      )}

      {!isCompleted && !awaitingRetry && currentTurn && (
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="answer">Your answer</label>
            <textarea
              id="answer"
              value={answerText}
              onChange={(e) => setAnswerText(e.target.value)}
              disabled={submitting}
              required
              maxLength={5000}
            />
          </div>
          <button type="submit" className="primary-button" disabled={submitting || !answerText.trim()}>
            {submitting ? "Sending…" : "Send"}
          </button>
        </form>
      )}

      {errorMessage && <p className="error-box">{errorMessage}</p>}
    </div>
  );
}
