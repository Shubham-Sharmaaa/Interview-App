import { useState } from "react";
import { api } from "../api.js";

export default function InterviewSetupScreen({ token, onInterviewCreated, onViewHistory }) {
  const [role, setRole] = useState("");
  const [yearsExperience, setYearsExperience] = useState("");
  const [skills, setSkills] = useState("");
  const [difficulty, setDifficulty] = useState("medium");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const skillsList = skills
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const interview = await api.createInterview(token, {
        role: role.trim(),
        years_experience: Number(yearsExperience),
        skills: skillsList,
        difficulty,
      });
      onInterviewCreated(interview);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="panel panel--narrow">
      <h2>Set up your interview</h2>
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="role">Target role</label>
          <input
            id="role"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            placeholder="Backend Engineer"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="years">Years of experience</label>
          <input
            id="years"
            type="number"
            min="0"
            step="0.5"
            value={yearsExperience}
            onChange={(e) => setYearsExperience(e.target.value)}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="skills">Skills or topics to focus on</label>
          <input
            id="skills"
            value={skills}
            onChange={(e) => setSkills(e.target.value)}
            placeholder="Python, SQL, System Design"
          />
        </div>
        <div className="field">
          <label htmlFor="difficulty">Difficulty</label>
          <select id="difficulty" value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </div>
        <button type="submit" className="primary-button" disabled={loading || !role || yearsExperience === ""}>
          {loading ? "Starting interview…" : "Start interview"}
        </button>
      </form>
      {error && <p className="error-box">{error}</p>}
      <p className="switch-mode">
        <button type="button" className="link-button" onClick={onViewHistory}>
          View past interviews
        </button>
      </p>
    </div>
  );
}
