import { useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { GAMES } from "../host/games";
import { updateReadyStatus } from "../api/client";
import GameRules from "./GameRules";
import PlayerRoster from "./PlayerRoster";
import { type LobbyPlayer, usePlayerSocket } from "./usePlayerSocket";

interface PlayerLobbyState {
  playerId?: string;
  playerName?: string;
  sessionId?: string;
  gameId?: string;
}

export default function PlayerLobby() {
  const { code } = useParams<{ code: string }>();
  const { state } = useLocation() as {
    state: PlayerLobbyState | null;
  };

  const navigate = useNavigate();

  const sessionId = state?.sessionId ?? code;
  const playerId = state?.playerId ?? (sessionId ? sessionStorage.getItem("mezclar-player:" + sessionId) : null);
  const [saving, setSaving] = useState(false);

  const {
    playerName,
    gameId,
    ready,
    setReady,
    players,
    connectionStatus,
    error,
    setError,
  } = usePlayerSocket(sessionId, playerId, {
    initialName: state?.playerName,
    initialGameId: state?.gameId,
    onGameStarted: (message, connectedName) => {
      navigate(`/player/${sessionId}/game`, {
        state: {
          playerId,
          playerName: connectedName,
          sessionId,
          gameId: message.game_id,
        },
      });
    },
  });

  const game = GAMES.find((game) => game.id === gameId);

  async function handleReady() {
    if (!sessionId || !playerId || saving) return;
    setSaving(true);
    setError("");
    try {
      setReady((await updateReadyStatus(sessionId, playerId, !ready)).ready);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Could not update ready status.");
    } finally {
      setSaving(false);
    }
  }

  async function handleKick(target: LobbyPlayer) {
    try { 
      await fetch(`/api/session/${sessionId}/kick`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player_id: target.player_id }),
    });
    } catch (error) {
      setError(error instanceof Error ? error.message : "Could not kick player.");
    }
  }

  async function handleHide(target: LobbyPlayer) {
    const nextHidden = !target.is_hidden;
    try {
      await fetch(`/api/session/${sessionId}/hide`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player_id: target.player_id, hidden: nextHidden }),
    });
    } catch (error) {
      setError(error instanceof Error ? error.message : "Could not hide player.");
    }
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
      <h1>You're in!</h1>

      <p>
        Welcome to the game, {playerName}.
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

        <h2>Waiting for the host</h2>

        <p style={{ color: "var(--text-muted)" }}>
          The game will begin when the host starts it.
        </p>

        <p aria-live="polite" style={{ color: "var(--text-muted)" }}>
          {ready ? "You are ready." : "You are not ready yet."}
        </p>

        <button
          type="button"
          aria-pressed={ready}
          disabled={!playerId || saving || connectionStatus !== "Connected"}
          onClick={handleReady}
          style={{
            width: "100%",
            marginTop: 16,
            padding: 16,
            border: "none",
            borderRadius: 12,
            background: "var(--accent)",
            color: "var(--accent-text)",
            fontFamily: "inherit",
            fontSize: 16,
            fontWeight: 700,
            cursor: playerId && !saving ? "pointer" : "not-allowed",
            opacity: playerId && !saving ? 1 : 0.4,
          }}
        >
          {saving ? "Updating..." : ready ? "Mark not ready" : "I'm ready"}
        </button>

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

      <PlayerRoster players={players} playerId={playerId} onKick={handleKick} onHide={handleHide} />

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
