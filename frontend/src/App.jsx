import { useEffect, useState } from "react";
import { api } from "./api.js";
import AuthScreen from "./screens/AuthScreen.jsx";
import InterviewSetupScreen from "./screens/InterviewSetupScreen.jsx";
import HistoryScreen from "./screens/HistoryScreen.jsx";
import ChatScreen from "./screens/ChatScreen.jsx";

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem("token"));
  // Undetermined until the token (if any) has been checked against the
  // backend once -- avoids flashing the login screen for a split second
  // on every reload before we know a stored token is still valid.
  const [checkingToken, setCheckingToken] = useState(Boolean(localStorage.getItem("token")));
  const [interview, setInterview] = useState(null);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    if (!token) {
      setCheckingToken(false);
      return;
    }
    api
      .me(token)
      .catch(() => {
        // Expired or otherwise invalid -- the token is a claim, not a
        // guarantee (see app/deps.py on the backend); treat it as logged out.
        localStorage.removeItem("token");
        setToken(null);
      })
      .finally(() => setCheckingToken(false));
  }, [token]);

  function handleAuthenticated(newToken) {
    localStorage.setItem("token", newToken);
    setToken(newToken);
  }

  function handleLogout() {
    // Stateless JWT: there's no server-side session to invalidate, so
    // logout is purely client-side -- see the auth design in the brief.
    localStorage.removeItem("token");
    setToken(null);
    setInterview(null);
    setShowHistory(false);
  }

  function startNew() {
    setInterview(null);
    setShowHistory(false);
  }

  let content;
  if (checkingToken) {
    content = null;
  } else if (!token) {
    content = <AuthScreen onAuthenticated={handleAuthenticated} />;
  } else if (interview) {
    // Reopening from history and creating fresh both land here — an
    // interview object is an interview object, whether it's brand new or
    // fetched from GET /interviews/{id}; ChatScreen doesn't need to know
    // which.
    content = <ChatScreen token={token} interview={interview} setInterview={setInterview} onStartNew={startNew} />;
  } else if (showHistory) {
    content = <HistoryScreen token={token} onSelectInterview={setInterview} onStartNew={startNew} />;
  } else {
    content = (
      <InterviewSetupScreen token={token} onInterviewCreated={setInterview} onViewHistory={() => setShowHistory(true)} />
    );
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <p className="app-title">AI Mock Interview</p>
        {token && (
          <button type="button" className="link-button" onClick={handleLogout}>
            Log out
          </button>
        )}
      </header>
      <main className="app-main">{content}</main>
    </div>
  );
}
