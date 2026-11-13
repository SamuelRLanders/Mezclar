import type {
  JoinSessionResponse,
  KeywordsHostView,
  KeywordsPlayerView,
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

export type {
  KeywordsHostGroup,
  KeywordsHostView,
  KeywordsPlayerView,
  KeywordsResult,
  LeaderboardEntry,
  SessionEvent,
  SessionPlayer,
  SessionResponse,
} from "../../../shared/types/messages";

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
  password?: string
): Promise<SessionResponse & { host_token: string }> {
  return apiResponse(await fetch("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ host_name: hostName, settings: { gameId, options }, password: password || null }),
  }));
}

export async function getSession(code: string): Promise<SessionResponse> {
  return apiResponse(await fetch("/api/session/" + code));
}

const DEVICE_TOKEN_KEY = "mezclar-device";

// One token per browser, kept across tabs and visits so a kick sticks to the device.
export function getDeviceToken(): string {
  let token = localStorage.getItem(DEVICE_TOKEN_KEY);
  if (!token) {
    token = crypto.randomUUID();
    localStorage.setItem(DEVICE_TOKEN_KEY, token);
  }
  return token;
}

export async function joinSession(
  code: string, playerId: string, name: string, password?: string
): Promise<JoinSessionResponse> {
  return apiResponse(await fetch("/api/session/" + code + "/join", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      player_id: playerId,
      name: name.trim() || null,
      password: password?.trim() || null,
      device_token: getDeviceToken(),
    }),
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
  const path = "/ws/session/" + code + "/player/" + playerId;
  // Vercel can't proxy WebSockets, so in production connect straight to the backend
  // (VITE_WS_URL, e.g. "wss://api.example.com"). Unset locally, so Vite's /ws proxy is used.
  const base = import.meta.env.VITE_WS_URL;
  if (base) return base + path;
  const url = new URL(path, window.location.href);
  url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return url.href;
}

export function hostSocketUrl(code: string): string {
  const url = new URL(playerSocketUrl(code, "host"));
  url.pathname = `/ws/session/${code}/host`;
  url.searchParams.set("token", sessionStorage.getItem("mezclar-host:" + code) ?? "");
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


export async function submitVote(
  sessionId: string,
  voterId: string,
  groupIndex: number,
  answerOwnerId: string,
): Promise<void> {
  await apiResponse(await fetch(
    `/api/session/${sessionId}/submit-vote`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        voter_id: voterId,
        group_index: groupIndex,
        answer_owner_id: answerOwnerId,
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

export async function startRoundTimer(
  sessionId: string,
  durationSeconds: number,
  currentRound: number,
): Promise<void> {
  await apiResponse(
    await fetch(`/api/session/${sessionId}/start-timer`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Host-Token": sessionStorage.getItem("mezclar-host:" + sessionId) ?? "",
      },
      body: JSON.stringify({ duration_seconds: durationSeconds, current_round: currentRound }),
    }),
  );
}

export async function controlGame(
  sessionId: string, action: "pause" | "resume" | "skip" | "extend", currentRound: number,
): Promise<SessionResponse> {
  return apiResponse(await fetch(`/api/session/${sessionId}/control`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Host-Token": sessionStorage.getItem("mezclar-host:" + sessionId) ?? "",
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

// A player's current Keywords screen, for page load and refresh.
export async function getKeywordsState(code: string, playerId: string): Promise<KeywordsPlayerView> {
  return apiResponse(await fetch(
    `/api/session/${code}/keywords/state?player_id=${encodeURIComponent(playerId)}`,
  ));
}

// The three "I'm done with this screen" buttons all send just the player ID.
export async function keywordsAction(
  code: string,
  action: "ready" | "role-seen" | "word-said",
  playerId: string,
): Promise<KeywordsPlayerView> {
  return apiResponse(await fetch(`/api/session/${code}/keywords/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_id: playerId }),
  }));
}

// A suspect's name, or the faker's keyword guess; the same call for both.
export async function keywordsSubmit(code: string, playerId: string, text: string): Promise<KeywordsPlayerView> {
  return apiResponse(await fetch(`/api/session/${code}/keywords/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_id: playerId, text }),
  }));
}

// Every group's full state, keywords and fakers included. Needs the host token.
export async function getKeywordsHostState(code: string): Promise<KeywordsHostView> {
  return apiResponse(await fetch(`/api/session/${code}/keywords/host-state`, {
    headers: { "X-Host-Token": sessionStorage.getItem("mezclar-host:" + code) ?? "" },
  }));
}
