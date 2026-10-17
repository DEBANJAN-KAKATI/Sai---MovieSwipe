import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BrandLogo } from "../components/BrandLogo";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { FeedCard, Media } from "../api/types";
import { SearchSheet, TonightPickSheet } from "../components/Extras";
import { Icon } from "../components/Icon";
import { InfoPanel, MediaDetails } from "../components/InfoPanel";
import { WatchSheet } from "../components/MediaSheets";
import { Sheet } from "../components/Sheet";
import { ActionBar, DIR_TO_ACTION, SwipeDeck, useDeckKeys, type DeckHandle, type Direction } from "../components/SwipeDeck";
import { useIsDesktop } from "../lib/useMedia";
import { toast, useDeckPrefs, type DeckMode } from "../store";

const MODES: { key: DeckMode; label: string; emoji: string }[] = [
  { key: "solo", label: "For you", emoji: "✨" },
  { key: "quick", label: "Quick pick", emoji: "⏱️" },
  { key: "mood", label: "Mood", emoji: "🎭" },
  { key: "decompress", label: "Decompress", emoji: "🫧" },
  { key: "new", label: "New", emoji: "🆕" },
];

const TOASTS: Record<string, string> = {
  watchlist: "Added to your Watch List",
  must_visit: "⭐ Pinned to Must Visit",
  undecided: "Parked in Maybe Later",
  rejected: "Not for you — noted",
  watched: "✓ Marked as watched — tuning your picks",
};

export function asFeedCard(m: Media): FeedCard {
  return {
    ...m,
    match_percent: null,
    because: "Back from undo",
    reasons: m.genres.slice(0, 2),
    badges: [],
    availability: null,
    friends_saved: [],
    friends_saved_count: 0,
    explore: false,
    resurfaced: false,
  };
}

export function Discover() {
  const prefs = useDeckPrefs();
  const desktop = useIsDesktop();
  const qc = useQueryClient();
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: Infinity });
  const [cards, setCards] = useState<FeedCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [exhausted, setExhausted] = useState(false);
  const [coldStart, setColdStart] = useState(false);
  const [personalization, setPersonalization] = useState(0);
  const [canUndo, setCanUndo] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const [watch, setWatch] = useState<Media | null>(null);
  const [sheet, setSheet] = useState<null | "mood" | "filters" | "search" | "tonight" | "help">(null);
  const deck = useRef<DeckHandle>(null);
  const fetching = useRef(false);
  const cardsRef = useRef<FeedCard[]>([]);
  cardsRef.current = cards;
  const gen = useRef(0);

  const load = useCallback(
    async (reset = false) => {
      if (fetching.current && !reset) return;
      fetching.current = true;
      const myGen = reset ? ++gen.current : gen.current;
      if (reset) {
        setCards([]);
        setLoading(true);
      }
      try {
        const res = await api.feed({
          limit: 10,
          mode: prefs.mode,
          mood: prefs.mode === "mood" ? prefs.mood : null,
          type: prefs.type,
          language: prefs.language || undefined,
          exclude: reset ? [] : cardsRef.current.map((c) => c.media_id),
        });
        if (myGen !== gen.current) return;
        setColdStart(res.cold_start);
        setPersonalization(res.personalization);
        setExhausted(res.cards.length === 0);
        setCards((prev) => {
          const have = new Set(prev.map((c) => c.media_id));
          return [...prev, ...res.cards.filter((c) => !have.has(c.media_id))];
        });
      } catch (e) {
        toast((e as Error).message);
      } finally {
        fetching.current = false;
        setLoading(false);
      }
    },
    [prefs.mode, prefs.mood, prefs.type, prefs.language],
  );

  useEffect(() => {
    load(true);
  }, [load]);

  useEffect(() => {
    if (!loading && cards.length < 4 && !exhausted) load();
  }, [cards.length, loading, exhausted, load]);

  useEffect(() => {
    if (!prefs.seenTutorial) setSheet("help");
  }, [prefs.seenTutorial]);

  const onSwipe = useCallback(
    async (card: FeedCard, dir: Direction) => {
      const action = DIR_TO_ACTION[dir];
      if (dir === "up") {
        setWatch(card);
        api.swipe(card.media_id, "watch_intent").catch(() => undefined);
        return;
      }
      setCards((prev) => prev.filter((c) => c.media_id !== card.media_id));
      try {
        await api.swipe(card.media_id, action);
        setCanUndo(true);
        qc.invalidateQueries({ queryKey: ["lists"] });
        if (prefs.blind) toast(`🙈 That was ${card.title} (${card.year ?? "?"}) — ${TOASTS[action].toLowerCase()}`);
        else if (dir === "star" || dir === "seen") toast(TOASTS[action]);
      } catch (e) {
        toast((e as Error).message);
      }
    },
    [prefs.blind, qc],
  );

  const undo = useCallback(async () => {
    try {
      const res = await api.undo();
      if (res.card) setCards((prev) => [asFeedCard(res.card!), ...prev.filter((c) => c.media_id !== res.card!.media_id)]);
      qc.invalidateQueries({ queryKey: ["lists"] });
      toast("Undone");
    } catch {
      setCanUndo(false);
      toast("Nothing to undo");
    }
  }, [qc]);

  useDeckKeys(
    useCallback(
      (k) => {
        if (k === "undo") undo();
        else if (k === "info") cardsRef.current[0] && setInfo(cardsRef.current[0].media_id);
        else deck.current?.swipe(k);
      },
      [undo],
    ),
    !info && !watch && !sheet,
  );

  // Desktop shows the top card's details beside the deck; warm the next two so swipes feel instant.
  const nextIds = cards.slice(0, 3).map((c) => c.media_id).join(",");
  useEffect(() => {
    if (!desktop || !nextIds) return;
    for (const id of nextIds.split(",")) {
      qc.prefetchQuery({ queryKey: ["media", id, "pane"], queryFn: () => api.media(id, false), staleTime: 60_000 });
    }
  }, [desktop, nextIds, qc]);

  const activeMood = meta.data?.moods.find((m) => m.key === prefs.mood);
  const filtersOn = prefs.type !== "all" || !!prefs.language;

  const sheets = (
    <>
      <InfoPanel
        mediaId={info}
        onClose={() => setInfo(null)}
        onOpenOther={(id) => setInfo(id)}
        onDeckAction={info && cards[0]?.media_id === info ? (d) => deck.current?.swipe(d) : undefined}
      />
      <WatchSheet media={watch} onClose={() => setWatch(null)} />
      <TonightPickSheet
        open={sheet === "tonight"}
        onClose={() => setSheet(null)}
        meta={meta.data}
        onOpen={(id) => {
          setSheet(null);
          setInfo(id);
        }}
      />
      <SearchSheet
        open={sheet === "search"}
        onClose={() => setSheet(null)}
        onPick={(m) => {
          setSheet(null);
          setInfo(m.media_id);
        }}
      />

      <Sheet open={sheet === "mood"} onClose={() => setSheet(null)} title="What's the mood?">
        <div className="chips wrap">
          {meta.data?.moods.map((m) => (
            <button
              key={m.key}
              className={`chip${prefs.mode === "mood" && prefs.mood === m.key ? " active" : ""}`}
              style={{ fontSize: 15, padding: "11px 16px" }}
              onClick={() => {
                prefs.set({ mode: "mood", mood: m.key });
                setSheet(null);
              }}
            >
              {m.emoji} {m.label}
            </button>
          ))}
        </div>
      </Sheet>

      <Sheet open={sheet === "filters"} onClose={() => setSheet(null)} title="Deck filters">
        <div className="stack">
          <div>
            <span className="label">Show me</span>
            <div className="segmented">
              {(["all", "movie", "tv"] as const).map((t) => (
                <button key={t} className={prefs.type === t ? "active" : ""} onClick={() => prefs.set({ type: t })}>
                  {t === "all" ? "Everything" : t === "movie" ? "Movies" : "Series"}
                </button>
              ))}
            </div>
          </div>
          <div>
            <span className="label">Language</span>
            <div className="chips wrap">
              <button className={`chip${!prefs.language ? " active" : ""}`} onClick={() => prefs.set({ language: "" })}>
                Any
              </button>
              {meta.data?.languages.map((l) => (
                <button key={l.code} className={`chip${prefs.language === l.code ? " active" : ""}`} onClick={() => prefs.set({ language: l.code })}>
                  {l.name}
                </button>
              ))}
            </div>
          </div>
          <p className="small faint">Content filters (genres, maturity, sensitive themes) live in your profile and always apply.</p>
          <button className="btn primary block" onClick={() => setSheet(null)}>
            Done
          </button>
        </div>
      </Sheet>

      <Sheet open={sheet === "help"} onClose={() => { prefs.set({ seenTutorial: true }); setSheet(null); }} title="How to swipe">
        <div className="stack">
          {[
            ["→", "Swipe right", "Add to your Watch List", "var(--yes)"],
            ["←", "Swipe left", "Not for me", "var(--no)"],
            ["↓", "Swipe down", "Maybe later — it'll come back in a few days", "var(--maybe)"],
            ["↑", "Swipe up", "Where can I watch this in India?", "var(--watch)"],
            ["⏺", "Long-press", "Must Visit — pinned to the top of your list", "var(--star)"],
            ["✓", "Tick button", "Already watched — sharpens your recommendations, stays off your Watch List", "#c4b2ff"],
            ["☝", "Tap", "Flip for the full story, cast, trailer & more", "var(--text)"],
          ].map(([k, g, d, c]) => (
            <div key={g} className="row">
              <div className="avatar" style={{ color: c, fontWeight: 800 }}>
                {k}
              </div>
              <div>
                <div style={{ fontWeight: 700 }}>{g}</div>
                <div className="small muted">{d}</div>
              </div>
            </div>
          ))}
          <button className="btn primary block" onClick={() => { prefs.set({ seenTutorial: true }); setSheet(null); }}>
            Let's go
          </button>
        </div>
      </Sheet>
    </>
  );

  const topCard = cards[0];
  const sidePanel = (
    <aside className="discover-side">
      <div className="panel stack" style={{ gap: 14 }}>
        <div>
          <div className="h3">Deck</div>
          <div className="mode-list" role="tablist" aria-label="Deck mode">
            {MODES.filter((m) => m.key !== "mood").map((m) => (
              <button
                key={m.key}
                role="tab"
                aria-selected={prefs.mode === m.key}
                className={`mode-item${prefs.mode === m.key ? " active" : ""}`}
                onClick={() => prefs.set({ mode: m.key })}
              >
                <span>{m.emoji}</span> {m.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <div className="h3">Mood</div>
          <div className="chips wrap">
            {meta.data?.moods.map((m) => (
              <button
                key={m.key}
                className={`chip${prefs.mode === "mood" && prefs.mood === m.key ? " active" : ""}`}
                onClick={() =>
                  prefs.mode === "mood" && prefs.mood === m.key ? prefs.set({ mode: "solo" }) : prefs.set({ mode: "mood", mood: m.key })
                }
              >
                {m.emoji} {m.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <div className="h3">Show me</div>
          <div className="segmented">
            {(["all", "movie", "tv"] as const).map((t) => (
              <button key={t} className={prefs.type === t ? "active" : ""} onClick={() => prefs.set({ type: t })}>
                {t === "all" ? "All" : t === "movie" ? "Movies" : "Series"}
              </button>
            ))}
          </div>
        </div>
        <div>
          <div className="h3">Language</div>
          <select className="select" value={prefs.language} onChange={(e) => prefs.set({ language: e.target.value })} aria-label="Language">
            <option value="">Any language</option>
            {meta.data?.languages.map((l) => (
              <option key={l.code} value={l.code}>
                {l.name}
              </option>
            ))}
          </select>
        </div>
        <div className="row between">
          <div>
            <div style={{ fontWeight: 600 }}>🙈 Blind date</div>
            <div className="tiny faint">Judge by the story, not the poster</div>
          </div>
          <button
            className={`toggle${prefs.blind ? " on" : ""}`}
            aria-pressed={prefs.blind}
            aria-label="Blind date mode"
            onClick={() => prefs.set({ blind: !prefs.blind })}
          />
        </div>
      </div>
      <button className="btn primary block" onClick={() => setSheet("tonight")}>
        <Icon name="dice" size={18} /> Decide for me
      </button>
      <button className="btn block" onClick={() => setSheet("search")}>
        <Icon name="search" size={18} /> Search titles, cast, themes
      </button>
      {coldStart && cards.length > 0 && (
        <div className="small muted" style={{ marginTop: 10 }}>
          <Icon name="sparkles" size={14} /> Swipe right on a few you like — your deck learns from every swipe.
        </div>
      )}
      {!coldStart && personalization > 0 && personalization < 0.9 && (
        <div className="row small faint" style={{ marginTop: 10 }}>
          <span>Tuning to your taste</span>
          <div className="progress grow">
            <div style={{ width: `${Math.round(personalization * 100)}%` }} />
          </div>
        </div>
      )}

    </aside>
  );

  if (desktop) {
    return (
      <div className="page discover-page">
        <div className="discover-grid">
          {sidePanel}
          <section className="discover-center">
      <SwipeDeck
        ref={deck}
        cards={cards}
        blind={prefs.blind}
        loading={loading}
        onSwipe={onSwipe}
        onTap={(c) => setInfo(c.media_id)}
        empty={
          <>
            <div className="big">🎬</div>
            <div className="h2">You've seen everything here</div>
            <p className="muted small" style={{ margin: 0 }}>
              Try another mode, loosen your filters, or check your Maybe Later pile.
            </p>
            <button className="btn" onClick={() => prefs.set({ mode: "solo", type: "all", language: "" })}>
              Reset filters
            </button>
          </>
        }
      />

            <ActionBar onAction={(d) => deck.current?.swipe(d)} onUndo={undo} canUndo={canUndo} disabled={!cards.length} />
            <div className="kbd-hint">
              <kbd>←</kbd> nope <kbd>→</kbd> watch list <kbd>W</kbd> watched <kbd>↓</kbd> maybe <kbd>↑</kbd> where to watch{" "}
              <kbd>S</kbd> must visit <kbd>Z</kbd> undo
            </div>
          </section>
          <aside className="discover-detail" aria-label="Current title details">
            {topCard && !prefs.blind ? (
              <MediaDetails
                key={topCard.media_id}
                mediaId={topCard.media_id}
                embedded
                onAction={(dir) => deck.current?.swipe(dir)}
                onOpenOther={(id) => setInfo(id)}
              />
            ) : (
              <div className="panel empty">
                <div className="big">{prefs.blind ? "🙈" : "🎬"}</div>
                <p>{prefs.blind ? "Blind date is on — details appear after you swipe." : "Details of the current card show up here."}</p>
              </div>
            )}
          </aside>
        </div>
        {sheets}
      </div>
    );
  }

  return (
    <div className="page" style={{ paddingTop: 10 }}>
      <div className="page-header" style={{ marginBottom: 10 }}>
        <div className="brand">
          <BrandLogo height={36} />
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className="icon-btn" onClick={() => setSheet("search")} aria-label="Search">
            <Icon name="search" size={19} />
          </button>
          <button className="icon-btn" onClick={() => setSheet("tonight")} aria-label="Decide for me">
            <Icon name="dice" size={19} />
          </button>
          <button className="icon-btn" onClick={() => setSheet("filters")} aria-label="Filters">
            <Icon name="settings" size={19} />
            {filtersOn && <span className="dot" />}
          </button>
        </div>
      </div>

      <div className="chips" role="tablist" aria-label="Deck mode">
        {MODES.map((m) => (
          <button
            key={m.key}
            role="tab"
            aria-selected={prefs.mode === m.key}
            className={`chip${prefs.mode === m.key ? " active" : ""}`}
            onClick={() => (m.key === "mood" ? setSheet("mood") : prefs.set({ mode: m.key }))}
          >
            {m.key === "mood" && activeMood && prefs.mode === "mood" ? `${activeMood.emoji} ${activeMood.label}` : `${m.emoji} ${m.label}`}
          </button>
        ))}
        <button
          className={`chip${prefs.blind ? " active" : ""}`}
          onClick={() => {
            prefs.set({ blind: !prefs.blind });
            toast(prefs.blind ? "Blind date off" : "🙈 Blind date: judge by the story, not the poster");
          }}
        >
          🙈 Blind date
        </button>
      </div>

      {coldStart && cards.length > 0 && (
        <div className="small muted" style={{ marginTop: 10 }}>
          <Icon name="sparkles" size={14} /> Swipe right on a few you like — your deck learns from every swipe.
        </div>
      )}
      {!coldStart && personalization > 0 && personalization < 0.9 && (
        <div className="row small faint" style={{ marginTop: 10 }}>
          <span>Tuning to your taste</span>
          <div className="progress grow">
            <div style={{ width: `${Math.round(personalization * 100)}%` }} />
          </div>
        </div>
      )}

      <SwipeDeck
        ref={deck}
        cards={cards}
        blind={prefs.blind}
        loading={loading}
        onSwipe={onSwipe}
        onTap={(c) => setInfo(c.media_id)}
        empty={
          <>
            <div className="big">🎬</div>
            <div className="h2">You've seen everything here</div>
            <p className="muted small" style={{ margin: 0 }}>
              Try another mode, loosen your filters, or check your Maybe Later pile.
            </p>
            <button className="btn" onClick={() => prefs.set({ mode: "solo", type: "all", language: "" })}>
              Reset filters
            </button>
          </>
        }
      />

      <ActionBar onAction={(d) => deck.current?.swipe(d)} onUndo={undo} canUndo={canUndo} disabled={!cards.length} />
      <div className="kbd-hint">
        <kbd>←</kbd> nope <kbd>→</kbd> watch list <kbd>W</kbd> already watched <kbd>↓</kbd> maybe <kbd>↑</kbd> where to watch <kbd>S</kbd> must visit{" "}
        <kbd>Space</kbd> details <kbd>Z</kbd> undo · <button className="btn sm ghost" onClick={() => setSheet("help")}>Gestures</button>
      </div>

      {sheets}
    </div>
  );
}

