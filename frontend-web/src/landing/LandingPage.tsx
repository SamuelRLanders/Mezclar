import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import mezclarLogo from "../assets/mezclar-logo.png";
import "./LandingPage.css";

// The backend does not define a join-code format yet. Change this (and the
// sanitizer below) once session codes are actually generated server-side.
const JOIN_CODE_LENGTH = 4;

function sanitizeCode(raw: string): string {
  return raw
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, "")
    .slice(0, JOIN_CODE_LENGTH);
}

export default function LandingPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  // Set when a player is sent here after being kicked or removed.
  const [notice, setNotice] = useState<string>(
    (location.state as { notice?: string } | null)?.notice ?? "",
  );

  // Clear it from history so a refresh doesn't show it again.
  useEffect(() => {
    if (location.state) navigate(location.pathname, { replace: true, state: null });
  }, [location, navigate]);

  const isComplete = code.length === JOIN_CODE_LENGTH;

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!isComplete) {
      setError(code ? `Game codes are ${JOIN_CODE_LENGTH} characters long.` : "Please enter a game code.");
      return;
    }
    navigate(`/join/${code}`);
  }

  return (
    <main className="landing">
      <div className="landing__inner">
        <header className="landing__header">
          <img className="landing__title" src={mezclarLogo} alt="Mezclar" />
          <p className="landing__welcome">
            Get a room talking. Enter your game code to jump in.
          </p>
        </header>

        {notice && (
          <div className="landing__notice" role="alert">
            <span>{notice}</span>
            <button type="button" aria-label="Dismiss" onClick={() => setNotice("")}>
              ×
            </button>
          </div>
        )}

        <form className="landing__join" onSubmit={handleSubmit}>
          <input
            id="join-code"
            className="landing__code"
            value={code}
            onChange={(event) => {
              setCode(sanitizeCode(event.target.value));
              setError("");
            }}
            placeholder="AB12"
            inputMode="text"
            autoComplete="off"
            autoCapitalize="characters"
            autoCorrect="off"
            spellCheck={false}
            maxLength={JOIN_CODE_LENGTH}
            autoFocus
          />
          <button className="landing__submit" type="submit">
            Join game
          </button>
        </form>
        {error && <p role="alert">{error}</p>}

        <button
          className="landing__host"
          type="button"
          onClick={() => navigate("/host/new")}
        >
          Host a game instead
        </button>
      </div>

      <footer className="landing__footer">
        <button
          className="landing__howto"
          type="button"
          onClick={() => navigate("/about")}
        >
          About Mezclar
        </button>
      </footer>
    </main>
  );
}
