export interface GameSummary {
  id: string;
  name: string;
  minPlayers: number;
  maxPlayers: number;
  minMinutes: number;
  maxMinutes: number;
  description: string;
}

export const GAMES: GameSummary[] = [
  {
    id: "quiplash",
    name: "Quiplash",
    minPlayers: 10,
    maxPlayers: 50,
    minMinutes: 5,
    maxMinutes: 30,
    description:
      "Players compete in a tournament to see who can respond with the funniest quips to prompts.",
  },
  {
    id: "keywords",
    name: "Keywords",
    minPlayers: 3,
    maxPlayers: 60,
    minMinutes: 5,
    maxMinutes: 10,
    description:
      "Small groups share a secret word, except for one faker. Everyone says a related word out loud, then the group votes on who was bluffing.",
  },
];

export function formatPlayerRange(game: GameSummary): string {
  return `${game.minPlayers}–${game.maxPlayers} players`;
}

export function formatTimeRange(game: GameSummary): string {
  return `${game.minMinutes}–${game.maxMinutes} min`;
}
