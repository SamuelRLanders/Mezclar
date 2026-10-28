
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { controlGame, getSession, type GameControlAction, type SessionResponse } from "../api/client";
import { GAMES } from "./games";
import useRoundTimer from "../useRoundTimer";

export default function HostGameView() {
  const { code } = useParams<{ code: string }>();

  const [session, setSession] = useState<SessionResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const [isControlling, setIsControlling] = useState(false);
  const [controlError, setControlError] = useState("");
  const remainingSeconds = useRoundTimer(session?.remaining_seconds ?? 0, session?.game_paused ?? false, session?.current_round ?? 0);
  const hasHostAccess = !!code && !!sessionStorage.getItem("mezclar-host:" + code);
  const controlsDisabled = isControlling || !hasHostAccess || !session?.game_started || session.game_completed || session.game_id !== "quiplash" || remainingSeconds === 0;

  useEffect(() => {
    if (!code) {
      setError("No session code found.");
      setLoading(false);
      return;
    }

    let isMounted = true;

    async function loadSession() {
      try {
        const data = await getSession(code!);

        if (isMounted) {
          setSession(data);
          setError("");
        }
      } catch (error) {
        if (isMounted) {
          setError(
            error instanceof Error
              ? error.message
              : "Unable to load the game.",
          );
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadSession();

    const intervalId = window.setInterval(loadSession, 2000);

    return () => {
      isMounted = false;
      window.clearInterval(intervalId);
    };
  }, [code]);

  async function handleControl(action: GameControlAction) {
    if (!code || !session || controlsDisabled) {
      return;
    }

    setIsControlling(true);
    setControlError("");

    try {
      setSession(await controlGame(code, action, session.current_round));
    } catch (error) {
      setControlError(
        error instanceof Error
          ? error.message
          : "Unable to update the game.",
      );
    } finally {
      setIsControlling(false);
    }
  }

  if (session?.game_completed) {
    return (
      <main style={{ maxWidth: 900, margin: "0 auto", padding: 24 }}>
        <h1>{GAMES.find((game) => game.id === session.game_id)?.name ?? session.game_id} complete</h1>
        <p role="status">The activity has finished. Thanks for playing!</p>
        <Link to="/">Return home</Link>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 900, margin: "0 auto", padding: 24 }}>
      <header>
        <p style={{ color: "var(--text-muted)", marginBottom: 4 }}>
          Host gameplay · Join code: {code}
        </p>
        <h1>Game Moderation</h1>
      </header>

      {loading && <p>Loading game...</p>}
      {error && <p role="alert">{error}</p>}

      {session && (
        <>
          <section
            style={{
              marginTop: 24,
              padding: 24,
              border: "1px solid var(--border)",
              borderRadius: 12,
            }}
          >
            <p style={{ color: "var(--text-muted)" }}>
              Round {session.current_round}
            </p>
            <p role="status">{session.game_paused ? "Paused · " : ""}{remainingSeconds} seconds remaining</p>
            <h2>Current prompt</h2>
            <p>{session.current_prompt ?? "No prompt available."}</p>
          </section>

          <section style={{ marginTop: 24 }}>
            <h2>Player responses</h2>
            <p style={{ color: "var(--text-muted)" }}>
              Submitted answers will appear here.
            </p>

            {session.players.map((player) => (
              <article
                key={player.player_id}
                style={{
                  marginTop: 12,
                  padding: 16,
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                }}
              >
                <h3 style={{ marginTop: 0 }}>
                  {player.hidden ? "Hidden player" : player.name}
                </h3>
                <p>
                  {session.answers[player.player_id] ?? "Waiting for response..."}
                </p>
              </article>
            ))}
          </section>
        </>
      )}

      <section style={{ marginTop: 32, textAlign: "center" }}>
        {controlError && <p role="alert">{controlError}</p>}
        {session && !hasHostAccess && <p>Open the original host tab to control this game.</p>}

        <div style={{ display: "flex", justifyContent: "center", flexWrap: "wrap", gap: 8 }}>
          <button
            type="button"
            onClick={() => handleControl(session?.game_paused ? "resume" : "pause")}
            disabled={controlsDisabled}
            aria-pressed={session?.game_paused ?? false}
          >
            {session?.game_paused ? "Resume" : "Pause"}
          </button>
          <button type="button" onClick={() => handleControl("skip")} disabled={controlsDisabled}>Skip round</button>
          <button type="button" onClick={() => handleControl("extend")} disabled={controlsDisabled}>Add 30 seconds</button>
        </div>
        {isControlling && <p role="status">Updating game...</p>}
      </section>

      <p style={{ marginTop: 24 }}>
        <Link to={`/host/lobby/${code}`}>Back to lobby</Link>
      </p>
    </main>
  );
}
