import { Link, useLocation, useParams } from "react-router-dom";

import { GAMES } from "../host/games";
import GameRules from "./GameRules";
import PlayerRoster from "./PlayerRoster";
import { usePlayerSocket } from "./usePlayerSocket";

interface GameInSessionState {
  playerId?: string;
  playerName?: string;
  sessionId?: string;
  gameId?: string;
}

export default function GameInSession() {
  const { code } = useParams<{ code: string }>();
  const { state } = useLocation() as {
    state: GameInSessionState | null;
  };

  const sessionId = state?.sessionId ?? code;
  const playerId = state?.playerId ?? (sessionId ? sessionStorage.getItem("mezclar-player:" + sessionId) : null);

  // No onGameStarted: the game is already running, and the server repeats
  // game_started on every connect.
  const { playerName, gameId, players, connectionStatus, error } =
    usePlayerSocket(sessionId, playerId, {
      initialName: state?.playerName,
      initialGameId: state?.gameId,
    });

  const game = GAMES.find((game) => game.id === gameId);

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
        Game in progress
      </p>

      <h1>You made it!</h1>

      <p>
        Welcome, {playerName}. This game has already started.
      </p>

      {game && <GameRules game={game} />}

      <section
        style={{
          margin: "24px 0",
          padding: 24,
          border: "1px solid var(--border)",
          borderRadius: 12,
        }}
      >
        <p
          style={{
            margin: 0,
            color: "var(--text-muted)",
          }}
        >
          Game Code
        </p>

        <h2
          style={{
            margin: "8px 0 24px",
            fontSize: 40,
            letterSpacing: 6,
          }}
        >
          {sessionId}
        </h2>

        <h2>Waiting for a good moment to insert you into the game...</h2>

        <p style={{ color: "var(--text-muted)" }}>
          Read the rules while you wait.
        </p>

        <p
          style={{
            marginTop: 24,
            color: "var(--text-muted)",
            fontSize: 14,
          }}
        >
          Connection: {connectionStatus}
        </p>
      </section>

      <PlayerRoster players={players} playerId={playerId} />

      {error && (
        <p
          role="alert"
          style={{
            color: "var(--text-muted)",
          }}
        >
          {error}
        </p>
      )}

      <Link to="/">Leave game</Link>
    </main>
  );
}
