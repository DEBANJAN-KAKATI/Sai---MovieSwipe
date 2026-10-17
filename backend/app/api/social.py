"""Friends, compatibility, recommendations, activity and collaborative lists."""

from __future__ import annotations

import datetime as dt
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    POSITIVE_ACTIONS,
    CollabList,
    Friendship,
    ListItem,
    ListMember,
    Recommendation,
    User,
    UserMediaAction,
    utcnow,
)
from ..schemas import (
    CollabListIn,
    CollabListPatchIn,
    FriendRequestIn,
    JoinIn,
    ListItemIn,
    RecommendIn,
    RecommendRespondIn,
)
from ..security import get_current_user, random_code
from ..services.actions import apply_action
from ..services.catalog import get_media, media_card
from ..services.social import are_friends, compatibility, friend_ids, positive_set, shares_activity
from ..services.users import PERSONAS, befriend, ensure_persona, public_user

router = APIRouter(tags=["social"])


def _iso(d: dt.datetime | None) -> str | None:
    return d.isoformat() + "Z" if d else None


# ---------------------------------------------------------------- friends


@router.get("/friends")
def friends(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Friendship).where(or_(Friendship.requester_id == user.id, Friendship.addressee_id == user.id))
    ).all()
    other_ids = {r.addressee_id if r.requester_id == user.id else r.requester_id for r in rows}
    others = {u.id: u for u in db.scalars(select(User).where(User.id.in_(other_ids))).all()} if other_ids else {}
    accepted, incoming, outgoing = [], [], []
    for r in rows:
        oid = r.addressee_id if r.requester_id == user.id else r.requester_id
        other = others.get(oid)
        if other is None:
            continue
        entry = {**public_user(other), "friendship_id": r.id, "since": _iso(r.created_at)}
        if r.status == "accepted":
            compat = compatibility(db, user, other)
            entry["compatibility"] = compat["percent"]
            entry["shared_count"] = compat["shared_count"]
            entry["shared_genres"] = compat["shared_genres"]
            entry["tagline"] = (other.preferences or {}).get("tagline")
            accepted.append(entry)
        elif r.status == "pending":
            (outgoing if r.requester_id == user.id else incoming).append(entry)
    accepted.sort(key=lambda e: -e["compatibility"])
    return {"friends": accepted, "incoming": incoming, "outgoing": outgoing, "your_code": user.friend_code}


@router.post("/friends/request")
def request_friend(body: FriendRequestIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = None
    if body.friend_code:
        target = db.scalar(select(User).where(User.friend_code == body.friend_code.strip().upper()))
    elif body.username:
        target = db.scalar(select(User).where(User.username == body.username.strip().lower()))
    if target is None:
        raise HTTPException(404, "No one found with that code")
    if target.id == user.id:
        raise HTTPException(400, "That's your own code 🙂")
    existing = db.scalar(
        select(Friendship).where(
            or_(
                and_(Friendship.requester_id == user.id, Friendship.addressee_id == target.id),
                and_(Friendship.requester_id == target.id, Friendship.addressee_id == user.id),
            )
        )
    )
    if existing:
        if existing.status == "blocked":
            raise HTTPException(403, "Can't send a request to this user")
        if existing.status == "pending" and existing.addressee_id == user.id:
            existing.status = "accepted"  # they already asked you — accept
            db.commit()
        return {"status": existing.status, "friend": public_user(target)}
    # Demo personas accept instantly.
    f = Friendship(requester_id=user.id, addressee_id=target.id, status="accepted" if target.is_bot else "pending")
    db.add(f)
    db.commit()
    return {"status": f.status, "friend": public_user(target)}


def _friendship_for(db: Session, fid: str, user: User) -> Friendship:
    f = db.get(Friendship, fid)
    if f is None or user.id not in (f.requester_id, f.addressee_id):
        raise HTTPException(404, "Request not found")
    return f


@router.post("/friends/{friendship_id}/accept")
def accept(friendship_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = _friendship_for(db, friendship_id, user)
    if f.addressee_id != user.id:
        raise HTTPException(403, "Only the recipient can accept")
    f.status = "accepted"
    db.commit()
    return {"status": "accepted"}


@router.post("/friends/{friendship_id}/decline")
def decline(friendship_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = _friendship_for(db, friendship_id, user)
    db.delete(f)
    db.commit()
    return {"status": "removed"}


@router.post("/friends/{friendship_id}/block")
def block(friendship_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    f = _friendship_for(db, friendship_id, user)
    other = f.addressee_id if f.requester_id == user.id else f.requester_id
    f.requester_id, f.addressee_id, f.status = user.id, other, "blocked"
    db.commit()
    return {"status": "blocked"}


@router.post("/friends/demo")
def demo_friends(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Add the demo personas (Aanya, Rohan, Meera) as friends so social features can be explored solo."""
    added = []
    for spec in PERSONAS:
        bot = ensure_persona(db, spec)
        befriend(db, user, bot)
        added.append(public_user(bot))
    db.commit()
    return {"added": added}


@router.get("/friends/{friend_id}/compare")
def compare(friend_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    other = db.get(User, friend_id)
    if other is None or not are_friends(db, user.id, friend_id):
        raise HTTPException(404, "Not a friend")
    compat = compatibility(db, user, other)
    shared = [media_card(m) for m in (get_media(db, i) for i in compat["shared_ids"][:12]) if m]
    picks = []
    if shares_activity(other):
        mine = set(db.scalars(select(UserMediaAction.media_id).where(UserMediaAction.user_id == user.id)).all())
        for mid in positive_set(db, other.id) - mine:
            m = get_media(db, mid)
            if m:
                picks.append(media_card(m))
        picks.sort(key=lambda c: -(c.get("vote_average") or 0))
    g = {k: v for k, v in (other.taste or {}).get("genres", {}).items() if v > 0}
    return {
        "friend": {**public_user(other), "tagline": (other.preferences or {}).get("tagline")},
        "compatibility": compat["percent"],
        "shared_genres": compat["shared_genres"],
        "shared": shared,
        "their_top_genres": [k for k, _ in sorted(g.items(), key=lambda kv: -kv[1])[:5]],
        "you_havent_seen": picks[:12],
    }


# ---------------------------------------------------------------- recommendations


@router.post("/recommendations/send")
def send_recommendation(body: RecommendIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not are_friends(db, user.id, body.to_user_id):
        raise HTTPException(403, "You can only recommend to friends")
    if get_media(db, body.media_id) is None:
        raise HTTPException(404, "Unknown title")
    rec = Recommendation(from_user_id=user.id, to_user_id=body.to_user_id, media_id=body.media_id,
                         message=body.message.strip())
    db.add(rec)
    to = db.get(User, body.to_user_id)
    if to is not None and to.is_bot:  # demo personas respond instantly
        rec.seen_at = utcnow()
        rec.response = "watchlist"
        apply_action(db, to, body.media_id, "watchlist")
    db.commit()
    return {"ok": True, "recommendation_id": rec.id}


@router.get("/recommendations/inbox")
def inbox(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Recommendation).where(Recommendation.to_user_id == user.id).order_by(Recommendation.created_at.desc())
    ).all()
    senders = {u.id: u for u in db.scalars(select(User).where(User.id.in_({r.from_user_id for r in rows}))).all()}
    out = []
    for r in rows[:50]:
        m = get_media(db, r.media_id)
        if m is None or r.from_user_id not in senders:
            continue
        out.append(
            {
                "recommendation_id": r.id,
                "from": public_user(senders[r.from_user_id]),
                "media": media_card(m),
                "message": r.message,
                "response": r.response,
                "created_at": _iso(r.created_at),
                "seen": r.seen_at is not None,
            }
        )
    return {"items": out, "unseen": sum(1 for o in out if not o["seen"])}


@router.post("/recommendations/{rec_id}/respond")
def respond(rec_id: str, body: RecommendRespondIn, user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    rec = db.get(Recommendation, rec_id)
    if rec is None or rec.to_user_id != user.id:
        raise HTTPException(404, "Recommendation not found")
    rec.response = body.action
    rec.seen_at = rec.seen_at or utcnow()
    if body.action != "dismiss":
        apply_action(db, user, rec.media_id, body.action)
    db.commit()
    return {"ok": True}


@router.post("/recommendations/mark-seen")
def mark_seen(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for rec in db.scalars(
        select(Recommendation).where(Recommendation.to_user_id == user.id, Recommendation.seen_at.is_(None))
    ).all():
        rec.seen_at = utcnow()
    db.commit()
    return {"ok": True}


@router.post("/recommendations/demo-incoming")
def demo_incoming(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Have each demo friend recommend one title they love that you haven't acted on."""
    mine = set(db.scalars(select(UserMediaAction.media_id).where(UserMediaAction.user_id == user.id)).all())
    sent = 0
    for spec in PERSONAS:
        bot = db.scalar(select(User).where(User.username == spec["username"]))
        if bot is None or not are_friends(db, user.id, bot.id):
            continue
        for mid in positive_set(db, bot.id) - mine:
            db.add(Recommendation(from_user_id=bot.id, to_user_id=user.id, media_id=mid,
                                  message=f"You'd love this — trust me! — {bot.display_name}"))
            mine.add(mid)
            sent += 1
            break
    db.commit()
    return {"sent": sent}


# ---------------------------------------------------------------- activity


@router.get("/social/activity")
def activity(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Aggregated, privacy-safe: '3 friends added Dune this week'. Never exposes rejects."""
    ids = friend_ids(db, user.id)
    if not ids:
        return {"items": []}
    friends_map = {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids))).all()}
    allowed = [i for i, u in friends_map.items() if shares_activity(u)]
    since = utcnow() - dt.timedelta(days=7)
    rows = db.execute(
        select(UserMediaAction.media_id, UserMediaAction.user_id).where(
            UserMediaAction.user_id.in_(allowed),
            UserMediaAction.action.in_(POSITIVE_ACTIONS),
            UserMediaAction.updated_at >= since,
        )
    ).all()
    by_media: dict[str, list[str]] = {}
    for mid, uid in rows:
        by_media.setdefault(mid, []).append(friends_map[uid].display_name)
    counts = Counter({mid: len(names) for mid, names in by_media.items()})
    items = []
    for mid, n in counts.most_common(15):
        m = get_media(db, mid)
        if m is None:
            continue
        names = by_media[mid]
        label = names[0] if n == 1 else f"{names[0]} and {n - 1} other{'s' if n > 2 else ''}"
        items.append({"media": media_card(m), "count": n, "names": names[:3],
                      "text": f"{label} saved it this week"})
    return {"items": items}


# ---------------------------------------------------------------- collaborative lists


def _member_role(db: Session, list_id: str, user_id: str) -> str | None:
    return db.scalar(select(ListMember.role).where(ListMember.list_id == list_id, ListMember.user_id == user_id))


def _list_payload(db: Session, cl: CollabList, viewer: User | None, full: bool = True) -> dict:
    members = db.execute(
        select(User, ListMember.role).join(ListMember, ListMember.user_id == User.id).where(ListMember.list_id == cl.id)
    ).all()
    items = db.scalars(select(ListItem).where(ListItem.list_id == cl.id).order_by(ListItem.created_at.desc())).all()
    names = {u.id: u.display_name for u, _ in members}
    out = {
        "list_id": cl.id,
        "name": cl.name,
        "description": cl.description,
        "emoji": cl.emoji,
        "is_public": cl.is_public,
        "owner_id": cl.owner_id,
        "item_count": len(items),
        "members": [{**public_user(u), "role": role} for u, role in members],
        "created_at": _iso(cl.created_at),
        "preview_posters": [],
    }
    if viewer is not None:
        out["your_role"] = next((role for u, role in members if u.id == viewer.id), None)
        if out["your_role"] in ("owner", "editor"):
            out["invite_code"] = cl.invite_code
    cards = []
    for it in items:
        m = get_media(db, it.media_id)
        if m is None:
            continue
        cards.append({**media_card(m), "note": it.note, "added_by": names.get(it.added_by, "Someone"),
                      "added_at": _iso(it.created_at)})
    out["preview_posters"] = [{"title": c["title"], "poster_url": c["poster_url"], "genres": c["genres"]}
                              for c in cards[:4]]
    if full:
        out["items"] = cards
    return out


@router.get("/collab-lists")
def my_lists(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lists = db.scalars(
        select(CollabList)
        .join(ListMember, ListMember.list_id == CollabList.id)
        .where(ListMember.user_id == user.id)
        .order_by(CollabList.created_at.desc())
    ).all()
    return {"lists": [_list_payload(db, cl, user, full=False) for cl in lists]}


@router.post("/collab-lists")
def create_list(body: CollabListIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cl = CollabList(name=body.name.strip(), description=body.description.strip(), emoji=body.emoji,
                    owner_id=user.id, is_public=body.is_public, invite_code=f"L-{random_code(7)}")
    db.add(cl)
    db.flush()
    db.add(ListMember(list_id=cl.id, user_id=user.id, role="owner"))
    db.commit()
    return _list_payload(db, cl, user)


@router.post("/collab-lists/join")
def join_list(body: JoinIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cl = db.scalar(select(CollabList).where(CollabList.invite_code == body.code.strip().upper()))
    if cl is None:
        raise HTTPException(404, "No list with that code")
    if _member_role(db, cl.id, user.id) is None:
        db.add(ListMember(list_id=cl.id, user_id=user.id, role="editor"))
        db.commit()
    return _list_payload(db, cl, user)


@router.get("/collab-lists/{list_id}")
def get_list(list_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cl = db.get(CollabList, list_id)
    if cl is None or (_member_role(db, list_id, user.id) is None and not cl.is_public):
        raise HTTPException(404, "List not found")
    return _list_payload(db, cl, user)


@router.patch("/collab-lists/{list_id}")
def patch_list(list_id: str, body: CollabListPatchIn, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    cl = db.get(CollabList, list_id)
    if cl is None or _member_role(db, list_id, user.id) != "owner":
        raise HTTPException(403, "Only the owner can edit list settings")
    for field in ("name", "description", "emoji", "is_public"):
        value = getattr(body, field)
        if value is not None:
            setattr(cl, field, value)
    db.commit()
    return _list_payload(db, cl, user)


@router.delete("/collab-lists/{list_id}")
def delete_list(list_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cl = db.get(CollabList, list_id)
    if cl is None:
        raise HTTPException(404, "List not found")
    role = _member_role(db, list_id, user.id)
    if role == "owner":
        db.delete(cl)
    elif role:
        db.execute(delete(ListMember).where(ListMember.list_id == list_id, ListMember.user_id == user.id))
    else:
        raise HTTPException(404, "List not found")
    db.commit()
    return {"ok": True}


@router.post("/collab-lists/{list_id}/items")
def add_item(list_id: str, body: ListItemIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if _member_role(db, list_id, user.id) not in ("owner", "editor"):
        raise HTTPException(403, "You can't edit this list")
    if get_media(db, body.media_id) is None:
        raise HTTPException(404, "Unknown title")
    exists = db.scalar(select(ListItem).where(ListItem.list_id == list_id, ListItem.media_id == body.media_id))
    if exists is None:
        db.add(ListItem(list_id=list_id, media_id=body.media_id, added_by=user.id, note=body.note.strip()))
    elif body.note:
        exists.note = body.note.strip()
    db.commit()
    return _list_payload(db, db.get(CollabList, list_id), user)


@router.delete("/collab-lists/{list_id}/items/{media_id}")
def remove_item(list_id: str, media_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if _member_role(db, list_id, user.id) not in ("owner", "editor"):
        raise HTTPException(403, "You can't edit this list")
    db.execute(delete(ListItem).where(ListItem.list_id == list_id, ListItem.media_id == media_id))
    db.commit()
    return _list_payload(db, db.get(CollabList, list_id), user)


@router.get("/public/lists/{list_id}")
def public_list(list_id: str, db: Session = Depends(get_db)):
    """Read-only shareable view — no auth, public lists only."""
    cl = db.get(CollabList, list_id)
    if cl is None or not cl.is_public:
        raise HTTPException(404, "List not found")
    payload = _list_payload(db, cl, None)
    payload["members"] = [{"display_name": m["display_name"], "avatar": m["avatar"]} for m in payload["members"]]
    return payload
