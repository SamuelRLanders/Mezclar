import type { GameSummary } from "../host/games";

export default function GameRules({ game }: { game: GameSummary }) {
  const rules = game.rules.split("\n").map((rule) => rule.trim()).filter(Boolean);

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
        {game.name}
      </h2>

      <h3 style={{ marginBottom: 8 }}>Rules</h3>

      {rules.length > 0 ? (
        <ul
          style={{
            marginTop: 0,
            paddingLeft: 24,
            color: "var(--text-muted)",
            lineHeight: 1.6,
          }}
        >
          {rules.map((rule, index) => (
            <li key={index}>{rule}</li>
          ))}
        </ul>
      ) : (
        <p style={{ marginTop: 0, color: "var(--text-muted)" }}>
          Rules for this game are not available yet. Ask the host how to play.
        </p>
      )}
    </section>
  );
}
