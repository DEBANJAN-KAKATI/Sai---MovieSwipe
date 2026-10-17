"""SQLAlchemy models. Timestamps are stored as naive UTC."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def uid() -> str:
    return uuid.uuid4().hex


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


# List-state actions stored in user_media_actions (latest action wins).
LIST_ACTIONS = ("watchlist", "must_visit", "undecided", "rejected", "liked", "watched")
POSITIVE_ACTIONS = ("watchlist", "must_visit", "liked")
# Logged-only actions: recorded as events, never change list state.
LOG_ACTIONS = ("watch_intent", "impression_detail")


# ---------------------------------------------------------------- catalog


class MediaItem(Base):
    __tablename__ = "media_items"
    __table_args__ = (UniqueConstraint("tmdb_id", "type", name="uq_media_tmdb"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, index=True)
    type: Mapped[str] = mapped_column(String(8))  # movie | tv
    title: Mapped[str] = mapped_column(String(300), index=True)
    original_title: Mapped[str | None] = mapped_column(String(300))
    overview: Mapped[str] = mapped_column(Text, default="")
    tagline: Mapped[str | None] = mapped_column(String(500))
    release_date: Mapped[dt.date | None] = mapped_column(Date)
    year: Mapped[int | None] = mapped_column(Integer)
    genres: Mapped[list] = mapped_column(JSON, default=list)
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    cast: Mapped[list] = mapped_column(JSON, default=list)
    creator: Mapped[str | None] = mapped_column(String(300))
    runtime_minutes: Mapped[int | None] = mapped_column(Integer)  # movie runtime or TV episode runtime
    season_count: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(8), default="en")
    certification: Mapped[str | None] = mapped_column(String(8))  # U | UA | A
    content_flags: Mapped[list] = mapped_column(JSON, default=list)
    poster_url: Mapped[str | None] = mapped_column(String(500))
    backdrop_url: Mapped[str | None] = mapped_column(String(500))
    logo_url: Mapped[str | None] = mapped_column(String(500))  # wide wordmark, shown on a plate when no poster
    image_source: Mapped[str | None] = mapped_column(String(500))  # attribution page for the artwork
    trailer_key: Mapped[str | None] = mapped_column(String(64))
    popularity: Mapped[float] = mapped_column(Float, default=0.0)
    vote_average: Mapped[float | None] = mapped_column(Float)
    providers_in: Mapped[list] = mapped_column(JSON, default=list)
    providers_checked_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    embedding: Mapped[list | None] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(16), default="seed")
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


# ---------------------------------------------------------------- users & taste


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    is_guest: Mapped[bool] = mapped_column(Boolean, default=True)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    region: Mapped[str] = mapped_column(String(2), default="IN")
    avatar: Mapped[str] = mapped_column(String(16), default="🍿")
    subscription_providers: Mapped[list] = mapped_column(JSON, default=list)
    privacy_settings: Mapped[dict] = mapped_column(JSON, default=dict)
    content_filters: Mapped[dict] = mapped_column(JSON, default=dict)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    taste: Mapped[dict] = mapped_column(JSON, default=dict)
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    friend_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    last_active_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class UserMediaAction(Base):
    """Current list state of a title for a user (latest action wins)."""

    __tablename__ = "user_media_actions"
    __table_args__ = (UniqueConstraint("user_id", "media_id", name="uq_user_media"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    media_id: Mapped[str] = mapped_column(ForeignKey("media_items.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(16))
    rating: Mapped[int | None] = mapped_column(Integer)
    session_id: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class SwipeEvent(Base):
    """Append-only swipe history: powers undo, streaks, idempotency and metrics."""

    __tablename__ = "swipe_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    media_id: Mapped[str] = mapped_column(ForeignKey("media_items.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(24))
    prev_action: Mapped[str | None] = mapped_column(String(16))
    prev_rating: Mapped[int | None] = mapped_column(Integer)
    prev_updated_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    session_id: Mapped[str | None] = mapped_column(String(32))
    undone: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)


class FeedImpression(Base):
    __tablename__ = "feed_impressions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    media_id: Mapped[str] = mapped_column(ForeignKey("media_items.id", ondelete="CASCADE"))
    rank: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(16))
    shown_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


# ---------------------------------------------------------------- relational


class Friendship(Base):
    __tablename__ = "friendships"
    __table_args__ = (UniqueConstraint("requester_id", "addressee_id", name="uq_friend_pair"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    requester_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    addressee_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending | accepted | blocked
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class CollabList(Base):
    __tablename__ = "collaborative_lists"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500), default="")
    emoji: Mapped[str] = mapped_column(String(8), default="🎬")
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    invite_code: Mapped[str] = mapped_column(String(16), unique=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class ListMember(Base):
    __tablename__ = "list_members"
    __table_args__ = (UniqueConstraint("list_id", "user_id", name="uq_list_member"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    list_id: Mapped[str] = mapped_column(ForeignKey("collaborative_lists.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10), default="editor")  # owner | editor | viewer
    joined_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class ListItem(Base):
    __tablename__ = "list_items"
    __table_args__ = (UniqueConstraint("list_id", "media_id", name="uq_list_item"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    list_id: Mapped[str] = mapped_column(ForeignKey("collaborative_lists.id", ondelete="CASCADE"), index=True)
    media_id: Mapped[str] = mapped_column(ForeignKey("media_items.id", ondelete="CASCADE"))
    added_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    note: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class SwipeSession(Base):
    """Duo / group swipe session."""

    __tablename__ = "swipe_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    host_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    mode: Mapped[str] = mapped_column(String(8))  # duo | group
    min_votes: Mapped[int | None] = mapped_column(Integer)  # None = unanimous
    status: Mapped[str] = mapped_column(String(10), default="open")
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    stack: Mapped[list] = mapped_column(JSON, default=list)
    feed_seed: Mapped[str] = mapped_column(String(32), default=uid)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class SessionMember(Base):
    __tablename__ = "session_members"
    __table_args__ = (UniqueConstraint("session_id", "user_id", name="uq_session_member"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("swipe_sessions.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    joined_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class SessionSwipe(Base):
    __tablename__ = "session_swipes"
    __table_args__ = (UniqueConstraint("session_id", "user_id", "media_id", name="uq_session_swipe"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("swipe_sessions.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    media_id: Mapped[str] = mapped_column(ForeignKey("media_items.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("session_id", "media_id", name="uq_match"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    session_id: Mapped[str] = mapped_column(ForeignKey("swipe_sessions.id", ondelete="CASCADE"), index=True)
    media_id: Mapped[str] = mapped_column(ForeignKey("media_items.id", ondelete="CASCADE"))
    participants: Mapped[list] = mapped_column(JSON, default=list)
    super_match: Mapped[bool] = mapped_column(Boolean, default=False)
    matched_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class Recommendation(Base):
    __tablename__ = "recommendations_to_user"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    from_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    to_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    media_id: Mapped[str] = mapped_column(ForeignKey("media_items.id", ondelete="CASCADE"))
    message: Mapped[str] = mapped_column(String(300), default="")
    response: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    seen_at: Mapped[dt.datetime | None] = mapped_column(DateTime)


class WatchParty(Base):
    __tablename__ = "watch_parties"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    host_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    media_id: Mapped[str] = mapped_column(ForeignKey("media_items.id", ondelete="CASCADE"))
    starts_at: Mapped[dt.datetime] = mapped_column(DateTime)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=120)
    notes: Mapped[str] = mapped_column(String(500), default="")
    invite_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class PartyRSVP(Base):
    __tablename__ = "party_rsvps"
    __table_args__ = (UniqueConstraint("party_id", "user_id", name="uq_rsvp"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    party_id: Mapped[str] = mapped_column(ForeignKey("watch_parties.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(8), default="going")  # going | maybe | no
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


Index("ix_events_user_created", SwipeEvent.user_id, SwipeEvent.created_at)
