
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { advanceRound, getSession, type SessionResponse } from "../api/client";

export default function HostGameView() {
  const { code } = useParams<{ code: string }>();

  const [session, setSession] = useState<SessionResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const [isAdvancing, setIsAdvancing] = useState(false);
  const [advanceError, setAdvanceError] = useState("");

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

  async function handleAdvanceRound() {
    if (!code || isAdvancing) {
      return;
    }

    setIsAdvancing(true);
    setAdvanceError("");

    try {
      await advanceRound(code);
    } catch (error) {
      setAdvanceError(
        error instanceof Error
          ? error.message
          : "Unable to start the next round.",
      );
    } finally {
      setIsAdvancing(false);
    }
  }

  // Test push to repo

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
        {advanceError && <p role="alert">{advanceError}</p>}

        <button
          type="button"
          onClick={handleAdvanceRound}
          disabled={isAdvancing || !session?.game_started}
        >
          {isAdvancing ? "Starting next round..." : "Start Next Round"}
        </button>
      </section>

      <p style={{ marginTop: 24 }}>
        <Link to={`/host/lobby/${code}`}>Back to lobby</Link>
      </p>
    </main>
  );
}
