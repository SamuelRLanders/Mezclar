# Mezclar

Mezclar is a web-based platform for large-group social games, built for rooms of 30 to 500+ people at once. Think of the energy of a party game night, but designed to actually scale to a packed room instead of just a handful of friends on a couch.

It's meant to be the replacement for the icebreaker — the thing a club, org, class, or professional meeting reaches for instead of "go around the room and say your name and a fun fact." Mezclar gives groups a genuinely fun, structured way to get people talking to each other instead.

Players join instantly by entering a short game code — no app download, no account creation, no friction. A host runs the show while everyone's phone becomes their personal controller.

The core idea is simple: most party games either turn into a passive scrolling session or default to trivia. Mezclar is built to do the opposite. The games are designed to pull people out of their phones and into the room — sparking real conversation, persuasion, negotiation, prediction, teamwork, and social deduction between actual humans standing near each other. The phone is just the input device; the real game happens face to face.

Mezclar is meant to support a variety of game types under one platform, let people jump in even after a round has started, and keep things running smoothly in real time no matter how large the crowd gets.

## Status

Early development — the real-time lobby and core multiplayer infrastructure are underway.


## Running project
- Frontend
  - cd into frontend-web and do "npm run dev"
- Backend
  - Run ".\backend\\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000"
- Tests
  - Run ".\backend\\.venv\Scripts\python.exe -m pytest backend/tests -q"
