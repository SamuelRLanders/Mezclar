import type { LobbyPlayer } from "./usePlayerSocket";

interface PlayerRosterProps {
  players: LobbyPlayer[];
  playerId: string | null;
}

export default function PlayerRoster({ players, playerId }: PlayerRosterProps) {
  const me = players.find((player) => player.player_id === playerId);
  const isMod = me?.is_mod === true;
  return (
    <section
      style={{
        margin: "24px 0",
        padding: 24,
        border: "1px solid var(--border)",
        borderRadius: 12,
        textAlign: "left",
      }}
    >
      <h2 style={{ marginTop: 0, textAlign: "center" }}>
        Players ({players.length})
      </h2>

      {players.length > 0 ? (
        <ul
          style={{
            margin: 0,
            paddingLeft: 24,
            lineHeight: 1.6,
          }}
        >
          {players.map((player) => (
            <li key={player.player_id}>
              {player.name}
              {player.player_id === playerId ? " (you)" : ""}
              {isMod && player.player_id != playerId && (
                <>
              <button>Kick</button>
              <button>Hide</button>
              </>
            )}
            </li>
          ))}
        </ul>
      ) : (
        <p style={{ margin: 0, color: "var(--text-muted)" }}>
          No players to show yet.
        </p>
      )}
    </section>
  );
}
