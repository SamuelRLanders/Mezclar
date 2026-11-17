import { expect, test, type Page, type WebSocketRoute } from "@playwright/test";
import type { KeywordsPlayerView, SessionResponse } from "../../shared/types/messages";

declare global {
  interface Window {
    speechTest: {
      spoken: string[];
      cancelled: number;
      active: SpeechSynthesisUtterance | null;
      throwOnSpeak: boolean;
    };
  }
}

// Keep real rendering/navigation, replacing only the speech service and game server.
async function setup(page: Page, options = { enabled: true, unsupported: false, storageBlocked: false }) {
  await page.addInitScript((options) => {
    sessionStorage.setItem("mezclar-player:TEST", "p1");
    if (options.enabled && localStorage.getItem("mezclar-read-aloud") === null) {
      localStorage.setItem("mezclar-read-aloud", "true");
    }
    if (options.storageBlocked) {
      const originalGet = Storage.prototype.getItem;
      const originalSet = Storage.prototype.setItem;
      Storage.prototype.getItem = function (key) {
        if (key === "mezclar-read-aloud") throw new Error("Storage blocked");
        return originalGet.call(this, key);
      };
      Storage.prototype.setItem = function (key, value) {
        if (key === "mezclar-read-aloud") throw new Error("Storage blocked");
        originalSet.call(this, key, value);
      };
    }
    window.speechTest = { spoken: [], cancelled: 0, active: null, throwOnSpeak: false };
    Object.defineProperty(window, "SpeechSynthesisUtterance", {
      configurable: true,
      value: options.unsupported ? undefined : class {
        constructor(public text: string) {}
      },
    });
    Object.defineProperty(window, "speechSynthesis", {
      configurable: true,
      value: {
        speak(speech: SpeechSynthesisUtterance) {
          if (window.speechTest.throwOnSpeak) throw new Error("Speech service unavailable");
          window.speechTest.active = speech;
          window.speechTest.spoken.push(speech.text);
        },
        cancel() {
          window.speechTest.cancelled++;
          const active = window.speechTest.active;
          window.speechTest.active = null;
          active?.onerror?.call(active, { error: "canceled" } as SpeechSynthesisErrorEvent);
        },
      },
    });
  }, options);

  const players = [
    { player_id: "p1", name: "Alex", ready: false, hidden: false, is_mod: false },
    { player_id: "p2", name: "Sam", ready: false, hidden: false, is_mod: false },
  ];
  const session: SessionResponse = {
    session_id: "TEST", host_name: "Host", settings: { gameId: "quiplash" },
    player_count: 2, players, auto_generate_names: false, allow_late_join: true,
    requires_password: false, profanity_filter: false, game_started: true,
    game_id: "quiplash", minimum_players: 2, maximum_players: 8,
    current_round: 1, total_rounds: 3, current_prompt: "Name a terrible superpower.",
    answers: {}, groups: [{ group_index: 0, prompt: "Name a terrible superpower.", players, answers: {}, vote_counts: {} }],
    round_duration_seconds: null, round_deadline: null, game_paused: false,
    paused_remaining: null, phase: "answering", scores: {}, round_results: [],
    event_log: [], leaderboard: [], submitted_count: 0, eligible_count: 2, submitted_player_ids: [],
  };
  const keywords: KeywordsPlayerView = {
    phase: "gathering", group_index: 0, group_color: "Blue", group_label: "Blue",
    single_group: false, members: players, ready_player_ids: [], role_seen_player_ids: [],
    is_faker: false, keyword: "Pineapple", speaking_order: ["p1", "p2"],
    current_speaker_id: "p1", has_submitted: false, submitted_count: 0, result: null,
  };
  let socket: WebSocketRoute;
  await page.routeWebSocket("**/ws/session/**", (connection) => {
    socket = connection;
    connection.send(JSON.stringify({
      type: "connected", session_id: "TEST", player_id: "p1", name: "Alex",
      ready: false, game_id: session.game_id, players,
    }));
  });
  await page.route("**/api/session/TEST**", async (route) => {
    if (route.request().url().includes("submit-answer")) {
      session.submitted_player_ids = ["p1"];
      session.submitted_count = 1;
      session.groups[0].answers.p1 = route.request().postDataJSON().answer;
      await route.fulfill({ json: {} });
    } else {
      await route.fulfill({ json: route.request().url().includes("keywords") ? keywords : session });
    }
  });

  return {
    session, keywords,
    send: (message: object) => socket.send(JSON.stringify(message)),
    updateKeywords: () => socket.send(JSON.stringify({ type: "keywords_state", ...keywords })),
  };
}

const setting = (page: Page) => page.getByRole("checkbox", { name: "Enable read-aloud" });
const play = (page: Page) => page.getByRole("button", { name: "Play read-aloud" });
const stop = (page: Page) => page.getByRole("button", { name: "Stop read-aloud" });
const spoken = (page: Page) => page.evaluate(() => window.speechTest.spoken.at(-1));

test("read-aloud starts disabled and its controls work with the keyboard", async ({ page }) => {
  await setup(page, { enabled: false, unsupported: false, storageBlocked: false });
  await page.goto("/player/TEST/game");
  await expect(page.getByRole("heading", { name: "Name a terrible superpower." })).toBeVisible();
  await expect(setting(page)).not.toBeChecked();
  await expect(play(page)).toHaveCount(0);
  await setting(page).focus();
  await page.keyboard.press("Space");
  await play(page).focus();
  await page.keyboard.press("Enter");
  await expect(stop(page)).toBeEnabled();
  expect(await spoken(page)).toContain("Name a terrible superpower.");
  expect(await spoken(page)).toContain("Submit quip");
  await expect(play(page)).toBeDisabled();
  await stop(page).click();
  await expect(play(page)).toBeEnabled();
  await play(page).click();
  await setting(page).uncheck();
  expect(await page.evaluate(() => window.speechTest.active)).toBeNull();
  await expect(play(page)).toHaveCount(0);
  await expect(page.getByText("Read-aloud could not play.", { exact: false })).toHaveCount(0);
});

test("both enabled and disabled preferences survive refresh without autoplay", async ({ page }) => {
  await setup(page);
  await page.goto("/player/TEST/game");
  await expect(setting(page)).toBeChecked();
  await play(page).click();
  await page.reload();
  await expect(setting(page)).toBeChecked();
  expect(await page.evaluate(() => window.speechTest.spoken)).toEqual([]);
  await setting(page).uncheck();
  await page.reload();
  await expect(setting(page)).not.toBeChecked();
});

test("unsupported browsers show a clear message and keep the saved preference", async ({ page }) => {
  await setup(page, { enabled: true, unsupported: true, storageBlocked: false });
  await page.goto("/player/TEST/game");
  await expect(setting(page)).toBeChecked();
  await expect(page.getByText("Read-aloud is unavailable in this browser.", { exact: false })).toBeVisible();
  await expect(play(page)).toHaveCount(0);
});

test("blocked storage still allows playback and explains the persistence failure", async ({ page }) => {
  await setup(page, { enabled: false, unsupported: false, storageBlocked: true });
  await page.goto("/player/TEST/game");
  await setting(page).check();
  await expect(page.getByRole("status")).toContainText("could not save this setting");
  await play(page).click();
  await expect(stop(page)).toBeEnabled();
});

test("completion, speech errors, and service failures allow another playback", async ({ page }) => {
  await setup(page);
  await page.goto("/player/TEST/game");
  await play(page).click();
  await page.evaluate(() => {
    const speech = window.speechTest.active!;
    speech.onend!.call(speech, new Event("end") as SpeechSynthesisEvent);
  });
  await expect(play(page)).toBeEnabled();
  await play(page).click();
  await page.evaluate(() => {
    const speech = window.speechTest.active!;
    speech.onerror!.call(speech, { error: "synthesis-unavailable" } as SpeechSynthesisErrorEvent);
  });
  await expect(page.getByRole("status")).toContainText("Read-aloud could not play");
  await expect(play(page)).toBeEnabled();
  await page.evaluate(() => { window.speechTest.throwOnSpeak = true; });
  await play(page).click();
  await expect(page.getByRole("status")).toContainText("Read-aloud could not play");
  await expect(play(page)).toBeEnabled();
  await page.evaluate(() => { window.speechTest.throwOnSpeak = false; });
  await play(page).click();
  await expect(stop(page)).toBeEnabled();
});

test("leaving a player screen cancels speech", async ({ page }) => {
  await setup(page);
  await page.goto("/player/TEST/game");
  await play(page).click();
  await page.getByRole("link", { name: "Leave game" }).click();
  await expect(page).toHaveURL("/");
  expect(await page.evaluate(() => window.speechTest.active)).toBeNull();
  expect(await page.evaluate(() => window.speechTest.cancelled)).toBe(1);
});

test("pagehide cancels speech before browser navigation or refresh", async ({ page }) => {
  await setup(page);
  await page.goto("/player/TEST/game");
  await play(page).click();
  await page.evaluate(() => window.dispatchEvent(new Event("pagehide")));
  await expect(stop(page)).toBeDisabled();
  expect(await page.evaluate(() => window.speechTest.active)).toBeNull();
});

test("new prompts replace spoken content and cancel the previous prompt", async ({ page }) => {
  const game = await setup(page);
  await page.goto("/player/TEST/game");
  await play(page).click();
  game.send({ type: "player_prompt", current_round: 1, current_prompt: "Name a strange pet." });
  await expect(page.getByRole("heading", { name: "Name a strange pet." })).toBeVisible();
  await expect(stop(page)).toBeDisabled();
  await play(page).click();
  expect(await spoken(page)).toContain("Name a strange pet.");
  expect(await spoken(page)).not.toContain("terrible superpower");
});

test("the countdown leaves playback running; pause and expiry update instructions", async ({ page }) => {
  const game = await setup(page);
  game.session.round_deadline = new Date(Date.now() + 60_000).toISOString();
  await page.goto("/player/TEST/game");
  const timer = page.getByRole("timer");
  await expect(timer).toBeVisible();
  const initialTime = await timer.textContent();
  await play(page).click();
  await expect.poll(() => timer.textContent()).not.toBe(initialTime);
  await expect(stop(page)).toBeEnabled();
  expect(await page.evaluate(() => window.speechTest.cancelled)).toBe(0);
  game.session.game_paused = true;
  game.session.paused_remaining = 40;
  game.send({ type: "round_updated" });
  await expect(page.getByText("Paused", { exact: true })).toBeVisible();
  await expect(stop(page)).toBeDisabled();
  await play(page).click();
  expect(await spoken(page)).toContain("paused");
  game.session.game_paused = false;
  game.session.round_deadline = new Date(Date.now() - 1000).toISOString();
  game.send({ type: "round_updated" });
  await expect(timer).toContainText("0s");
  await expect(stop(page)).toBeDisabled();
  await play(page).click();
  expect(await spoken(page)).toContain("Time is up");
});

test("submission changes instructions, preserves the response, and survives refresh", async ({ page }) => {
  const game = await setup(page);
  await page.goto("/player/TEST/game");
  await play(page).click();
  await page.getByRole("textbox", { name: "Your quip" }).fill("Invisible only when nobody looks");
  await expect(stop(page)).toBeEnabled();
  expect(await spoken(page)).not.toContain("Invisible");
  await page.getByRole("button", { name: "Submit quip" }).click();
  await expect(page.getByText("Response received", { exact: true })).toBeVisible();
  await expect(stop(page)).toBeDisabled();
  await play(page).click();
  expect(await spoken(page)).toContain("Response received");
  expect(game.session.submitted_count).toBe(1);
  expect(game.session.groups[0].answers.p1).toBe("Invisible only when nobody looks");
  await page.reload();
  await expect(page.getByRole("textbox", { name: "Your quip" })).toHaveValue("Invisible only when nobody looks");
  await play(page).click();
  expect(await spoken(page)).toContain("Response received");
});

test("voting, the next round, and finishing stop obsolete speech", async ({ page }) => {
  const game = await setup(page);
  await page.goto("/player/TEST/game");
  await play(page).click();
  game.session.phase = "voting";
  game.send({ type: "voting_started", current_round: 1, groups: [{
    group_index: 0, prompt: "Name a terrible superpower.",
    answers: [{ player_id: "p1", answer: "Invisibility" }, { player_id: "p2", answer: "Flying backwards" }],
  }] });
  await expect(page.getByRole("heading", { name: "Pick your favorite." })).toBeVisible();
  await expect(stop(page)).toBeDisabled();
  await play(page).click();
  expect(await spoken(page)).toContain("Option A: Invisibility");
  expect(await spoken(page)).toContain("Option B: Flying backwards");
  await page.getByRole("button", { name: "A Invisibility" }).click();
  await page.getByRole("button", { name: "Lock in my votes" }).click();
  await expect(stop(page)).toBeDisabled();
  await play(page).click();
  expect(await spoken(page)).toContain("Votes locked in");
  game.session.phase = "answering";
  game.session.current_round = 2;
  game.send({ type: "round_updated" });
  await expect(page.getByRole("heading", { name: "Make it memorable." })).toBeVisible();
  await expect(stop(page)).toBeDisabled();
  await play(page).click();
  expect(await spoken(page)).toContain("Round 2");
  game.session.phase = "finished";
  game.send({ type: "game_finished" });
  await expect(page.getByRole("heading", { name: "Game over!" })).toBeVisible();
  await expect(stop(page)).toBeDisabled();
  await play(page).click();
  expect(await spoken(page)).toContain("Game over");
});

test("the lobby setting carries into the game and stops lobby speech", async ({ page }) => {
  const game = await setup(page);
  await page.goto("/player/TEST");
  await expect(page.getByText("Connection: Connected")).toBeVisible();
  await play(page).click();
  expect(await spoken(page)).toContain("lobby");
  game.send({ type: "game_started", game_id: "quiplash" });
  await expect(page).toHaveURL("/player/TEST/game");
  await expect(setting(page)).toBeChecked();
  await expect(stop(page)).toBeDisabled();
  expect(await page.evaluate(() => window.speechTest.active)).toBeNull();
});

test("late joiners can read the waiting instructions", async ({ page }) => {
  await setup(page);
  await page.goto("/player/TEST/in-session");
  await play(page).click();
  expect(await spoken(page)).toContain("wait to join a round");
});

test("Keywords keeps covered roles private and updates after revealing", async ({ page }) => {
  const game = await setup(page);
  game.keywords.phase = "roles";
  await page.goto("/player/TEST/keywords");
  await expect(page.getByRole("heading", { name: "Keep it secret" })).toBeVisible();
  await play(page).click();
  expect(await spoken(page)).not.toContain("Pineapple");
  await page.getByRole("button", { name: "Tap to see your role" }).click();
  await expect(stop(page)).toBeDisabled();
  await play(page).click();
  expect(await spoken(page)).toContain("The keyword is Pineapple");
  game.keywords.phase = "speaking";
  game.updateKeywords();
  await expect(page.getByRole("heading", { name: "Your turn!" })).toBeVisible();
  await expect(stop(page)).toBeDisabled();
});

test("Keywords follows grouping, speaker changes, voting, submission, and results", async ({ page }) => {
  const game = await setup(page);
  await page.goto("/player/TEST/keywords");
  await expect(page.getByRole("heading", { name: "Blue Group" })).toBeVisible();
  await play(page).click();
  expect(await spoken(page)).toContain("Find your group: Sam");
  game.keywords.phase = "speaking";
  game.updateKeywords();
  await expect(page.getByRole("heading", { name: "Your turn!" })).toBeVisible();
  await play(page).click();
  expect(await spoken(page)).toContain("Your turn!");
  game.keywords.current_speaker_id = "p2";
  game.updateKeywords();
  await expect(page.getByRole("heading", { name: "Listen to Sam" })).toBeVisible();
  await expect(stop(page)).toBeDisabled();
  await play(page).click();
  expect(await spoken(page)).toContain("Listen to Sam");
  game.keywords.phase = "voting";
  game.keywords.is_faker = true;
  game.keywords.keyword = null;
  game.updateKeywords();
  await expect(page.getByRole("heading", { name: "Guess the keyword" })).toBeVisible();
  await play(page).click();
  expect(await spoken(page)).toContain("Guess the keyword");
  expect(await spoken(page)).not.toContain("Pineapple");
  game.keywords.has_submitted = true;
  game.updateKeywords();
  await expect(page.getByRole("heading", { name: "Answer locked in" })).toBeVisible();
  await expect(stop(page)).toBeDisabled();
  await play(page).click();
  expect(await spoken(page)).toContain("Waiting for the rest");
  game.keywords.phase = "reveal";
  game.keywords.result = {
    winner: "players", faker_id: "p1", faker_name: "Alex", keyword: "Pineapple",
    faker_guess: "Apple", faker_caught: true, faker_guessed_keyword: false, vote_counts: { p1: 1 },
  };
  game.updateKeywords();
  await expect(page.getByRole("heading", { name: "Players win!" })).toBeVisible();
  await expect(stop(page)).toBeDisabled();
  await play(page).click();
  expect(await spoken(page)).toContain("The keyword was Pineapple");
});

test("read-aloud controls fit a phone screen", async ({ page }, testInfo) => {
  await setup(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/player/TEST/game");
  await expect(play(page)).toBeVisible();
  await expect(stop(page)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.screenshot({ path: testInfo.outputPath("read-aloud-mobile.png"), fullPage: true });
});
