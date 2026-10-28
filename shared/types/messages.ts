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
  game_started: boolean;
  game_id: string | null;
  minimum_players: number | null;
  maximum_players: number | null;
  current_round: number;
  current_prompt: string;
  answers: Record<string, string>;
  groups: SessionGroup[];
  round_duration_seconds: number | null;
  round_deadline: string | null;
  phase: string;
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