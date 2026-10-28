import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { getSession, playerSocketUrl, type SessionResponse } from "../api/client";
import { GAMES } from "../host/games";
import QuipInput from "./QuipInput";
import useRoundTimer from "../useRoundTimer";

interface GameLandingState {
  playerId?: string;
  playerName?: string;
  sessionId?: string;
  gameId?: string;
}

export default function GameLanding() {
  const { code } = useParams<{ code: string }>();
  const { state } = useLocation() as {
    state: GameLandingState | null;
  };

  const {
    playerId = code ? sessionStorage.getItem("mezclar-player:" + code) : null,
    playerName,
    sessionId = code,
    gameId,
  } = state || {};

  // const sessionId = state?.sessionId;

  const [session, setSession] = useState<SessionResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const remainingSeconds = useRoundTimer(session?.remaining_seconds ?? 0, session?.game_paused ?? false, session?.current_round ?? 0);

  useEffect(() => {
    if (!sessionId) {
      setError("Missing session information. Please rejoin the game.");
      setLoading(false);
      return;
    }

    getSession(sessionId)
      .then(setSession)
      .catch((error: unknown) => {
        setError(
          error instanceof Error
            ? error.message
            : "Could not load the game."
        );
      })
      .finally(() => setLoading(false));
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId || !playerId) {
      return;
    }

    const websocket = new WebSocket(
      playerSocketUrl(sessionId, playerId),
    );

    websocket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);

        if (message.type === "round_updated") {
          getSession(sessionId)
            .then(setSession)
            .catch((error: unknown) => {
              setError(
                error instanceof Error
                  ? error.message
                  : "Could not load the next round.",
              );
            });
        }
      } catch (error) {
        console.error("Failed to process WebSocket message:", error);
      }
    };

    websocket.onerror = (event) => {
      console.error("Game updates WebSocket error:", event);
    };

    return () => {
      websocket.close();
    };
  }, [sessionId, playerId]);

  useEffect(() => {
    if (!sessionId) return;
    // Recover the current screen even if a WebSocket update was missed.
    const intervalId = window.setInterval(() => {
      getSession(sessionId)
        .then((data) => {
          setSession(data);
          setError("");
        })
        .catch((error: unknown) => console.error("Failed to refresh game:", error));
    }, 2000);
    return () => window.clearInterval(intervalId);
  }, [sessionId]);

  if (session?.game_completed) {
    return (
      <main style={{ maxWidth: 560, margin: "0 auto", padding: 24, textAlign: "center" }}>
        <h1>{GAMES.find((game) => game.id === session.game_id)?.name ?? session.game_id} complete</h1>
        <p role="status">The activity has finished. Thanks for playing!</p>
        <Link to="/">Return home</Link>
      </main>
    );
  }

  return (
    <main
      style={{
        maxWidth: 560,
        margin: "0 auto",
        padding: 24,
        textAlign: "center",
      }}
    >
      <p
        style={{
          color: "var(--text-muted)",
          fontSize: 14,
        }}
      >
        Game started
      </p>

      <h1>Get ready!</h1>

      <p>
        Welcome, {playerName ?? "Player"}.
      </p>

      {loading && <p>Loading game...</p>}

      {error && <p role="alert">{error}</p>}

      {!loading && !error && session && (
        <section>
          <h2>Round {session.current_round}</h2>
          <p role="status">{session.game_paused ? "Paused · " : ""}{remainingSeconds} seconds remaining</p>
          <p>{session.current_prompt ?? "No prompt selected yet."}</p>
          {session.game_id === "quiplash" && playerId && sessionId && (
            <QuipInput
              key={session.current_round}
              sessionId={sessionId}
              playerId={playerId}
              currentRound={session.current_round}
              disabled={session.game_paused || remainingSeconds === 0}
            />
          )}
        </section>
      )}

      

      <p>
        Game: {gameId ?? "Unknown"}
      </p>

      <Link to="/">Leave game</Link>
    </main>
  );
}