import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BrandLogo } from "../components/BrandLogo";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { shareOrigin } from "../api/base";
import { copyText } from "../lib/clipboard";
import { api } from "../api/client";
import type { Media } from "../api/types";
import { SearchSheet } from "../components/Extras";
import { Icon } from "../components/Icon";
import { InfoPanel } from "../components/InfoPanel";
import { Poster } from "../components/Poster";
import { Sheet } from "../components/Sheet";
import { toast } from "../store";

function MiniRow({ items, onOpen }: { items: Media[]; onOpen: (id: string) => void }) {
  return (
    <div className="scroller">
      {items.map((m) => (
        <button key={m.media_id} className="mini-card" onClick={() => onOpen(m.media_id)}>
          <div className="mini-poster">
            <Poster media={m} fontSize={8} />
          </div>
          <div className="t">{m.title}</div>
        </button>
      ))}
    </div>
  );
}

export function Social() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const friends = useQuery({ queryKey: ["friends"], queryFn: api.friends });
  const inbox = useQuery({ queryKey: ["inbox"], queryFn: api.inbox });
  const activity = useQuery({ queryKey: ["activity"], queryFn: api.activity });
  const lists = useQuery({ queryKey: ["collab-lists"], queryFn: api.collabLists });
  const parties = useQuery({ queryKey: ["parties"], queryFn: api.parties });
  const [code, setCode] = useState("");
  const [info, setInfo] = useState<string | null>(null);
  const [sheet, setSheet] = useState<null | "newList" | "joinList">(null);
  const [listName, setListName] = useState("");
  const [listCode, setListCode] = useState("");

  const refresh = () => {
    for (const k of ["friends", "inbox", "activity", "collab-lists", "parties"]) qc.invalidateQueries({ queryKey: [k] });
  };

  useEffect(() => {
    if (inbox.data && inbox.data.unseen > 0) {
      const t = setTimeout(() => api.markRecsSeen().then(() => qc.invalidateQueries({ queryKey: ["inbox"] })), 2500);
      return () => clearTimeout(t);
    }
  }, [inbox.data, qc]);

  const add = useMutation({
    mutationFn: () => api.requestFriend(code.trim()),
    onSuccess: (r) => {
      toast(r.status === "accepted" ? `You're now friends with ${r.friend.display_name}` : `Request sent to ${r.friend.display_name}`);
      setCode("");
      refresh();
    },
    onError: (e: Error) => toast(e.message),
  });
  const demo = useMutation({
    mutationFn: async () => {
      await api.demoFriends();
      await api.demoIncoming();
    },
    onSuccess: () => {
      toast("Say hi to Aanya, Rohan & Meera 👋");
      refresh();
    },
  });
  const respond = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "watchlist" | "must_visit" | "dismiss" }) => api.respondRec(id, action),
    onSuccess: (_d, v) => {
      toast(v.action === "dismiss" ? "Dismissed" : "Added to your list");
      refresh();
      qc.invalidateQueries({ queryKey: ["lists"] });
    },
  });
  const newList = useMutation({
    mutationFn: () => api.createCollabList({ name: listName.trim() || "Our picks" }),
    onSuccess: (l) => navigate(`/shared/${l.list_id}`),
  });
  const joinList = useMutation({
    mutationFn: () => api.joinCollabList(listCode.trim()),
    onSuccess: (l) => navigate(`/shared/${l.list_id}`),
    onError: (e: Error) => toast(e.message),
  });

  const f = friends.data;
  const pendingRecs = inbox.data?.items.filter((r) => !r.response) ?? [];

  return (
    <div className="page narrow">
      <div className="page-header">
        <h1 className="h1">Social</h1>
      </div>

      <div className="panel stack">
        <div className="row between">
          <div>
            <div className="small muted">Your friend code</div>
            <div style={{ fontWeight: 800, fontSize: 20, letterSpacing: "0.08em" }}>{f?.your_code ?? "…"}</div>
          </div>
          <button
            className="btn sm"
            onClick={() => {
              copyText(f?.your_code ?? "");
              toast("Code copied");
            }}
          >
            <Icon name="copy" size={15} /> Copy
          </button>
        </div>
        <form
          className="row"
          onSubmit={(e) => {
            e.preventDefault();
            if (code.trim()) add.mutate();
          }}
        >
          <input className="input" placeholder="Friend's code, e.g. MS-ABC234" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} />
          <button className="btn primary" disabled={!code.trim() || add.isPending}>
            Add
          </button>
        </form>
        {f && f.friends.length === 0 && (
          <button className="btn block" onClick={() => demo.mutate()} disabled={demo.isPending}>
            <Icon name="bot" size={16} /> No friends here yet? Add 3 demo friends
          </button>
        )}
      </div>

      {f && f.incoming.length > 0 && (
        <div className="section">
          <div className="h3">Friend requests</div>
          <div className="stack" style={{ gap: 8 }}>
            {f.incoming.map((r) => (
              <div key={r.friendship_id} className="list-row">
                <div className="avatar">{r.avatar}</div>
                <div className="grow title">{r.display_name}</div>
                <button className="btn sm primary" onClick={() => api.acceptFriend(r.friendship_id).then(refresh)}>
                  Accept
                </button>
                <button className="btn sm ghost" onClick={() => api.declineFriend(r.friendship_id).then(refresh)}>
                  Decline
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {pendingRecs.length > 0 && (
        <div className="section">
          <div className="h3">🎁 Recommended to you</div>
          <div className="stack" style={{ gap: 10 }}>
            {pendingRecs.map((r) => (
              <div key={r.recommendation_id} className="list-row">
                <div className="thumb" onClick={() => setInfo(r.media.media_id)}>
                  <Poster media={r.media} fontSize={5} />
                </div>
                <div className="grow">
                  <div className="small muted">
                    {r.from.avatar} {r.from.display_name} {!r.seen && <span className="tag green">new</span>}
                  </div>
                  <div className="title" onClick={() => setInfo(r.media.media_id)}>
                    {r.media.title}
                  </div>
                  {r.message && <div className="small" style={{ fontStyle: "italic", color: "var(--text-2)" }}>“{r.message}”</div>}
                  <div className="row" style={{ gap: 6, marginTop: 8 }}>
                    <button className="btn sm primary" onClick={() => respond.mutate({ id: r.recommendation_id, action: "watchlist" })}>
                      <Icon name="check" size={14} /> Watch list
                    </button>
                    <button className="btn sm" style={{ color: "var(--star)" }} onClick={() => respond.mutate({ id: r.recommendation_id, action: "must_visit" })}>
                      ★
                    </button>
                    <button className="btn sm ghost" onClick={() => respond.mutate({ id: r.recommendation_id, action: "dismiss" })}>
                      Not now
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {f && f.friends.length > 0 && (
        <div className="section">
          <div className="h3">Friends · taste compatibility</div>
          <div className="stack" style={{ gap: 8 }}>
            {f.friends.map((fr) => (
              <Link key={fr.user_id} to={`/friends/${fr.user_id}`} className="list-row" style={{ textDecoration: "none" }}>
                <div className="avatar">{fr.avatar}</div>
                <div className="grow" style={{ minWidth: 0 }}>
                  <div className="title">{fr.display_name}</div>
                  <div className="small muted ellipsis">
                    {fr.shared_genres?.length ? `Both into ${fr.shared_genres.join(", ")}` : fr.tagline ?? "Swipe more to compare"}
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div className="compat">{fr.compatibility}%</div>
                  <div className="tiny faint">match</div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {activity.data && activity.data.items.length > 0 && (
        <div className="section">
          <div className="h3">This week among friends</div>
          <div className="stack" style={{ gap: 8 }}>
            {activity.data.items.slice(0, 6).map((a) => (
              <div key={a.media.media_id} className="list-row" style={{ cursor: "pointer" }} onClick={() => setInfo(a.media.media_id)}>
                <div className="thumb" style={{ width: 44, height: 64 }}>
                  <Poster media={a.media} fontSize={5} />
                </div>
                <div className="grow">
                  <div className="title">{a.media.title}</div>
                  <div className="small muted">{a.text}</div>
                </div>
                <span className="tag green">{a.count} 👥</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="section">
        <div className="row between" style={{ marginBottom: 10 }}>
          <div className="h3" style={{ margin: 0 }}>Shared lists</div>
          <div className="row" style={{ gap: 6 }}>
            <button className="btn sm" onClick={() => setSheet("joinList")}>
              Join
            </button>
            <button className="btn sm primary" onClick={() => setSheet("newList")}>
              <Icon name="plus" size={14} /> New
            </button>
          </div>
        </div>
        <div className="stack" style={{ gap: 8 }}>
          {lists.data?.lists.map((l) => (
            <Link key={l.list_id} to={`/shared/${l.list_id}`} className="list-row" style={{ textDecoration: "none" }}>
              <div className="avatar" style={{ borderRadius: 14 }}>
                {l.emoji}
              </div>
              <div className="grow">
                <div className="title">{l.name}</div>
                <div className="small muted">
                  {l.item_count} titles · {l.members.map((m) => m.display_name).join(", ")}
                  {l.is_public && " · public"}
                </div>
              </div>
              <Icon name="chevron" size={18} />
            </Link>
          ))}
          {lists.data?.lists.length === 0 && (
            <p className="small muted" style={{ margin: 0 }}>
              Make a “Weekend horror” or “Partner picks” list and invite people to add to it.
            </p>
          )}
        </div>
      </div>

      {parties.data && parties.data.parties.length > 0 && (
        <div className="section">
          <div className="h3">Watch parties</div>
          <div className="stack" style={{ gap: 8 }}>
            {parties.data.parties.map((p) => (
              <Link key={p.party_id} to={`/party/${p.code}`} className="list-row" style={{ textDecoration: "none", opacity: p.upcoming ? 1 : 0.55 }}>
                <div className="thumb" style={{ width: 44, height: 64 }}>
                  {p.media && <Poster media={p.media} fontSize={5} />}
                </div>
                <div className="grow">
                  <div className="title">{p.media?.title}</div>
                  <div className="small muted">
                    {new Date(p.starts_at).toLocaleString([], { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                  </div>
                </div>
                <span className="tag">{p.rsvps.filter((r) => r.status === "going").length} going</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      <InfoPanel mediaId={info} onClose={() => setInfo(null)} onOpenOther={setInfo} />
      <Sheet open={sheet === "newList"} onClose={() => setSheet(null)} title="New shared list">
        <form
          className="stack"
          onSubmit={(e) => {
            e.preventDefault();
            newList.mutate();
          }}
        >
          <input className="input" autoFocus placeholder="Weekend horror, Marvel order, Partner picks…" value={listName} onChange={(e) => setListName(e.target.value)} />
          <div className="chips wrap">
            {["Weekend horror 🎃", "Partner picks 💑", "Marvel order 🦸", "Family night 🏡"].map((t) => (
              <button type="button" key={t} className="chip" onClick={() => setListName(t)}>
                {t}
              </button>
            ))}
          </div>
          <button className="btn primary block">Create list</button>
        </form>
      </Sheet>
      <Sheet open={sheet === "joinList"} onClose={() => setSheet(null)} title="Join a shared list">
        <form
          className="stack"
          onSubmit={(e) => {
            e.preventDefault();
            joinList.mutate();
          }}
        >
          <input className="input code" placeholder="L-XXXXXXX" value={listCode} onChange={(e) => setListCode(e.target.value.toUpperCase())} />
          <button className="btn primary block" disabled={!listCode.trim()}>
            Join
          </button>
        </form>
      </Sheet>
    </div>
  );
}

export function FriendCompare() {
  const { id } = useParams();
  const navigate = useNavigate();
  const q = useQuery({ queryKey: ["compare", id], queryFn: () => api.compare(id!) });
  const [info, setInfo] = useState<string | null>(null);
  const d = q.data;
  return (
    <div className="page narrow">
      <div className="page-header">
        <button className="icon-btn" onClick={() => navigate(-1)} aria-label="Back">
          <Icon name="back" size={20} />
        </button>
        <div className="grow" />
      </div>
      {!d ? (
        <div className="skeleton" style={{ height: 200, borderRadius: 20 }} />
      ) : (
        <div className="stack lg">
          <div className="archetype" style={{ textAlign: "center" }}>
            <div className="row" style={{ justifyContent: "center" }}>
              <div className="avatar lg">{d.friend.avatar}</div>
            </div>
            <div className="name">{d.friend.display_name}</div>
            {d.friend.tagline && <div className="small muted">{d.friend.tagline}</div>}
            <div style={{ fontFamily: "var(--display)", fontSize: 52, fontWeight: 800, marginTop: 10 }} className="compat">
              {d.compatibility}%
            </div>
            <div className="small muted">taste compatibility</div>
            {d.shared_genres.length > 0 && <div className="small" style={{ marginTop: 8 }}>You're both into {d.shared_genres.join(", ")}</div>}
          </div>
          {d.shared.length > 0 && (
            <div>
              <div className="h3">You both saved ({d.shared.length})</div>
              <MiniRow items={d.shared} onOpen={setInfo} />
            </div>
          )}
          {d.you_havent_seen.length > 0 && (
            <div>
              <div className="h3">{d.friend.display_name} loves — you haven't swiped</div>
              <MiniRow items={d.you_havent_seen} onOpen={setInfo} />
            </div>
          )}
          {d.their_top_genres.length > 0 && (
            <div>
              <div className="h3">Their top genres</div>
              <div className="chips wrap">
                {d.their_top_genres.map((g) => (
                  <span key={g} className="chip static">
                    {g}
                  </span>
                ))}
              </div>
            </div>
          )}
          <button className="btn primary block" onClick={() => navigate("/together")}>
            <Icon name="heart" size={18} /> Start a duo session
          </button>
        </div>
      )}
      <InfoPanel mediaId={info} onClose={() => setInfo(null)} onOpenOther={setInfo} />
    </div>
  );
}

export function SharedList() {
  const { id } = useParams();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const q = useQuery({ queryKey: ["collab-list", id], queryFn: () => api.collabList(id!) });
  const [search, setSearch] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const l = q.data;
  const canEdit = l?.your_role === "owner" || l?.your_role === "editor";
  const update = (data: typeof l) => {
    qc.setQueryData(["collab-list", id], data);
    qc.invalidateQueries({ queryKey: ["collab-lists"] });
  };
  const publicUrl = `${shareOrigin()}/l/${id}`;

  return (
    <div className="page narrow">
      <div className="page-header">
        <button className="icon-btn" onClick={() => navigate(-1)} aria-label="Back">
          <Icon name="back" size={20} />
        </button>
        {canEdit && (
          <button className="btn sm primary" onClick={() => setSearch(true)}>
            <Icon name="plus" size={15} /> Add title
          </button>
        )}
      </div>
      {!l ? (
        <div className="skeleton" style={{ height: 200, borderRadius: 20 }} />
      ) : (
        <div className="stack">
          <div>
            <div style={{ fontSize: 40 }}>{l.emoji}</div>
            <h1 className="h1">{l.name}</h1>
            {l.description && <p className="muted">{l.description}</p>}
            <div className="row wrap small muted" style={{ marginTop: 6 }}>
              <div className="avatar-stack">
                {l.members.map((m) => (
                  <div key={m.user_id} className="avatar sm" title={`${m.display_name} (${m.role})`}>
                    {m.avatar}
                  </div>
                ))}
              </div>
              {l.members.length} member{l.members.length === 1 ? "" : "s"} · {l.item_count} titles
            </div>
          </div>

          {canEdit && (
            <div className="panel stack" style={{ gap: 10 }}>
              {l.invite_code && (
                <div className="row between">
                  <div>
                    <div className="small muted">Invite code (editors)</div>
                    <div style={{ fontWeight: 800, letterSpacing: "0.08em" }}>{l.invite_code}</div>
                  </div>
                  <button
                    className="btn sm"
                    onClick={() => {
                      copyText(l.invite_code!);
                      toast("Invite code copied");
                    }}
                  >
                    <Icon name="copy" size={14} /> Copy
                  </button>
                </div>
              )}
              {l.your_role === "owner" && (
                <div className="row between">
                  <div>
                    <div style={{ fontWeight: 600 }}>Public link</div>
                    <div className="tiny faint">Anyone with the link can view (read-only)</div>
                  </div>
                  <button
                    className={`toggle${l.is_public ? " on" : ""}`}
                    aria-pressed={l.is_public}
                    aria-label="Public list"
                    onClick={() => api.updateCollabList(l.list_id, { is_public: !l.is_public }).then(update)}
                  />
                </div>
              )}
              {l.is_public && (
                <button
                  className="btn sm"
                  onClick={() => {
                    copyText(publicUrl);
                    toast("Public link copied");
                  }}
                >
                  <Icon name="link" size={14} /> Copy public link
                </button>
              )}
            </div>
          )}

          {l.items?.map((it) => (
            <div key={it.media_id} className="list-row">
              <div className="thumb" onClick={() => setInfo(it.media_id)}>
                <Poster media={it} fontSize={5} />
              </div>
              <div className="grow" onClick={() => setInfo(it.media_id)} style={{ cursor: "pointer" }}>
                <div className="title">{it.title}</div>
                <div className="small muted">
                  {it.year} · {it.runtime_label}
                </div>
                <div className="tiny faint">Added by {it.added_by}</div>
                {it.note && <div className="small" style={{ fontStyle: "italic", marginTop: 4 }}>“{it.note}”</div>}
              </div>
              {canEdit && (
                <button className="icon-btn" aria-label="Remove" onClick={() => api.removeFromCollabList(l.list_id, it.media_id).then(update)}>
                  <Icon name="trash" size={16} />
                </button>
              )}
            </div>
          ))}
          {l.items?.length === 0 && <div className="empty">No titles yet — add the first one.</div>}

          <button
            className="btn ghost danger"
            onClick={() => {
              if (confirm(l.your_role === "owner" ? "Delete this list for everyone?" : "Leave this list?"))
                api.deleteCollabList(l.list_id).then(() => {
                  qc.invalidateQueries({ queryKey: ["collab-lists"] });
                  navigate("/social");
                });
            }}
          >
            {l.your_role === "owner" ? "Delete list" : "Leave list"}
          </button>
        </div>
      )}
      <SearchSheet
        open={search}
        onClose={() => setSearch(false)}
        actionLabel="Add"
        title={`Add to ${l?.name ?? "list"}`}
        onPick={(m) =>
          api.addToCollabList(id!, m.media_id).then((d) => {
            update(d);
            toast(`Added ${m.title}`);
          })
        }
      />
      <InfoPanel mediaId={info} onClose={() => setInfo(null)} onOpenOther={setInfo} />
    </div>
  );
}

export function PublicList() {
  const { id } = useParams();
  const q = useQuery({ queryKey: ["public-list", id], queryFn: () => api.publicList(id!), retry: false });
  const l = q.data;
  return (
    <div className="page" style={{ maxWidth: 540, margin: "0 auto" }}>
      <div className="brand" style={{ marginBottom: 20 }}>
        <BrandLogo height={42} />
      </div>
      {q.isError && <div className="empty">This list is private or doesn't exist.</div>}
      {l && (
        <div className="stack">
          <div style={{ fontSize: 40 }}>{l.emoji}</div>
          <h1 className="h1">{l.name}</h1>
          <div className="small muted">
            Curated by {l.members.map((m) => `${m.avatar} ${m.display_name}`).join(", ")} · {l.item_count} titles
          </div>
          {l.items?.map((it) => (
            <div key={it.media_id} className="list-row">
              <div className="thumb">
                <Poster media={it} fontSize={5} />
              </div>
              <div className="grow">
                <div className="title">{it.title}</div>
                <div className="small muted">
                  {it.year} · {it.type === "tv" ? "Series" : "Movie"} · {it.genres.slice(0, 2).join(", ")}
                </div>
                <div className="small faint" style={{ marginTop: 4 }}>{it.logline}</div>
                {it.note && <div className="small" style={{ fontStyle: "italic", marginTop: 4 }}>“{it.note}” — {it.added_by}</div>}
              </div>
            </div>
          ))}
          <Link to="/" className="btn primary block">
            Make your own on sai
          </Link>
        </div>
      )}
    </div>
  );
}
