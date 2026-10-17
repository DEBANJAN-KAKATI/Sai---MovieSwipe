import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { ListAction, ListItemCard, Media } from "../api/types";
import { RatingStars, TonightPickSheet } from "../components/Extras";
import { Icon } from "../components/Icon";
import { InfoPanel } from "../components/InfoPanel";
import { AddToListSheet, PartySheet, RecommendSheet, WatchSheet } from "../components/MediaSheets";
import { Poster } from "../components/Poster";
import { Sheet } from "../components/Sheet";
import { toast } from "../store";

type Tab = "itinerary" | "maybe" | "history";

function fmtMinutes(min: number) {
  const h = Math.floor(min / 60);
  const m = min % 60;
  return h ? `${h}h ${m}m` : `${m}m`;
}

function Row({
  item,
  pinned,
  onOpen,
  onAction,
  onMore,
}: {
  item: ListItemCard;
  pinned?: boolean;
  onOpen: () => void;
  onAction: (a: ListAction, rating?: number) => void;
  onMore: (kind: "watch" | "friend" | "list" | "party" | "rate") => void;
}) {
  const [menu, setMenu] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!menu) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setMenu(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [menu]);
  const items: [string, string, () => void][] = [];
  if (item.action !== "must_visit") items.push(["star", "Pin as Must Visit", () => onAction("must_visit")]);
  if (item.action !== "watchlist") items.push(["check", "Move to Watch List", () => onAction("watchlist")]);
  if (item.action !== "undecided") items.push(["clock", "Maybe later", () => onAction("undecided")]);
  items.push(["eye", item.action === "watched" ? "Change rating" : "Mark watched & rate", () => onMore("rate")]);
  items.push(["send", "Recommend to a friend", () => onMore("friend")]);
  items.push(["plus", "Add to shared list", () => onMore("list")]);
  items.push(["calendar", "Plan watch party", () => onMore("party")]);
  if (item.action !== "rejected") items.push(["x", "Not for me", () => onAction("rejected")]);
  items.push(["trash", "Remove", () => onAction("remove")]);

  return (
    <div className={`list-row${pinned ? " pinned" : ""}`} ref={ref}>
      <div className="thumb" onClick={onOpen}>
        <Poster media={item} fontSize={5} />
      </div>
      <div className="grow" onClick={onOpen} style={{ cursor: "pointer", minWidth: 0 }}>
        <div className="row" style={{ gap: 6 }}>
          {pinned && <span style={{ color: "var(--star)" }}>★</span>}
          <div className="title ellipsis">{item.title}</div>
        </div>
        <div className="small muted ellipsis">
          {item.year} · {item.type === "tv" ? "Series" : "Movie"} · {item.runtime_label}
        </div>
        <div className="row wrap" style={{ gap: 5, marginTop: 5 }}>
          {item.rating ? (
            <span className="tag gold">{"★".repeat(item.rating)}</span>
          ) : (
            (item.reasons?.length ? item.reasons : item.genres.slice(0, 2)).slice(0, 2).map((g) => (
              <span key={g} className="tag">
                {g}
              </span>
            ))
          )}
          {item.providers[0] && <span className="tag blue">{item.providers[0]}</span>}
          {item.from_session && <span className="tag violet">matched</span>}
        </div>
      </div>
      <div className="stack" style={{ gap: 6 }}>
        <button className="icon-btn" onClick={() => onMore("watch")} aria-label={`Where to watch ${item.title}`}>
          <Icon name="play" size={18} />
        </button>
        <button className="icon-btn" onClick={() => setMenu((v) => !v)} aria-label="More actions" aria-expanded={menu}>
          <Icon name="more" size={18} />
        </button>
      </div>
      {menu && (
        <div className="menu" role="menu">
          {items.map(([icon, label, run]) => (
            <button
              key={label}
              role="menuitem"
              onClick={() => {
                setMenu(false);
                run();
              }}
            >
              <Icon name={icon} size={16} /> {label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function Lists() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("itinerary");
  const [sort, setSort] = useState("added");
  const [historyKind, setHistoryKind] = useState("watched");
  const [info, setInfo] = useState<string | null>(null);
  const [sheet, setSheet] = useState<{ kind: "watch" | "friend" | "list" | "party" | "rate"; item: ListItemCard } | null>(null);
  const [tonight, setTonight] = useState(false);
  const [rating, setRating] = useState<number | null>(null);
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: Infinity });

  const wl = useQuery({ queryKey: ["lists", "watchlist", sort], queryFn: () => api.watchlist(sort), enabled: tab === "itinerary" });
  const maybe = useQuery({ queryKey: ["lists", "undecided"], queryFn: api.undecided });
  const hist = useQuery({ queryKey: ["lists", "history", historyKind], queryFn: () => api.history(historyKind), enabled: tab === "history" });
  const counts = useQuery({ queryKey: ["lists", "counts"], queryFn: api.counts });

  const act = async (item: ListItemCard, action: ListAction, r?: number) => {
    await api.setListAction(item.media_id, action, r);
    qc.invalidateQueries({ queryKey: ["lists"] });
    const verb: Record<string, string> = {
      must_visit: "Pinned ⭐",
      watchlist: "Moved to Watch List",
      undecided: "Parked in Maybe Later",
      rejected: "Marked not for you",
      watched: "Thanks — your ratings tune your deck",
      remove: "Removed",
    };
    toast(`${item.title}: ${verb[action] ?? "Updated"}`, {
      label: "Undo",
      run: async () => {
        await api.undo();
        qc.invalidateQueries({ queryKey: ["lists"] });
      },
    });
  };

  const render = (items: ListItemCard[] | undefined, pinned = false) =>
    items && items.length > 0 && (
      <div className="list-grid">
        {items.map((it) => (
      <Row
        key={it.media_id}
        item={it}
        pinned={pinned}
        onOpen={() => setInfo(it.media_id)}
        onAction={(a, r) => act(it, a, r)}
        onMore={(kind) => {
          setRating(it.rating);
          setSheet({ kind, item: it });
        }}
      />
        ))}
      </div>
    );

  const c = counts.data ?? {};
  const itineraryCount = (c.must_visit ?? 0) + (c.watchlist ?? 0);

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="h1">Your lists</h1>
        <button className="btn sm primary" onClick={() => setTonight(true)}>
          <Icon name="dice" size={16} /> Decide for me
        </button>
      </div>

      <div className="segmented" role="tablist">
        <button className={tab === "itinerary" ? "active" : ""} onClick={() => setTab("itinerary")} role="tab">
          Itinerary <span className="count">{itineraryCount}</span>
        </button>
        <button className={tab === "maybe" ? "active" : ""} onClick={() => setTab("maybe")} role="tab">
          Maybe later <span className="count">{c.undecided ?? 0}</span>
        </button>
        <button className={tab === "history" ? "active" : ""} onClick={() => setTab("history")} role="tab">
          History
        </button>
      </div>

      {tab === "itinerary" && (
        <div className="stack" style={{ marginTop: 14 }}>
          <div className="row between">
            <div className="small muted">
              {wl.data && wl.data.movie_minutes_total > 0 && <>≈ {fmtMinutes(wl.data.movie_minutes_total)} of movies queued</>}
            </div>
            <select className="select" style={{ width: "auto", padding: "8px 12px" }} value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort">
              <option value="added">Recently added</option>
              <option value="match">Best match</option>
              <option value="runtime">Shortest first</option>
              <option value="year">Newest</option>
              <option value="title">A–Z</option>
            </select>
          </div>
          {wl.data && wl.data.must_visit.length > 0 && (
            <>
              <div className="h3" style={{ marginTop: 6 }}>⭐ Must visit</div>
              {render(wl.data.must_visit, true)}
            </>
          )}
          {wl.data && wl.data.watchlist.length > 0 && (
            <>
              <div className="h3" style={{ marginTop: 10 }}>Watch list</div>
              {render(wl.data.watchlist)}
            </>
          )}
          {wl.data && !wl.data.must_visit.length && !wl.data.watchlist.length && (
            <div className="empty">
              <div className="big">🗺️</div>
              <p>Your itinerary is empty. Swipe right on titles you want to watch — long-press to pin the must-sees.</p>
            </div>
          )}
        </div>
      )}

      {tab === "maybe" && (
        <div className="stack" style={{ marginTop: 14 }}>
          <p className="small muted" style={{ margin: 0 }}>
            Parked titles drift back into your deck after a few days. Promote or drop them here any time.
          </p>
          {render(maybe.data?.items)}
          {maybe.data?.items.length === 0 && (
            <div className="empty">
              <div className="big">🅿️</div>
              <p>Nothing parked. Swipe down on a card to save it for later.</p>
            </div>
          )}
        </div>
      )}

      {tab === "history" && (
        <div className="stack" style={{ marginTop: 14 }}>
          <div className="chips">
            {[
              ["watched", "Watched"],
              ["liked", "Loved"],
              ["rejected", "Not for me"],
            ].map(([k, l]) => (
              <button key={k} className={`chip${historyKind === k ? " active" : ""}`} onClick={() => setHistoryKind(k)}>
                {l} <span className="count">{c[k] ?? 0}</span>
              </button>
            ))}
          </div>
          {historyKind === "rejected" && (
            <p className="small muted" style={{ margin: 0 }}>
              Changed your mind? Rejected titles stay out of your deck for 60 days — you can rescue them here.
            </p>
          )}
          {render(hist.data?.items)}
          {hist.data?.items.length === 0 && <div className="empty">Nothing here yet.</div>}
        </div>
      )}

      <InfoPanel mediaId={info} onClose={() => setInfo(null)} onOpenOther={setInfo} />
      <WatchSheet media={sheet?.kind === "watch" ? sheet.item : null} onClose={() => setSheet(null)} />
      <RecommendSheet media={sheet?.kind === "friend" ? (sheet.item as Media) : null} onClose={() => setSheet(null)} />
      <AddToListSheet media={sheet?.kind === "list" ? (sheet.item as Media) : null} onClose={() => setSheet(null)} />
      <PartySheet media={sheet?.kind === "party" ? (sheet.item as Media) : null} onClose={() => setSheet(null)} />
      <Sheet open={sheet?.kind === "rate"} onClose={() => setSheet(null)} title={`How was ${sheet?.item.title ?? ""}?`}>
        <div className="stack" style={{ alignItems: "center" }}>
          <RatingStars value={rating} onChange={setRating} />
          <p className="small muted" style={{ textAlign: "center", margin: 0 }}>
            Ratings tell the recommender what actually landed — 4–5★ pulls similar titles closer, 1–2★ pushes them away.
          </p>
          <button
            className="btn primary block"
            disabled={!rating}
            onClick={() => {
              if (sheet) act(sheet.item, "watched", rating ?? undefined);
              setSheet(null);
            }}
          >
            Save rating
          </button>
        </div>
      </Sheet>
      <TonightPickSheet
        open={tonight}
        onClose={() => setTonight(false)}
        meta={meta.data}
        onOpen={(id) => {
          setTonight(false);
          setInfo(id);
        }}
      />
    </div>
  );
}
