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
}

export interface JoinSessionResponse extends SessionPlayer {
  session_id: string;
}

export interface UpdateReadyStatusRequest {
  ready: boolean;
}

export interface StartGameRequest {
  game_id: string;
  minimum_players: number;
  maximum_players: number;
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
  game_started: boolean;
  game_completed: boolean;
  game_id: string | null;
  minimum_players: number | null;
  maximum_players: number | null;
  current_round: number;
  current_prompt: string;
  answers: Record<string, string>;
}

export interface KickPlayerRequest {
  player_id: string;
}

export interface HidePlayerRequest {
  player_id: string;
  hidden: boolean;
}