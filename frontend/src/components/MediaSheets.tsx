import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Media, WatchInfo } from "../api/types";
import { toast, useAuth } from "../store";
import { Icon } from "./Icon";
import { Poster } from "./Poster";
import { Sheet } from "./Sheet";

const PROVIDER_COLORS: Record<string, string> = {
  Netflix: "#E50914",
  "Prime Video": "#00A8E1",
  JioHotstar: "#1F80E0",
  SonyLIV: "#F5A623",
  ZEE5: "#8230C6",
  "Apple TV+": "#555",
  Aha: "#FF6D00",
  "Sun NXT": "#F7B500",
};

export function WatchOptions({ info, title }: { info: WatchInfo; title: string }) {
  return (
    <div className="stack" style={{ gap: 8 }}>
      {info.providers.map((p) => (
        <a key={p.name} className="provider-row" href={p.link} target="_blank" rel="noreferrer noopener">
          <div className="row">
            <div className="provider-dot" style={{ background: PROVIDER_COLORS[p.name] ?? "#444" }}>
              {p.name[0]}
            </div>
            <div>
              <div style={{ fontWeight: 700 }}>{p.name}</div>
              <div className="tiny faint">
                {p.type === "flatrate" ? "Streaming" : p.type === "rent" ? "Rent" : p.type === "buy" ? "Buy" : p.type}
                {p.on_your_plan && " · on your plan"}
              </div>
            </div>
          </div>
          {p.on_your_plan ? <span className="tag green">Yours</span> : <Icon name="chevron" size={18} />}
        </a>
      ))}
      <a className="btn primary block" href={info.google_url} target="_blank" rel="noreferrer noopener">
        <Icon name="search" size={18} /> Where can I watch “{title}” in India?
      </a>
      <p className="tiny faint" style={{ margin: "4px 2px 0" }}>
        {info.disclaimer}
      </p>
    </div>
  );
}

export function WatchSheet({ media, onClose }: { media: Media | null; onClose: () => void }) {
  const q = useQuery({
    queryKey: ["watch", media?.media_id],
    queryFn: () => api.watchInIndia(media!.media_id),
    enabled: !!media,
  });
  return (
    <Sheet open={!!media} onClose={onClose} title="Where to watch in India">
      {media && (
        <div className="stack">
          <div className="row">
            <div className="thumb">
              <Poster media={media} fontSize={6} />
            </div>
            <div className="grow">
              <div className="h2">{media.title}</div>
              <div className="small muted">
                {media.year} · {media.runtime_label}
              </div>
            </div>
          </div>
          {q.data ? <WatchOptions info={q.data} title={media.title} /> : <div className="skeleton" style={{ height: 120, borderRadius: 14 }} />}
        </div>
      )}
    </Sheet>
  );
}

export function RecommendSheet({ media, onClose }: { media: Media | null; onClose: () => void }) {
  const friends = useQuery({ queryKey: ["friends"], queryFn: api.friends, enabled: !!media });
  const [msg, setMsg] = useState("");
  const [to, setTo] = useState<string | null>(null);
  const navigate = useNavigate();
  useEffect(() => {
    setMsg("");
    setTo(null);
  }, [media]);
  const send = useMutation({
    mutationFn: () => api.recommend(to!, media!.media_id, msg),
    onSuccess: () => {
      toast("Recommendation sent 🎁");
      onClose();
    },
    onError: (e: Error) => toast(e.message),
  });
  const list = friends.data?.friends ?? [];
  return (
    <Sheet open={!!media} onClose={onClose} title={`Recommend ${media?.title ?? ""}`}>
      {list.length === 0 && !friends.isLoading ? (
        <div className="empty">
          <div className="big">👋</div>
          <p>Add a friend first, then you can send them titles with one tap.</p>
          <button
            className="btn primary"
            onClick={() => {
              onClose();
              navigate("/social");
            }}
          >
            Find friends
          </button>
        </div>
      ) : (
        <div className="stack">
          <div className="chips wrap">
            {list.map((f) => (
              <button key={f.user_id} className={`chip${to === f.user_id ? " active" : ""}`} onClick={() => setTo(f.user_id)}>
                {f.avatar} {f.display_name}
              </button>
            ))}
          </div>
          <textarea
            className="input"
            rows={2}
            placeholder="Add a note (optional) — e.g. “You have to see this”"
            value={msg}
            maxLength={300}
            onChange={(e) => setMsg(e.target.value)}
          />
          <button className="btn primary block" disabled={!to || send.isPending} onClick={() => send.mutate()}>
            <Icon name="send" size={18} /> Send
          </button>
        </div>
      )}
    </Sheet>
  );
}

export function AddToListSheet({ media, onClose }: { media: Media | null; onClose: () => void }) {
  const qc = useQueryClient();
  const lists = useQuery({ queryKey: ["collab-lists"], queryFn: api.collabLists, enabled: !!media });
  const [name, setName] = useState("");
  const add = useMutation({
    mutationFn: async (listId: string | null) => {
      let id = listId;
      if (!id) id = (await api.createCollabList({ name: name.trim() || "Our picks" })).list_id;
      return api.addToCollabList(id, media!.media_id);
    },
    onSuccess: (l) => {
      qc.invalidateQueries({ queryKey: ["collab-lists"] });
      toast(`Added to ${l.emoji} ${l.name}`);
      onClose();
    },
    onError: (e: Error) => toast(e.message),
  });
  const editable = (lists.data?.lists ?? []).filter((l) => l.your_role === "owner" || l.your_role === "editor");
  return (
    <Sheet open={!!media} onClose={onClose} title="Add to a shared list">
      <div className="stack">
        {editable.map((l) => (
          <button key={l.list_id} className="provider-row" style={{ cursor: "pointer" }} onClick={() => add.mutate(l.list_id)}>
            <div className="row">
              <div className="provider-dot" style={{ background: "var(--surface-3)", fontSize: 18 }}>
                {l.emoji}
              </div>
              <div style={{ textAlign: "left" }}>
                <div style={{ fontWeight: 700 }}>{l.name}</div>
                <div className="tiny faint">
                  {l.item_count} titles · {l.members.length} member{l.members.length === 1 ? "" : "s"}
                </div>
              </div>
            </div>
            <Icon name="plus" size={18} />
          </button>
        ))}
        <div className="row">
          <input className="input" placeholder="New list name, e.g. Partner picks" value={name} onChange={(e) => setName(e.target.value)} />
          <button className="btn primary" onClick={() => add.mutate(null)} disabled={add.isPending}>
            Create
          </button>
        </div>
      </div>
    </Sheet>
  );
}

function defaultPartyTime(): string {
  const d = new Date();
  d.setDate(d.getDate() + (d.getHours() >= 19 ? 1 : 0));
  d.setHours(20, 30, 0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function PartySheet({
  media,
  sessionId,
  onClose,
}: {
  media: Media | null;
  sessionId?: string | null;
  onClose: () => void;
}) {
  const [when, setWhen] = useState(defaultPartyTime);
  const [notes, setNotes] = useState("");
  const navigate = useNavigate();
  const create = useMutation({
    mutationFn: () =>
      api.createParty({ media_id: media!.media_id, starts_at: new Date(when).toISOString(), notes, session_id: sessionId }),
    onSuccess: (p) => {
      onClose();
      navigate(`/party/${p.code}`);
    },
    onError: (e: Error) => toast(e.message),
  });
  return (
    <Sheet open={!!media} onClose={onClose} title="Plan a watch party">
      {media && (
        <div className="stack">
          <div className="row">
            <div className="thumb">
              <Poster media={media} fontSize={6} />
            </div>
            <div>
              <div className="h2">{media.title}</div>
              <div className="small muted">{media.runtime_label}</div>
            </div>
          </div>
          <label>
            <span className="label">When</span>
            <input className="input" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} />
          </label>
          <label>
            <span className="label">Notes for guests</span>
            <input className="input" placeholder="Snacks at mine, bring blankets" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
          <button className="btn primary block" onClick={() => create.mutate()} disabled={create.isPending}>
            <Icon name="calendar" size={18} /> Create invite
          </button>
          <p className="tiny faint">You'll get an invite link and a calendar file with a 1-hour reminder.</p>
        </div>
      )}
    </Sheet>
  );
}

export function useSpoilerShield(): boolean {
  return useAuth((s) => s.user?.preferences.spoiler_shield ?? false);
}
