export interface ToggleAutoNamesRequest {
    enabled: boolean;
}

export interface ToggleProfanityFilterRequest {
    enabled: boolean;
}

export interface RegenerateNameRequest {
    player_id: string;
}

export interface GenerateNameResponse {
    name: string;
}

export interface SubmitNameRequest {
    player_id: string;
    requested_name: string;
}

export interface SessionPlayer {
  player_id: string;
  name: string;
  ready: boolean;
  hidden: boolean;
  is_mod: boolean
}

export interface JoinSessionResponse extends SessionPlayer {
  session_id: string;
  game_started: boolean;
}

export interface UpdateReadyStatusRequest {
  ready: boolean;
}

export interface StartGameRequest {
  game_id: string;
  minimum_players: number;
  maximum_players: number;
}

export interface SessionGroup {
  group_index: number;
  prompt: string;
  players: SessionPlayer[];
  answers: Record<string, string>;
  vote_counts: Record<string, number>;
}

export interface SessionEvent {
  id: number;
  timestamp: string;
  type: string;
  player_id: string | null;
  player_name: string | null;
  message: string;
}

export interface LeaderboardEntry {
  player_id: string;
  name: string;
  hidden: boolean;
  score: number;
  rank: number;
  waiting: boolean;
}

export interface SessionResponse {
  session_id: string;
  host_name: string;
  settings: {
    gameId?: string;
    options?: Record<string, boolean>;
  };
  player_count: number;
  players: SessionPlayer[];
  auto_generate_names: boolean;
  allow_late_join: boolean;
  requires_password: boolean;
  profanity_filter: boolean;
  game_started: boolean;
  game_id: string | null;
  minimum_players: number | null;
  maximum_players: number | null;
  current_round: number;
  total_rounds: number;
  current_prompt: string;
  answers: Record<string, string>;
  groups: SessionGroup[];
  round_duration_seconds: number | null;
  round_deadline: string | null;
  game_paused: boolean;
  paused_remaining: number | null;
  phase: string;
  scores: Record<string, number>;
  round_results: {
    round: number;
    groups: SessionGroup[];
  }[];
  event_log: SessionEvent[];
  leaderboard: LeaderboardEntry[];
  submitted_count: number;
  eligible_count: number;
  submitted_player_ids: string[];
}

export interface KickPlayerRequest {
  player_id: string;
}

export interface HidePlayerRequest {
  player_id: string;
  hidden: boolean;
}

export interface ModPlayerRequest {
  player_id: string;
  is_mod: boolean;
}

// The phases each Keywords group moves through, in order.
export type KeywordsPhase = "gathering" | "roles" | "speaking" | "voting" | "reveal";

export interface KeywordsMember {
  player_id: string;
  name: string;
}

// The outcome of one group's game, shown on the reveal screen.
export interface KeywordsResult {
  winner: "players" | "faker";
  faker_id: string;
  faker_name: string;
  keyword: string;
  faker_guess: string | null;
  faker_caught: boolean;
  faker_guessed_keyword: boolean;
  vote_counts: Record<string, number>;
}

/*
 * What one player is allowed to see; mirrors KeywordsGame.player_view() in the backend.
 * keyword is null for the faker, and for everyone until the roles phase.
 */
export interface KeywordsPlayerView {
  phase: KeywordsPhase;
  group_index: number;
  group_color: string;
  group_label: string;
  members: KeywordsMember[];
  ready_player_ids: string[];
  role_seen_player_ids: string[];
  is_faker: boolean;
  keyword: string | null;
  speaking_order: string[];
  current_speaker_id: string | null;
  has_submitted: boolean;
  submitted_count: number;
  result: KeywordsResult | null;
}

// One group as the host sees it, secrets included; mirrors KeywordsGame.host_view().
export interface KeywordsHostGroup {
  group_index: number;
  group_color: string;
  group_label: string;
  phase: KeywordsPhase;
  members: KeywordsMember[];
  keyword: string;
  faker_id: string;
  ready_player_ids: string[];
  role_seen_player_ids: string[];
  speaking_order: string[];
  current_speaker_id: string | null;
  submitted_player_ids: string[];
  result: KeywordsResult | null;
}

export interface KeywordsHostView {
  finished: boolean;
  groups: KeywordsHostGroup[];
}
