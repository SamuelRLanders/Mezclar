import type {
  GameControlAction,
  JoinSessionResponse,
  KickPlayerRequest,
  SessionPlayer,
  SessionResponse,
  StartGameRequest,
  UpdateReadyStatusRequest,
} from "../../../shared/types/messages";

export async function toggleAutoNames(sessionId: string, enabled: boolean): Promise<void> {
  await apiResponse(await fetch(`/api/session/${sessionId}/toggle-auto-names`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  }));
}

export async function regenerateName(sessionId: string, player_id: string): Promise<string> {
  const data = await apiResponse<{ name : string }>(await fetch(`/api/session/${sessionId}/regenerate-name`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_id }),
  }));
  return data.name;
}

export type { GameControlAction, SessionPlayer, SessionResponse } from "../../../shared/types/messages";

async function apiResponse<T>(response: Response): Promise<T> {
  const data = await response.json();
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "Could not complete the request. Please try again.";
    throw new Error(detail);
  }
  return data as T;
}

export async function createSession(
  hostName: string,
  gameId: string,
  options: Record<string, boolean>,
): Promise<SessionResponse> {
  const session = await apiResponse<SessionResponse & { host_token: string }>(await fetch("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ host_name: hostName, settings: { gameId, options } }),
  }));
  sessionStorage.setItem("mezclar-host:" + session.session_id, session.host_token);
  return session;
}

export async function getSession(code: string): Promise<SessionResponse> {
  return apiResponse(await fetch("/api/session/" + code));
}

export async function joinSession(
  code: string, playerId: string, name: string,
): Promise<JoinSessionResponse> {
  return apiResponse(await fetch("/api/session/" + code + "/join", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_id: playerId, name: name.trim() || null }),
  }));
}

export async function updateReadyStatus(
  code: string, playerId: string, ready: boolean,
): Promise<SessionPlayer> {
  const body: UpdateReadyStatusRequest = { ready };
  return apiResponse(await fetch("/api/session/" + code + "/players/" + playerId + "/ready", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }));
}

export async function startGame(code: string, request: StartGameRequest): Promise<Pick<SessionResponse, "session_id" | "game_id" | "game_started" | "player_count">> {
  return apiResponse(await fetch("/api/session/" + code + "/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  }));
}

export function playerSocketUrl(code: string, playerId: string): string {
  const url = new URL("/ws/session/" + code + "/player/" + playerId, window.location.href);
  url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return url.href;
}

export async function kickPlayer(code: string, request: KickPlayerRequest): Promise<void> {
  return apiResponse(await fetch("/api/session/" + code + "/kick", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  }));
}

export async function hidePlayer(code: string, playerId: string, hidden: boolean): Promise<SessionPlayer> {
  const player = await apiResponse<SessionPlayer>(await fetch("/api/session/" + code + "/hide", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_id: playerId, hidden }),
  }));
  return player;
}

export async function submitAnswer(
  sessionId: string,
  playerId: string,
  answer: string,
  currentRound: number,
): Promise<void> {
  await apiResponse(await fetch(
    `/api/session/${sessionId}/submit-answer`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        player_id: playerId,
        answer,
        current_round: currentRound,
      }),
    },
  ));
}

export async function advanceRound(
  sessionId: string,
): Promise<void> {
  await apiResponse(await fetch(
    `/api/session/${sessionId}/advance-round`,
    {
      method: "POST",
      headers: { "X-Host-Token": sessionStorage.getItem("mezclar-host:" + sessionId) ?? "" },
    },
  ));
}

export async function controlGame(code: string, action: GameControlAction, currentRound: number): Promise<SessionResponse> {
  return apiResponse(await fetch(`/api/session/${code}/control`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Host-Token": sessionStorage.getItem("mezclar-host:" + code) ?? "",
    },
    body: JSON.stringify({ action, current_round: currentRound }),
  }));
}

export async function modPlayer(code: string, playerId: string, mod: boolean): Promise<SessionPlayer> {
  const player = await apiResponse<SessionPlayer>(await fetch("/api/session/" + code + "/mod", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_id: playerId, is_mod: mod }),
  }));
  return player;
}
