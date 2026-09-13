// Vite exposes env vars prefixed VITE_ to client code via import.meta.env.
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, { method = "GET", token, body } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const data = await res.json().catch(() => null);

  if (!res.ok) {
    // FastAPI's `detail` is a plain string for most errors, but the
    // answer-submission endpoint's 409 sends a structured object
    // ({reason, currentState}) so the caller can reconcile local state
    // instead of just showing an error — see ChatScreen.jsx.
    const message = typeof data?.detail === "string" ? data.detail : `Request failed (${res.status})`;
    const error = new Error(message);
    error.status = res.status;
    error.detail = data?.detail;
    throw error;
  }

  return data;
}

export const api = {
  signup: (email, password) => request("/auth/signup", { method: "POST", body: { email, password } }),
  login: (email, password) => request("/auth/login", { method: "POST", body: { email, password } }),
  me: (token) => request("/auth/me", { token }),
  createInterview: (token, config) => request("/interviews", { method: "POST", token, body: config }),
  listInterviews: (token) => request("/interviews", { token }),
  getInterview: (token, interviewId) => request(`/interviews/${interviewId}`, { token }),
  submitAnswer: (token, interviewId, questionIndex, answer) =>
    request(`/interviews/${interviewId}/answer`, {
      method: "POST",
      token,
      body: { question_index: questionIndex, answer },
    }),
};
