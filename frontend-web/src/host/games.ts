export interface GameSummary {
  id: string;
  name: string;
  minPlayers: number;
  maxPlayers: number;
  minMinutes: number;
  maxMinutes: number;
  description: string;
  rules: string;
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
    rules:
      `
        Players receive prompts and submit their funniest responses. 
        Responses are shown to the group, and players vote for their favorite. 
        The response with the most votes earns points. 
        Players continue through multiple rounds, with the highest-scoring players winning the game.
      `  
    
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
    rules:
      `
        Players are split into small groups and find each other using their group's color.
        Everyone in a group gets the same secret keyword, except one faker who gets nothing.
        Taking turns, each player says one word related to the keyword out loud.
        Everyone then types who they think the faker is. The faker types their guess at the keyword.
        Players win if they catch the faker and the faker guesses the keyword wrong. Otherwise the faker wins.
      `,
  },
];

export function formatPlayerRange(game: GameSummary): string {
  return `${game.minPlayers}–${game.maxPlayers} players`;
}

export function formatTimeRange(game: GameSummary): string {
  return `${game.minMinutes}–${game.maxMinutes} min`;
}
