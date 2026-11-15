import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  getKeywordsHostState,
  hostSocketUrl,
  type KeywordsHostGroup,
  type KeywordsHostView as KeywordsHostData,
} from "../../api/client";
// Reused for the group color classes (keywords--red, keywords--blue, ...).
import "../../player/keywords/Keywords.css";
import "./KeywordsHost.css";

// What the host sees for each phase, in plain words.
const PHASE_LABELS: Record<KeywordsHostGroup["phase"], string> = {
  gathering: "Finding their group",
  roles: "Reading roles",
  speaking: "Saying words",
  voting: "Voting",
  reveal: "Results in",
};

/*
 * The host's page for a Keywords game (US 60, plus the "update host view" task
 * of US 61-65). Shows every group's phase, keyword, faker, and each member's
 * progress. Groups play at their own pace, so the page refreshes whenever the
 * backend pings the host socket after a player acts.
 */
export default function KeywordsHostView() {
  const { code } = useParams<{ code: string }>();
  const [game, setGame] = useState<KeywordsHostData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!code) {
      setError("No session code found.");
      return;
    }

    // Stops state updates after the host leaves the page.
    let active = true;
    let reconnectTimeout: number;
    let websocket: WebSocket;

    async function reload() {
      try {
        const data = await getKeywordsHostState(code!);
        if (active) {
          setGame(data);
          setError("");
        }
      } catch (error) {
        if (active) setError(error instanceof Error ? error.message : "Could not load the game.");
      }
    }

    // Any message on the host socket means a player acted, so fetch the latest state.
    function connect() {
      websocket = new WebSocket(hostSocketUrl(code!));
      websocket.onopen = () => void reload();
      websocket.onmessage = () => void reload();
      websocket.onclose = () => {
        if (active) reconnectTimeout = window.setTimeout(connect, 1000);
      };
    }

    reload();
    connect();

    return () => {
      active = false;
      window.clearTimeout(reconnectTimeout);
      websocket.close();
    };
  }, [code]);

  const singleGroup = game?.groups.length === 1;
  const playerCount = game?.groups.reduce((total, group) => total + group.members.length, 0) ?? 0;
  const finishedGroups = game?.groups.filter((group) => group.phase === "reveal").length ?? 0;

  return (
    <main className="keywords-host">
      <header className="keywords-host__header">
        <p className="keywords-host__eyebrow">Keywords · Join code {code}</p>
        <h1>{game?.finished ? "Game over" : "Host view"}</h1>

        {/* Game details at a glance (US 60 AC3). */}
        {game && (
          <p className="keywords-host__details">
            {playerCount} players · {game.groups.length} {game.groups.length === 1 ? "group" : "groups"} ·{" "}
            {finishedGroups}/{game.groups.length} finished
          </p>
        )}
      </header>

      {error && <p role="alert" className="keywords-host__error">{error}</p>}
      {!game && !error && <p>Loading game...</p>}

      {/* One card per group, listing its players (US 60 AC2) and their progress. */}
      {game && (
        <div className="keywords-host__groups">
          {game.groups.map((group) => (
            <GroupCard key={group.group_index} group={group} singleGroup={singleGroup} />
          ))}
        </div>
      )}

      <Link to="/" className="keywords-host__home">Back to home</Link>
    </main>
  );
}

/*
 * One group: its phase, keyword and faker, each member's progress in the
 * current phase, and the outcome once the group reaches the reveal.
 */
function GroupCard({ group, singleGroup }: { group: KeywordsHostGroup; singleGroup: boolean }) {
  // Look up a member's display name from their ID.
  const nameOf = (id: string) =>
    group.members.find((member) => member.player_id === id)?.name ?? "Unknown player";

  // While speaking, list members in speaking order so the host can follow along.
  const memberIds =
    group.phase === "speaking" ? group.speaking_order : group.members.map((member) => member.player_id);

  // A single group gets no color, matching the players' screens.
  const colorClass = singleGroup ? "" : ` keywords--${group.group_color.toLowerCase()}`;

  return (
    <article className={`keywords-host__card${colorClass}`}>
      <p className="keywords-host__eyebrow">
        {singleGroup ? "Everyone" : `${group.group_label} Group`}
      </p>
      <h2>{PHASE_LABELS[group.phase]}</h2>

      <dl className="keywords-host__secrets">
        <dt>Keyword</dt>
        <dd>{group.keyword}</dd>
        <dt>Faker</dt>
        <dd>{nameOf(group.faker_id)}</dd>
      </dl>

      {group.result && (
        <p className="keywords-host__result">
          <strong>{group.result.winner === "faker" ? "The faker wins!" : "Players win!"}</strong>{" "}
          The faker guessed "{group.result.faker_guess ?? "nothing"}".
        </p>
      )}

      <ul className="keywords-host__members">
        {memberIds.map((id) => (
          <li key={id}>
            <span>
              {nameOf(id)}
              {id === group.faker_id && <span className="keywords-host__faker-tag"> faker</span>}
            </span>
            <span className="keywords-host__status">{memberStatus(group, id)}</span>
          </li>
        ))}
      </ul>
    </article>
  );
}

// What a member is doing (or has done) in their group's current phase.
function memberStatus(group: KeywordsHostGroup, playerId: string): string {
  switch (group.phase) {
    case "gathering":
      return group.ready_player_ids.includes(playerId) ? "✓ Found group" : "Looking...";
    case "roles":
      return group.role_seen_player_ids.includes(playerId) ? "✓ Read role" : "Reading...";
    case "speaking": {
      if (group.current_speaker_id === playerId) return "Speaking now";
      const position = group.speaking_order.indexOf(playerId);
      const current = group.speaking_order.indexOf(group.current_speaker_id ?? "");
      return position < current ? "✓ Spoke" : "Waiting to speak";
    }
    case "voting":
      return group.submitted_player_ids.includes(playerId) ? "✓ Answered" : "Answering...";
    case "reveal": {
      const votes = group.result?.vote_counts[playerId] ?? 0;
      return `${votes} ${votes === 1 ? "vote" : "votes"}`;
    }
  }
}
