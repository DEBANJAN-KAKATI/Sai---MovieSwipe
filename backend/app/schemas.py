"""Request bodies. Responses are plain dicts built by the serializers in services/."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

# "watched" = already seen: a positive taste signal that goes to History, never to the Watch List.
SwipeAction = Literal[
    "watchlist", "rejected", "undecided", "must_visit", "liked", "watched", "watch_intent", "impression_detail"
]
ListAction = Literal["watchlist", "must_visit", "undecided", "rejected", "liked", "watched", "remove"]


class GuestIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=40)


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    email: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, max_length=40)


class LoginIn(BaseModel):
    login: str = Field(max_length=255)
    password: str = Field(max_length=128)


class SwipeIn(BaseModel):
    media_id: str
    action: SwipeAction
    idempotency_key: str | None = Field(default=None, max_length=64)
    session_id: str | None = None


class ListPatchIn(BaseModel):
    action: ListAction
    rating: int | None = Field(default=None, ge=1, le=5)


class OnboardingIn(BaseModel):
    liked_ids: list[str] = Field(default_factory=list, max_length=50)
    display_name: str | None = Field(default=None, max_length=40)
    subscriptions: list[str] | None = None
    languages: list[str] | None = None
    content_filters: dict | None = None


class ProfilePatchIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=40)
    avatar: str | None = Field(default=None, max_length=16)
    region: str | None = Field(default=None, min_length=2, max_length=2)
    subscription_providers: list[str] | None = None
    content_filters: dict | None = None
    preferences: dict | None = None
    privacy_settings: dict | None = None


class SessionCreateIn(BaseModel):
    mode: Literal["duo", "group"] = "duo"
    min_votes: int | None = Field(default=None, ge=2, le=20)
    mood: str | None = None
    type: Literal["all", "movie", "tv"] = "all"
    max_runtime: int | None = Field(default=None, ge=20, le=400)


class JoinIn(BaseModel):
    code: str = Field(min_length=4, max_length=12)


class FriendRequestIn(BaseModel):
    friend_code: str | None = Field(default=None, max_length=16)
    username: str | None = Field(default=None, max_length=40)


class RecommendIn(BaseModel):
    to_user_id: str
    media_id: str
    message: str = Field(default="", max_length=300)


class RecommendRespondIn(BaseModel):
    action: Literal["watchlist", "must_visit", "dismiss"]


class CollabListIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    emoji: str = Field(default="🎬", max_length=8)
    is_public: bool = False


class CollabListPatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    emoji: str | None = Field(default=None, max_length=8)
    is_public: bool | None = None


class ListItemIn(BaseModel):
    media_id: str
    note: str = Field(default="", max_length=300)


class PartyIn(BaseModel):
    media_id: str
    starts_at: dt.datetime
    notes: str = Field(default="", max_length=500)
    session_id: str | None = None


class RSVPIn(BaseModel):
    status: Literal["going", "maybe", "no"]
