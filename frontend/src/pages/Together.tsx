import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { QRCodeSVG } from "qrcode.react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { shareOrigin } from "../api/base";
import { copyText } from "../lib/clipboard";
import { api, sessionSocketUrl } from "../api/client";
import type { FeedCard, MatchInfo, Media } from "../api/types";
import { MatchCelebration, TonightPickSheet } from "../components/Extras";
import { Icon } from "../components/Icon";
import { InfoPanel } from "../components/InfoPanel";
import { PartySheet, WatchSheet } from "../components/MediaSheets";
import { Poster } from "../components/Poster";
import { Sheet } from "../components/Sheet";
import { ActionBar, DIR_TO_ACTION, SwipeDeck, useDeckKeys, type DeckHandle, type Direction } from "../components/SwipeDeck";
import { toast } from "../store";

function timeAgo(iso: string) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

export function Together() {
  const navigate = useNavigate();
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: Infinity });
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: api.sessions });
  const [mode, setMode] = useState<"duo" | "group">("duo");
  const [minVotes, setMinVotes] = useState<number | null>(2);
  const [mood, setMood] = useState<string | null>(null);
  const [type, setType] = useState("all");
  const [code, setCode] = useState("");

  const create = useMutation({
    mutationFn: () => api.createSession({ mode, min_votes: mode === "group" ? minVotes : null, mood, type }),
    onSuccess: (s) => navigate(`/session/${s.session_id}`),
    onError: (e: Error) => toast(e.message),
  });
  const join = useMutation({
    mutationFn: () => api.joinSession(code),
    onSuccess: (s) => navigate(`/session/${s.session_id}`),
    onError: (e: Error) => toast(e.message),
  });

  return (
    <div className="page narrow">
      <div className="page-header">
        <div>
          <h1 className="h1">Swipe together</h1>
          <p className="muted small" style={{ margin: "6px 0 0" }}>
            Everyone swipes the same blended stack. When you agree, it's a match.
          </p>
        </div>
      </div>

      <div className="panel stack">
        <div className="segmented">
          <button className={mode === "duo" ? "active" : ""} onClick={() => setMode("duo")}>
            💑 Duo
          </button>
          <button className={mode === "group" ? "active" : ""} onClick={() => setMode("group")}>
            🍕 Group
          </button>
        </div>
        {mode === "group" && (
          <div>
            <span className="label">A title matches when…</span>
            <div className="chips wrap">
              {[
                [2, "Any 2 agree"],
                [3, "3 agree"],
                [null, "Everyone agrees"],
              ].map(([v, l]) => (
                <button key={String(v)} className={`chip${minVotes === v ? " active" : ""}`} onClick={() => setMinVotes(v as number | null)}>
                  {l}
                </button>
              ))}
            </div>
          </div>
        )}
        <div>
          <span className="label">Tonight's vibe (optional)</span>
          <div className="chips wrap">
            {meta.data?.moods.map((m) => (
              <button key={m.key} className={`chip${mood === m.key ? " active" : ""}`} onClick={() => setMood(mood === m.key ? null : m.key)}>
                {m.emoji} {m.label}
              </button>
            ))}
          </div>
        </div>
        <div className="segmented">
          {[
            ["all", "Anything"],
            ["movie", "Movies"],
            ["tv", "Series"],
          ].map(([k, l]) => (
            <button key={k} className={type === k ? "active" : ""} onClick={() => setType(k)}>
              {l}
            </button>
          ))}
        </div>
        <button className="btn primary block lg" onClick={() => create.mutate()} disabled={create.isPending}>
          Start a {mode} session
        </button>
      </div>

      <div className="panel stack" style={{ marginTop: 14 }}>
        <div className="h2">Got a code?</div>
        <form
          className="row"
          onSubmit={(e) => {
            e.preventDefault();
            if (code.trim()) join.mutate();
          }}
        >
          <input className="input code" placeholder="ABC2345" maxLength={7} value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} />
          <button className="btn primary" disabled={code.length < 4 || join.isPending}>
            Join
          </button>
        </form>
      </div>

      {sessions.data && sessions.data.sessions.length > 0 && (
        <div className="section">
          <div className="h3">Recent sessions</div>
          <div className="stack" style={{ gap: 10 }}>
            {sessions.data.sessions.map((s) => (
              <Link key={s.session_id} to={`/session/${s.session_id}`} className="list-row" style={{ textDecoration: "none" }}>
                <div className="thumb" style={{ width: 52, height: 76 }}>
                  {s.latest_match ? <Poster media={s.latest_match.media} fontSize={5} /> : <div className="gen-poster" style={{ background: "var(--surface-2)", fontSize: 8 }}><div className="gp-glyph" style={{ margin: "auto" }}>{s.mode === "duo" ? "💑" : "🍕"}</div></div>}
                </div>
                <div className="grow">
                  <div className="title">{s.members.map((m) => m.display_name).join(" + ")}</div>
                  <div className="small muted">
                    {s.match_count} match{s.match_count === 1 ? "" : "es"} · {timeAgo(s.created_at)} · {s.status === "open" ? "live" : s.status}
                  </div>
                  {s.latest_match && <div className="tiny faint ellipsis">Latest: {s.latest_match.media.title}</div>}
                </div>
                <div className="avatar-stack">
                  {s.members.slice(0, 3).map((m) => (
                    <div key={m.user_id} className="avatar sm">
                      {m.avatar}
                    </div>
                  ))}
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function JoinRedirect() {
  const { code } = useParams();
  const navigate = useNavigate();
  const started = useRef(false);
  useEffect(() => {
    if (started.current || !code) return;
    started.current = true;
    api
      .joinSession(code)
      .then((s) => navigate(`/session/${s.session_id}`, { replace: true }))
      .catch((e: Error) => {
        toast(e.message);
        navigate("/together", { replace: true });
      });
  }, [code, navigate]);
  return <div className="page empty">Joining session {code}…</div>;
}

export function SessionRoom() {
  const { id } = useParams();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: Infinity });
  const state = useQuery({ queryKey: ["session", id], queryFn: () => api.session(id!), refetchInterval: 6000 });
  const [cards, setCards] = useState<FeedCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [celebrate, setCelebrate] = useState<MatchInfo | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [watch, setWatch] = useState<Media | null>(null);
  const [party, setParty] = useState<Media | null>(null);
  const [sheet, setSheet] = useState<null | "invite" | "matches" | "tonight">(null);
  const deck = useRef<DeckHandle>(null);
  const seenMatches = useRef<Set<string>>(new Set());
  const cardsRef = useRef(cards);
  cardsRef.current = cards;
  const loadingMore = useRef(false);

  const s = state.data;
  const open = s?.status === "open";
  const alone = (s?.members.length ?? 0) < 2;

  const loadMore = useCallback(async () => {
    if (!id || loadingMore.current) return;
    loadingMore.current = true;
    try {
      const res = await api.sessionFeed(id, 12);
      setCards((prev) => {
        const have = new Set(prev.map((c) => c.media_id));
        return [...prev, ...res.cards.filter((c) => !have.has(c.media_id))];
      });
    } catch (e) {
      toast((e as Error).message);
    } finally {
      loadingMore.current = false;
      setLoading(false);
    }
  }, [id]);

  const memberCount = s?.members.length ?? 0;
  useEffect(() => {
    // (Re)load when membership changes before anyone has swiped — the stack is re-blended.
    if (!open) return;
    setCards([]);
    setLoading(true);
    loadMore();
  }, [memberCount, open, loadMore]);

  useEffect(() => {
    if (open && !loading && cards.length < 4) loadMore();
  }, [cards.length, loading, open, loadMore]);

  // Matches that existed when the room opened don't celebrate; new ones (e.g. made by a partner) do.
  const primed = useRef(false);
  useEffect(() => {
    if (!s) return;
    for (const m of s.matches) {
      if (seenMatches.current.has(m.match_id)) continue;
      seenMatches.current.add(m.match_id);
      if (primed.current) setCelebrate(m);
    }
    primed.current = true;
  }, [s]);

  // Live updates over WebSocket (polling above is the fallback).
  useEffect(() => {
    if (!id) return;
    let ws: WebSocket | null = null;
    let alive = true;
    let ping: number | undefined;
    const connect = () => {
      ws = new WebSocket(sessionSocketUrl(id));
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.event === "session.match" || msg.event === "session.user_joined" || msg.event === "session.closed") {
          qc.invalidateQueries({ queryKey: ["session", id] });
        }
        if (msg.event === "session.user_joined") toast(`${msg.data.avatar} ${msg.data.display_name} joined`);
        if (msg.event === "session.progress") {
          qc.setQueryData(["session", id], (old: typeof s) =>
            old ? { ...old, members: old.members.map((m) => ({ ...m, swiped: msg.data.swiped[m.user_id] ?? m.swiped })) } : old,
          );
        }
      };
      ws.onopen = () => {
        ping = window.setInterval(() => ws?.readyState === 1 && ws.send("ping"), 25_000);
      };
      ws.onclose = () => {
        window.clearInterval(ping);
        if (alive) setTimeout(connect, 3000);
      };
    };
    connect();
    return () => {
      alive = false;
      window.clearInterval(ping);
      ws?.close();
    };
  }, [id, qc]);

  const onSwipe = useCallback(
    async (card: FeedCard, dir: Direction) => {
      if (dir === "up") {
        setWatch(card);
        return;
      }
      setCards((prev) => prev.filter((c) => c.media_id !== card.media_id));
      try {
        const res = await api.swipe(card.media_id, DIR_TO_ACTION[dir], id);
        if (res.match && !seenMatches.current.has(res.match.match_id)) {
          seenMatches.current.add(res.match.match_id);
          setCelebrate(res.match);
        }
        qc.invalidateQueries({ queryKey: ["session", id] });
      } catch (e) {
        toast((e as Error).message);
      }
    },
    [id, qc],
  );

  useDeckKeys(
    useCallback(
      (k) => {
        if (k === "info") cardsRef.current[0] && setInfo(cardsRef.current[0].media_id);
        else if (k !== "undo") deck.current?.swipe(k);
      },
      [],
    ),
    !info && !watch && !sheet && !celebrate && !party,
  );

  const addBot = useMutation({
    mutationFn: () => api.addBot(id!),
    onSuccess: (st) => qc.setQueryData(["session", id], st),
    onError: (e: Error) => toast(e.message),
  });
  const close = useMutation({
    mutationFn: () => api.closeSession(id!),
    onSuccess: (st) => qc.setQueryData(["session", id], st),
  });

  if (state.isError) {
    return (
      <div className="page empty">
        <div className="big">🔒</div>
        <p>{(state.error as Error).message}</p>
        <button className="btn" onClick={() => navigate("/together")}>
          Back
        </button>
      </div>
    );
  }
  if (!s) return <div className="page narrow"><div className="skeleton" style={{ height: 400, borderRadius: 24 }} /></div>;

  const inviteUrl = `${shareOrigin()}${s.join_path}`;
  const moodMeta = meta.data?.moods.find((m) => m.key === s.filters.mood);

  return (
    <div className="page narrow session-room" style={{ paddingTop: 10 }}>
      <div className="page-header" style={{ marginBottom: 8 }}>
        <button className="icon-btn" onClick={() => navigate("/together")} aria-label="Back">
          <Icon name="back" size={20} />
        </button>
        <div className="grow" style={{ textAlign: "center" }}>
          <div className="h2">{s.mode === "duo" ? "Duo session" : "Group session"}</div>
          <div className="tiny faint">
            {moodMeta ? `${moodMeta.emoji} ${moodMeta.label} · ` : ""}
            {s.mode === "group" ? `${s.required_votes} votes to match` : "match when you both say yes"}
          </div>
        </div>
        <button className="icon-btn" onClick={() => setSheet("matches")} aria-label="Matches">
          <Icon name="heart" size={19} solid={s.matches.length > 0} />
          {s.matches.length > 0 && <span className="dot" />}
        </button>
      </div>

      <div className="row between panel tight" style={{ marginBottom: 4 }}>
        <div className="row" style={{ gap: 8, minWidth: 0 }}>
          {s.members.map((m) => (
            <div key={m.user_id} className="row" style={{ gap: 6 }} title={`${m.display_name}: ${m.swiped} swiped`}>
              <div className="avatar sm">{m.avatar}</div>
              <div className="tiny">
                <div style={{ fontWeight: 700 }}>{m.is_you ? "You" : m.display_name}</div>
                <div className="faint">{m.swiped} swiped</div>
              </div>
            </div>
          ))}
        </div>
        <button className="btn sm" onClick={() => setSheet("invite")}>
          <Icon name="plus" size={15} /> Invite
        </button>
      </div>

      {!open ? (
        <div className="deck-wrap">
          <div className="deck-empty">
            <div className="big">🏁</div>
            <div className="h2">This session has {s.status === "closed" ? "ended" : "expired"}</div>
            <p className="muted small">{s.matches.length} match{s.matches.length === 1 ? "" : "es"} — pick one to watch!</p>
            <button className="btn primary" onClick={() => setSheet("tonight")}>
              <Icon name="dice" size={16} /> Pick from our matches
            </button>
          </div>
        </div>
      ) : alone ? (
        <div className="deck-wrap">
          <div className="deck-empty">
            <div className="big">⏳</div>
            <div className="h2">Waiting for {s.mode === "duo" ? "your partner" : "your crew"}</div>
            <p className="muted small" style={{ margin: 0 }}>Share code</p>
            <div className="code-box">{s.code}</div>
            <div className="row">
              <button className="btn primary" onClick={() => setSheet("invite")}>
                <Icon name="share" size={16} /> Share invite
              </button>
              <button className="btn" onClick={() => addBot.mutate()} disabled={addBot.isPending}>
                <Icon name="bot" size={16} /> Try with a demo bot
              </button>
            </div>
          </div>
        </div>
      ) : (
        <>
          <SwipeDeck
            ref={deck}
            cards={cards}
            loading={loading}
            onSwipe={onSwipe}
            onTap={(c) => setInfo(c.media_id)}
            empty={
              <>
                <div className="big">🍿</div>
                <div className="h2">Stack finished</div>
                <p className="muted small">Check your matches or let us pick one.</p>
                <button className="btn primary" onClick={() => setSheet("tonight")}>
                  Pick from matches
                </button>
              </>
            }
          />
          <ActionBar onAction={(d) => deck.current?.swipe(d)} disabled={!cards.length} />
        </>
      )}

      <div className="row" style={{ justifyContent: "center", marginTop: 28, gap: 8 }}>
        {open && (
          <button className="btn sm" onClick={() => setSheet("tonight")} disabled={!s.matches.length}>
            <Icon name="dice" size={15} /> Decide from {s.matches.length} match{s.matches.length === 1 ? "" : "es"}
          </button>
        )}
        {open && s.mode === "group" && !alone && (
          <button className="btn sm" onClick={() => addBot.mutate()}>
            <Icon name="bot" size={15} /> Add bot
          </button>
        )}
        {open && s.is_host && (
          <button className="btn sm ghost" onClick={() => close.mutate()}>
            End session
          </button>
        )}
      </div>

      <Sheet open={sheet === "invite"} onClose={() => setSheet(null)} title="Invite to this session">
        <div className="stack" style={{ alignItems: "center", textAlign: "center" }}>
          <div className="qr">
            <QRCodeSVG value={inviteUrl} size={180} />
          </div>
          <div className="code-box" style={{ width: "100%" }}>
            {s.code}
          </div>
          <button
            className="btn primary block"
            onClick={async () => {
              const text = `Swipe with me on sai! Code ${s.code} — ${inviteUrl}`;
              if (navigator.share) await navigator.share({ title: "sai session", text, url: inviteUrl }).catch(() => undefined);
              else {
                await copyText(text);
                toast("Invite copied");
              }
            }}
          >
            <Icon name="share" size={18} /> Share link
          </button>
          <p className="tiny faint">Codes expire with the session ({new Date(s.expires_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}).</p>
          {s.mode === "group" || s.members.length < 2 ? (
            <button className="btn block" onClick={() => addBot.mutate()}>
              <Icon name="bot" size={16} /> Add a demo bot instead
            </button>
          ) : null}
        </div>
      </Sheet>

      <Sheet open={sheet === "matches"} onClose={() => setSheet(null)} title={`Matches (${s.matches.length})`}>
        {s.matches.length === 0 ? (
          <div className="empty">
            <div className="big">💞</div>
            <p>No matches yet. Keep swiping — when {s.mode === "duo" ? "you both" : `${s.required_votes} of you`} swipe right on the same title, it lands here.</p>
          </div>
        ) : (
          <div className="stack">
            {s.matches.map((m) => (
              <div key={m.match_id} className="list-row">
                <div className="thumb" onClick={() => setInfo(m.media.media_id)}>
                  <Poster media={m.media} fontSize={5} />
                </div>
                <div className="grow">
                  <div className="title">
                    {m.super_match && "⭐ "}
                    {m.media.title}
                  </div>
                  <div className="small muted">{m.participants.join(", ")}</div>
                  <div className="row" style={{ gap: 6, marginTop: 6 }}>
                    <button className="btn sm" onClick={() => setWatch(m.media)}>
                      <Icon name="play" size={14} /> Watch
                    </button>
                    <button className="btn sm" onClick={() => setParty(m.media)}>
                      <Icon name="calendar" size={14} /> Party
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Sheet>

      <MatchCelebration
        match={celebrate}
        onClose={() => setCelebrate(null)}
        onWatch={(m) => {
          setCelebrate(null);
          setWatch(m);
        }}
        onParty={(m) => {
          setCelebrate(null);
          setParty(m);
        }}
      />
      <InfoPanel
        mediaId={info}
        onClose={() => setInfo(null)}
        onOpenOther={setInfo}
        onDeckAction={open && !alone && info && cards[0]?.media_id === info ? (d) => deck.current?.swipe(d) : undefined}
      />
      <WatchSheet media={watch} onClose={() => setWatch(null)} />
      <PartySheet media={party} sessionId={id} onClose={() => setParty(null)} />
      <TonightPickSheet
        open={sheet === "tonight"}
        onClose={() => setSheet(null)}
        sessionId={id}
        meta={meta.data}
        onOpen={(mid) => {
          setSheet(null);
          setInfo(mid);
        }}
      />
    </div>
  );
}
