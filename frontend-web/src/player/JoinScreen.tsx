import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import "./JoinScreen.css";
import { getSession, type SessionResponse, joinSession, regenerateName } from "../api/client";

interface JoinSessionResponse {
  player_id: string;
  name: string;
  session_id: string;
  game_id: string;
  hidden: boolean;
  game_started: boolean;
}

export default function JoinScreen() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();

  const [session, setSession] = useState<SessionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [isJoining, setIsJoining] = useState(false);
  const [error, setError] = useState("");

  const storedPlayerId = code ? sessionStorage.getItem("mezclar-player:" + code) : null;
  const isReturningPlayer = !!session && session.players.some((player) => player.player_id === storedPlayerId);
  const lateJoinBlocked = !!session && session.game_started && !session.allow_late_join && !isReturningPlayer;

  useEffect(() => {
    if (!code) return;
    let active = true;
    setLoading(true);
    setSession(null);
    setError("");
    getSession(code).then((found) => {
      if (active) setSession(found);
    }).catch((error) => {
      if (active) setError(error instanceof Error ? error.message : "Could not load the lobby.");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [code]);

  useEffect(() => {
  if (!code || !session || session.game_started || !session.auto_generate_names || name.trim()) return;

  const playerId = sessionStorage.getItem("mezclar-player:" + code) ?? crypto.randomUUID();

  joinSession(code, playerId, "")
    .then((result) => {
      sessionStorage.setItem("mezclar-player:" + code, result.player_id);
      setName(result.name);
    })
    .catch((error) => {
      console.error("Failed to pre-generate name:", error);
    });
}, [code, session]);

  async function handleRegenerate() {
    if (!code) {
      return;
    }
    const playerId = sessionStorage.getItem("mezclar-player:" + code);
    if (!playerId) return;

    try {
      const newName = await regenerateName(code, playerId);
      setName(newName);
    } catch (error) {
      console.error("Failed to regenerate name:", error);
    }
  }
  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    if (!code || !session || isJoining || (!name.trim() && !session.auto_generate_names)) return;

    setIsJoining(true);
    setError("");

    const playerId = sessionStorage.getItem("mezclar-player:" + code) ?? crypto.randomUUID();

    try {
      const response = await fetch(
        `/api/session/${code}/join`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            player_id: playerId,
            name: name.trim() || null,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Unable to join session.");
      }

      const sessionData: JoinSessionResponse = data;

      sessionStorage.setItem("mezclar-player:" + code, sessionData.player_id);
      const destination = sessionData.game_started
        ? `/player/${sessionData.session_id}/in-session`
        : `/player/${sessionData.session_id}`;
      navigate(destination, {
        state: {
          playerId: sessionData.player_id,
          playerName: sessionData.name,
          sessionId: sessionData.session_id,
          gameId: sessionData.game_id,
        },
      });
    } catch (error) {
      console.error("Failed to join session:", error);

      setError(
        error instanceof Error
          ? error.message
          : "Unable to join session. Please try again."
      );
    } finally {
      setIsJoining(false);
    }
  }

  if (!loading && !session) {
    return (
      <main className="join">
        <div className="join__inner">
          <header className="join__header">
            <p className="join__eyebrow">Game not found</p>

            <h1 className="join__title">{code}</h1>

            <p className="join__welcome">
              The game you are looking for doesn't exist. Check the code and try again.
            </p>
          </header>

          <Link className="join__submit join__home" to="/">
            Back to home
          </Link>
        </div>
      </main>
    );
  }

  if (lateJoinBlocked) {
    return (
      <main className="join">
        <div className="join__inner">
          <header className="join__header">
            <p className="join__eyebrow">Game in progress</p>

            <h1 className="join__title">{code}</h1>

            <p className="join__welcome">
              This game has already started and isn't accepting new players.
            </p>
          </header>

          <Link className="join__submit join__home" to="/">
            Back to home
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="join">
      <div className="join__inner">
        <header className="join__header">
          <p className="join__eyebrow">Joining game</p>

          <h1 className="join__title">{code}</h1>

          <p className="join__welcome">
            Enter your name to jump into the game.
          </p>
          {session && <p className="join__welcome">Hosted by {session.host_name}</p>}
        </header>

        {loading && <p>Finding lobby...</p>}
        <form className="join__form" onSubmit={handleSubmit}>
          <label className="join__label" htmlFor="player-name">
            Your name
          </label>
          <div className="join_input_row">
            <input
              id="player-name"
              className="join__name"
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Enter your name"
              maxLength={30}
              autoComplete="off"
              autoFocus
            />
            <button
              type="button"
              className="join-regenerate-button"
              onClick={handleRegenerate}
            >
              ↻
            </button>
          </div>

          {session?.auto_generate_names && <p>Leave blank for a generated name.</p>}

          <button
            className="join__submit"
            type="submit"
            disabled={isJoining || !session || (!name.trim() && !session.auto_generate_names)}
          >
            {isJoining ? "Joining..." : "Join game"}
          </button>

          {error && (
            <p className="join__error" role="alert">
              {error}
            </p>
          )}
        </form>

        <Link className="join__back" to="/">
          &larr; Back
        </Link>
      </div>
    </main>
  );
}