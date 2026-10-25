import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { playerSocketUrl } from "../api/client";

export interface LobbyPlayer {
  player_id: string;
  name: string;
  is_mod: boolean;
}

export interface GameStartedMessage {
  type: "game_started";
  session_id: string;
  game_id: string;
}

interface ConnectedMessage {
  type: "connected";
  session_id: string;
  player_id: string;
  name: string;
  ready: boolean;
  game_id: string;
  players: LobbyPlayer[];
}

interface PlayersUpdatedMessage {
  type: "players_updated";
  players: LobbyPlayer[];
}

interface PlayerSocketOptions {
  initialName?: string;
  initialGameId?: string;
  onGameStarted?: (message: GameStartedMessage, playerName: string) => void;
}

/**
 * Opens the player's websocket for a session and tracks the lobby state it
 * reports. Kicks are handled here; each page decides what game_started means.
 */
export function usePlayerSocket(
  sessionId: string | undefined,
  playerId: string | null,
  { initialName, initialGameId, onGameStarted }: PlayerSocketOptions = {},
) {
  const navigate = useNavigate();

  const [playerName, setPlayerName] = useState(initialName ?? "Player");
  const [gameId, setGameId] = useState<string | null>(initialGameId ?? null);
  const [ready, setReady] = useState(false);
  const [players, setPlayers] = useState<LobbyPlayer[]>([]);
  const [connectionStatus, setConnectionStatus] = useState(
    "Connecting..."
  );
  const [error, setError] = useState("");

  // Kept in a ref so a new callback on each render doesn't reopen the socket.
  const onGameStartedRef = useRef(onGameStarted);
  useEffect(() => {
    onGameStartedRef.current = onGameStarted;
  });

  useEffect(() => {
    if (!sessionId || !playerId) {
      setError("Missing session or player information.");
      setConnectionStatus("Disconnected");
      return;
    }

    let active = true;
    let connectedName = initialName ?? "Player";
    const websocket = new WebSocket(
      playerSocketUrl(sessionId, playerId)
    );

    websocket.onopen = () => {
      if (!active) return;
      setConnectionStatus("Connected");
      setError("");
    };

    websocket.onmessage = (event) => {
      if (!active) return;
      try {
        const message = JSON.parse(event.data);

        if (message.type === "kicked") {
          leaveLobby("You have been kicked from the session.")
          return;
        }

        if (message.type === "connected") {
          const connectedMessage = message as ConnectedMessage;

          connectedName = connectedMessage.name;
          setPlayerName(connectedMessage.name);
          setReady(connectedMessage.ready);
          setGameId(connectedMessage.game_id);
          setPlayers(connectedMessage.players);
        }
        if (message.type === "players_updated") {
          const playersUpdatedMessage =
            message as PlayersUpdatedMessage;

          setPlayers(playersUpdatedMessage.players);
        }
        if (message.type === "game_started") {
          onGameStartedRef.current?.(
            message as GameStartedMessage,
            connectedName
          );
        }
      } catch (error) {
        console.error(
          "Failed to process WebSocket message:",
          error
        );
      }
    };

    websocket.onerror = () => {
      if (!active) return;
      setConnectionStatus("Connection error");
      setError("Unable to connect to the game server.");
      setGameId(null);
      setPlayers([]);
    };

    websocket.onclose = (event) => {
      if (!active) return;
      if (event.code === 4403) {
        leaveLobby("You are no longer in this lobby")
        return;
      }
      setConnectionStatus("Disconnected");
      setError("Lost connection to the game server.");
      setGameId(null);
      setPlayers([]);
    };

    return () => {
      active = false;
      websocket.close();
    };

    function leaveLobby(notice: string) {
      active = false;
      websocket.close();
      if (sessionId) {
        sessionStorage.removeItem("mezclar-player:" + sessionId)
      }
      navigate("/", { replace: true, state: { notice } });
    }
  }, [navigate, playerId, initialName, sessionId]);

  return {
    playerName,
    gameId,
    ready,
    setReady,
    players,
    connectionStatus,
    error,
    setError,
  };
}
