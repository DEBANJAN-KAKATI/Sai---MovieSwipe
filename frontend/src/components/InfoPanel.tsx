import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { imgSrc } from "../api/base";
import { api } from "../api/client";
import type { ListAction, Media } from "../api/types";
import { toast } from "../store";
import { Icon } from "./Icon";
import { AddToListSheet, PartySheet, RecommendSheet, useSpoilerShield, WatchOptions } from "./MediaSheets";
import { Poster } from "./Poster";
import { Sheet } from "./Sheet";
import type { Direction } from "./SwipeDeck";

type Props = {
  mediaId: string | null;
  onClose: () => void;
  /** When opened from the deck, actions swipe the top card instead of editing lists directly. */
  onDeckAction?: (dir: Direction) => void;
  onOpenOther?: (id: string) => void;
};

const ACTION_LABEL: Record<string, string> = {
  watchlist: "On your Watch List",
  must_visit: "Pinned as Must Visit",
  undecided: "In Maybe Later",
  rejected: "Marked not for you",
  liked: "You loved this",
  watched: "Watched",
};

function QA({ q, icon, children }: { q: string; icon: string; children: React.ReactNode }) {
  return (
    <div className="qa">
      <div className="qa-q">
        <Icon name={icon} size={14} /> {q}
      </div>
      <div className="qa-a">{children}</div>
    </div>
  );
}

type DetailsProps = {
  mediaId: string;
  /** Called by the action buttons. Return value is ignored. */
  onAction: (dir: Direction, listAction: ListAction) => void;
  onOpenOther?: (id: string) => void;
  onClose?: () => void;
  /** Side-column version on desktop: no close button, no sticky footer, no impression logging. */
  embedded?: boolean;
};

export function MediaDetails({ mediaId, onAction, onOpenOther, onClose, embedded = false }: DetailsProps) {
  const q = useQuery({
    queryKey: ["media", mediaId, embedded ? "pane" : "sheet"],
    queryFn: () => api.media(mediaId, !embedded),
  });
  const shield = useSpoilerShield();
  const [revealed, setRevealed] = useState(false);
  const [showTrailer, setShowTrailer] = useState(false);
  const [sheet, setSheet] = useState<null | "friend" | "list" | "party">(null);
  const d = q.data;

  useEffect(() => {
    setRevealed(false);
    setShowTrailer(false);
  }, [mediaId]);

  if (!d) {
    return (
      <div className="stack">
        <div className="skeleton" style={{ height: 210, borderRadius: 20 }} />
        <div className="skeleton" style={{ height: 18, width: "60%", borderRadius: 8 }} />
        <div className="skeleton" style={{ height: 80, borderRadius: 12 }} />
      </div>
    );
  }
  const act = onAction;

  return (
    <div className={embedded ? "details embedded" : "details"}>
        <div className="info-hero">
          {d.backdrop_url ? (
            <img src={imgSrc(d.backdrop_url)} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          ) : (
            <Poster media={d} showTitle={false} fontSize={16} ambient="hero" />
          )}
          <div className="card-shade" />
          <div className="info-hero-text">
            <div className="row wrap" style={{ gap: 6, marginBottom: 6 }}>
              {d.qa.match && <span className="tag green">{d.qa.match.match_percent}% match</span>}
              {d.certification && <span className="tag">{d.certification}</span>}
              {d.vote_average && <span className="tag gold">★ {d.vote_average.toFixed(1)}</span>}
              <span className="tag">{d.language_name}</span>
            </div>
            <div className="card-title" style={{ fontSize: 30, margin: 0 }}>
              {d.title}
            </div>
          </div>
          {onClose && (
            <button className="icon-btn" onClick={onClose} aria-label="Close" style={{ position: "absolute", top: 10, right: 10 }}>
              <Icon name="x" size={18} />
            </button>
          )}
        </div>

        {d.image_source && (
          <a className="tiny faint" href={d.image_source} target="_blank" rel="noreferrer noopener" style={{ display: "block", margin: "-8px 2px 10px" }}>
            Artwork: {d.image_source.includes("tvmaze.com") ? "TVmaze" : "Wikipedia"}
          </a>
        )}
        <div className="row" style={{ gap: 8, marginBottom: 12 }}>
          <button className="btn sm grow" onClick={() => setSheet("friend")}>
            <Icon name="send" size={15} /> Recommend
          </button>
          <button className="btn sm grow" onClick={() => setSheet("list")}>
            <Icon name="plus" size={15} /> Shared list
          </button>
          <button className="btn sm grow" onClick={() => setSheet("party")}>
            <Icon name="calendar" size={15} /> Party
          </button>
        </div>

        {d.your_action && (
          <div className="row" style={{ marginBottom: 10 }}>
            <span className="tag gold">
              {ACTION_LABEL[d.your_action.action] ?? d.your_action.action}
              {d.your_action.rating ? ` · ${"★".repeat(d.your_action.rating)}` : ""}
            </span>
          </div>
        )}

        <QA q="What is it about?" icon="info">
          {shield && !revealed && d.your_action?.action !== "watched" ? (
            <>
              {d.logline}{" "}
              <button className="btn sm ghost" onClick={() => setRevealed(true)}>
                <Icon name="eye" size={14} /> Spoiler shield on — show more
              </button>
            </>
          ) : (
            d.qa.about
          )}
          {d.tagline && <div className="small faint" style={{ marginTop: 6, fontStyle: "italic" }}>“{d.tagline}”</div>}
        </QA>

        <QA q="Movie or series? How long?" icon="clock">
          {d.qa.format}
          <div className="small muted" style={{ marginTop: 4 }}>
            {d.year} · {d.genres.join(", ")}
          </div>
        </QA>

        <QA q="Who's in it?" icon="users">
          {d.qa.cast.join(", ")}
          {d.qa.creator && (
            <div className="small muted" style={{ marginTop: 4 }}>
              {d.qa.creator_label} {d.qa.creator}
            </div>
          )}
        </QA>

        <QA q="Trailer" icon="play">
          {d.qa.trailer.embed_url && showTrailer ? (
            <iframe
              className="trailer-frame"
              src={`${d.qa.trailer.embed_url}?autoplay=1`}
              title={`${d.title} trailer`}
              allow="autoplay; encrypted-media; picture-in-picture"
              allowFullScreen
            />
          ) : d.qa.trailer.embed_url ? (
            <button className="btn" onClick={() => setShowTrailer(true)}>
              <Icon name="play" size={18} /> Play trailer
            </button>
          ) : (
            <a className="btn" href={d.qa.trailer.search_url} target="_blank" rel="noreferrer noopener">
              <Icon name="play" size={18} /> Find the trailer on YouTube
            </a>
          )}
        </QA>

        <QA q="Similar to things I like?" icon="sparkles">
          {d.qa.match ? (
            <>
              <div style={{ fontWeight: 600 }}>
                {d.qa.match.match_percent}% match{d.qa.match.reasons.length ? ` — ${d.qa.match.reasons.join(", ")}` : ""}
              </div>
              {d.qa.match.because && <div className="small muted">{d.qa.match.because}</div>}
            </>
          ) : (
            <span className="muted">Swipe a few more titles and we'll tell you how well this fits your taste.</span>
          )}
          {d.friends_saved.length > 0 && (
            <div className="small" style={{ marginTop: 6, color: "var(--yes)" }}>
              👥 Saved by {d.friends_saved.join(", ")}
            </div>
          )}
          {d.similar.length > 0 && (
            <div className="scroller" style={{ marginTop: 12 }}>
              {d.similar.map((s) => (
                <button key={s.media_id} className="mini-card" onClick={() => onOpenOther?.(s.media_id)}>
                  <div className="mini-poster">
                    <Poster media={s} fontSize={8} />
                  </div>
                  <div className="t">{s.title}</div>
                  <div className="tiny faint">{s.similarity_percent}% similar</div>
                </button>
              ))}
            </div>
          )}
        </QA>

        <QA q="Content notes" icon="eyeOff">
          {d.qa.certification_label && <div className="small muted">{d.qa.certification_label}</div>}
          {d.qa.content_notes.length ? (
            <div className="chips wrap" style={{ marginTop: 6 }}>
              {d.qa.content_notes.map((n) => (
                <span key={n.flag} className="chip static">
                  {n.label}
                </span>
              ))}
            </div>
          ) : (
            <span className="muted">No major content flags.</span>
          )}
        </QA>

        <QA q="Where can I watch it in India?" icon="globe">
          <WatchOptions info={d.qa.where_to_watch} title={d.title} />
        </QA>

        <div className={embedded ? "info-actions pane-actions" : "sticky-footer info-actions"}>
          <button className="btn" style={{ color: "var(--no)" }} onClick={() => act("left", "rejected")} aria-label="Not for me">
            <Icon name="x" size={18} />
          </button>
          <button className="btn" style={{ color: "var(--maybe)" }} onClick={() => act("down", "undecided")} aria-label="Maybe later">
            <Icon name="clock" size={18} />
          </button>
          <button className="btn" style={{ color: "var(--star)" }} onClick={() => act("star", "must_visit")} aria-label="Must visit">
            <Icon name="star" size={18} solid />
          </button>
          <button className="btn" style={{ color: "#c4b2ff" }} onClick={() => act("seen", "watched")} aria-label="Already watched">
            <Icon name="check" size={18} />
          </button>
          <button className="btn primary grow" onClick={() => act("right", "watchlist")}>
            <Icon name="plus" size={18} /> Watch List
          </button>
        </div>
      <RecommendSheet media={sheet === "friend" ? (d as Media) : null} onClose={() => setSheet(null)} />
      <AddToListSheet media={sheet === "list" ? (d as Media) : null} onClose={() => setSheet(null)} />
      <PartySheet media={sheet === "party" ? (d as Media) : null} onClose={() => setSheet(null)} />
    </div>
  );
}

export function InfoPanel({ mediaId, onClose, onDeckAction, onOpenOther }: Props) {
  const qc = useQueryClient();
  const act = async (dir: Direction, listAction: ListAction) => {
    if (onDeckAction) {
      onClose();
      setTimeout(() => onDeckAction(dir), 180);
      return;
    }
    await api.setListAction(mediaId!, listAction);
    qc.invalidateQueries({ queryKey: ["media", mediaId] });
    qc.invalidateQueries({ queryKey: ["lists"] });
    toast(ACTION_LABEL[listAction] ?? "Saved");
  };
  return (
    <Sheet open={!!mediaId} onClose={onClose} label="Title details" wide>
      {mediaId && <MediaDetails key={mediaId} mediaId={mediaId} onAction={act} onOpenOther={onOpenOther} onClose={onClose} />}
    </Sheet>
  );
}
