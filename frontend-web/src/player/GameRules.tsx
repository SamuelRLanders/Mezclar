import { useEffect, useState } from "react";
import { GAMES } from "../host/games";

export default function GameRules({ gameId }: { gameId: string | null }) {
  const game = GAMES.find((entry) => entry.id === gameId);
  const [rules, setRules] = useState<string[] | null>(null);

  useEffect(() => {
    if (!gameId) return;

    const controller = new AbortController();
    const { signal } = controller;
    const url = `${import.meta.env.BASE_URL}game-rules/${encodeURIComponent(gameId)}.json`;
    fetch(url, { signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("Rules unavailable");
        const data: unknown = await response.json();
        if (signal.aborted) return;
        setRules(Array.isArray(data)
          ? data.filter((rule): rule is string => typeof rule === "string" && rule.trim() !== "")
          : []);
      })
      .catch(() => {
        if (!signal.aborted) setRules([]);
      });

    return () => controller.abort();
  }, [gameId]);

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
        {game?.name ?? "Rules"}
      </h2>

      {game && <h3 style={{ marginBottom: 8 }}>Rules</h3>}

      {gameId && rules === null ? (
        <p role="status">Loading rules...</p>
      ) : rules?.length ? (
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
        <p role="status" style={{ marginTop: 0, color: "var(--text-muted)" }}>
          Rules for this game are not available yet. Ask the host how to play.
        </p>
      )}
    </section>
  );
}
