from pydantic import BaseModel, ConfigDict, Field, JsonValue, StrictBool, model_validator
from datetime import datetime

class GenerateNameResponse(BaseModel):
    name: str

class RegenerateNameRequest(BaseModel):
    player_id: str

class ToggleAutoNamesRequest(BaseModel):
    enabled: bool

class ToggleProfanityFilterRequest(BaseModel):
    enabled: bool

class JoinSessionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    player_id: str = Field(min_length=1)
    name: str | None = Field(default=None, min_length=1)

class JoinSessionResponse(BaseModel):
    player_id: str
    name: str
    session_id: str
    ready: bool
    hidden: bool
    game_started: bool

class SessionPlayerResponse(BaseModel):
    player_id: str
    name: str
    ready: bool
    hidden: bool
    is_mod: bool

class SessionGroupResponse(BaseModel):
    group_index: int
    prompt: str
    players: list[SessionPlayerResponse]
    answers: dict[str, str]
    vote_counts: dict[str, int] = Field(default_factory=dict)

class SessionResponse(BaseModel):
    session_id: str
    player_count: int
    players: list[SessionPlayerResponse]
    game_started: bool
    host_name: str
    settings: dict[str, JsonValue]
    auto_generate_names: bool
    profanity_filter: bool
    requires_password: bool
    allow_late_join: bool
    game_id: str | None
    minimum_players: int | None
    maximum_players: int | None
    current_round: int
    current_prompt: str | None
    answers: dict[str, str]
    groups: list[SessionGroupResponse] = Field(default_factory=list)
    round_duration_seconds: int | None
    round_deadline: datetime | None
    phase: str

class StartGameRequest(BaseModel):
    game_id: str
    minimum_players: int
    maximum_players: int

class SubmitNameRequest(BaseModel):
    player_id: str
    requested_name: str

class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    host_name: str = Field(default="Host", min_length=1)
    settings: dict[str, JsonValue] = Field(default_factory=dict)
    password: str | None = Field(default=None, min_length=1)

    
    @model_validator(mode="after")
    def validate_rounds(self):
        rounds = self.settings.get("rounds", 3)

        if isinstance(rounds, bool) or not isinstance(rounds, int):
            raise ValueError("Rounds must be an integer between 1 and 5.")

        if not 1 <= rounds <= 5:
            raise ValueError("Rounds must be between 1 and 5.")

        self.settings["rounds"] = rounds
        return self


class UpdateReadyStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ready: StrictBool

class KickPlayerRequest(BaseModel):
    player_id: str

class HidePlayerRequest(BaseModel):
    player_id: str
    hidden: bool

class ModPlayerRequest(BaseModel):
    player_id: str
    is_mod: bool


class SubmitAnswerRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    player_id: str = Field(min_length=1)
    answer: str = Field(min_length=1, max_length=200)

class StartRoundTimerRequest(BaseModel):
    duration_seconds: int

class SubmitVoteRequest(BaseModel):
    voter_id: str
    answer_owner_id: str