import {
  animate,
  motion,
  useMotionValue,
  useMotionValueEvent,
  useTransform,
  type PanInfo,
} from "framer-motion";
import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState, type ReactNode } from "react";
import type { FeedCard } from "../api/types";
import { Icon } from "./Icon";
import { Poster } from "./Poster";

/** "seen" (✓ button / W key) = already watched: no gesture, flies out right with its own stamp. */
export type Direction = "right" | "left" | "up" | "down" | "star" | "seen";
export type DeckHandle = { swipe: (dir: Direction) => void };

const SWIPE_X = 110;
const SWIPE_Y = 110;
const VELOCITY = 650;
const LONG_PRESS_MS = 450;
const MOVE_CANCEL = 10;

function haptic(ms = 12) {
  try {
    navigator.vibrate?.(ms);
  } catch {
    /* unsupported */
  }
}

type CardProps = {
  card: FeedCard;
  depth: number;
  blind: boolean;
  onSwipe: (dir: Direction) => void;
  onTap: () => void;
  controlRef?: (fn: ((dir: Direction) => void) | null) => void;
};

function SwipeCard({ card, depth, blind, onSwipe, onTap, controlRef }: CardProps) {
  const isTop = depth === 0;
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const press = useMotionValue(0);
  const rotate = useTransform(x, [-320, 320], [-16, 16]);
  const yes = useTransform(x, [25, SWIPE_X], [0, 1]);
  const no = useTransform(x, [-SWIPE_X, -25], [1, 0]);
  const maybe = useTransform(y, [25, SWIPE_Y], [0, 1]);
  const watch = useTransform(y, [-SWIPE_Y, -25], [1, 0]);
  const ringOffset = useTransform(press, [0, 1], [251, 0]);
  const [starred, setStarred] = useState(false);
  const [seen, setSeen] = useState(false);
  const [pressing, setPressing] = useState(false);
  const leaving = useRef(false);
  const pressTimer = useRef<number | null>(null);
  const pressAnim = useRef<ReturnType<typeof animate> | null>(null);
  const longPressed = useRef(false);
  const start = useRef<{ x: number; y: number } | null>(null);

  const cancelPress = useCallback(() => {
    if (pressTimer.current) window.clearTimeout(pressTimer.current);
    pressTimer.current = null;
    pressAnim.current?.stop();
    press.set(0);
    setPressing(false);
  }, [press]);

  const fling = useCallback(
    async (dir: Direction) => {
      if (leaving.current) return;
      haptic(dir === "star" ? 30 : 12);
      if (dir === "up") {
        // Watch now = intent only: nudge up, spring back, keep the card.
        await animate(y, -90, { duration: 0.16 });
        animate(y, 0, { type: "spring", stiffness: 380, damping: 24 });
        onSwipe("up");
        return;
      }
      leaving.current = true;
      const w = window.innerWidth + 260;
      const h = window.innerHeight + 200;
      if (dir === "star") {
        setStarred(true);
        await animate(y, -h, { duration: 0.42, ease: [0.4, 0, 0.2, 1] });
      } else if (dir === "down") {
        await animate(y, h, { duration: 0.34, ease: "easeIn" });
      } else {
        if (dir === "seen") setSeen(true);
        const sign = dir === "left" ? -1 : 1;
        await Promise.all([
          animate(x, sign * w, { duration: 0.32, ease: "easeOut" }),
          animate(y, y.get() + 40, { duration: 0.32 }),
        ]);
      }
      onSwipe(dir);
    },
    [onSwipe, x, y],
  );

  useEffect(() => {
    if (!isTop || !controlRef) return;
    controlRef(fling);
    return () => controlRef(null);
  }, [isTop, controlRef, fling]);

  useMotionValueEvent(x, "change", (v) => {
    if (pressing && Math.abs(v) > MOVE_CANCEL) cancelPress();
  });

  const onDragEnd = (_: unknown, info: PanInfo) => {
    const { offset, velocity } = info;
    const absX = Math.abs(offset.x);
    const absY = Math.abs(offset.y);
    if (absX > absY && (absX > SWIPE_X || Math.abs(velocity.x) > VELOCITY)) {
      fling(offset.x > 0 ? "right" : "left");
    } else if (absY > absX && (absY > SWIPE_Y || Math.abs(velocity.y) > VELOCITY)) {
      if (offset.y < 0) {
        animate(x, 0, { type: "spring", stiffness: 400, damping: 30 });
        fling("up");
      } else fling("down");
    } else {
      animate(x, 0, { type: "spring", stiffness: 420, damping: 30 });
      animate(y, 0, { type: "spring", stiffness: 420, damping: 30 });
    }
  };

  const onPointerDown = (e: React.PointerEvent) => {
    if (!isTop) return;
    longPressed.current = false;
    start.current = { x: e.clientX, y: e.clientY };
    setPressing(true);
    pressAnim.current = animate(press, 1, { duration: LONG_PRESS_MS / 1000, ease: "linear" });
    pressTimer.current = window.setTimeout(() => {
      longPressed.current = true;
      setPressing(false);
      fling("star");
    }, LONG_PRESS_MS);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!start.current || !pressTimer.current) return;
    if (Math.hypot(e.clientX - start.current.x, e.clientY - start.current.y) > MOVE_CANCEL) cancelPress();
  };

  const onPointerUp = () => {
    start.current = null;
    if (pressTimer.current) cancelPress();
  };

  const showPoster = !blind;
  const meta = [card.year, card.type === "tv" ? "Series" : "Movie", card.runtime_label, card.language_name].filter(
    Boolean,
  );

  return (
    <motion.div
      className={`swipe-card${isTop ? "" : " behind"}`}
      style={{ x, y, rotate, zIndex: 10 - depth }}
      initial={{ scale: 0.92, y: 24, opacity: 0 }}
      animate={{
        scale: starred ? 1.04 : 1 - depth * 0.045,
        y: depth * 14,
        opacity: depth > 2 ? 0 : 1,
        boxShadow: starred ? "0 0 60px rgba(255,209,102,.6)" : undefined,
      }}
      transition={{ type: "spring", stiffness: 300, damping: 28 }}
      drag={isTop}
      dragMomentum={false}
      onDragEnd={onDragEnd}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      onTap={() => {
        if (!isTop || longPressed.current || leaving.current) return;
        if (Math.abs(x.get()) < 6 && Math.abs(y.get()) < 6) onTap();
      }}
      aria-hidden={!isTop}
    >
      <div className="card-poster">
        {showPoster ? (
          <Poster media={card} showTitle={false} fontSize={26} ambient="card" />
        ) : (
          <div className="blind-cover">
            <div className="q">🙈</div>
            <div className="tag violet">Blind date</div>
            <p>“{card.logline}”</p>
            <div className="card-tags" style={{ justifyContent: "center" }}>
              {card.genres.slice(0, 3).map((g) => (
                <span key={g} className="tag">
                  {g}
                </span>
              ))}
              <span className="tag">{card.type === "tv" ? "Series" : "Movie"}</span>
            </div>
          </div>
        )}
      </div>
      {showPoster && <div className="card-shade" />}

      <div className="card-top">
        {card.match_percent != null ? (
          <span className="match-pill">
            <span className="ring" />
            {card.match_percent}% {card.group_fit != null ? "group fit" : "match"}
          </span>
        ) : (
          <span className="match-pill">✨ Discover</span>
        )}
        <div className="stack" style={{ gap: 6, alignItems: "flex-end" }}>
          {card.availability && <span className="tag blue">{card.availability}</span>}
          {card.explore && <span className="tag violet">New territory</span>}
          {card.resurfaced && <span className="tag gold">Maybe later</span>}
        </div>
      </div>

      {showPoster && (
        <div className="card-body">
          {card.because && (
            <div className="because">
              <Icon name="sparkles" size={15} /> {card.because}
            </div>
          )}
          <h2 className="card-title">{card.title}</h2>
          <div className="card-meta">
            {meta.map((m) => (
              <span key={String(m)}>{m}</span>
            ))}
          </div>
          <p className="card-logline">{card.logline}</p>
          <div className="card-tags">
            {(card.reasons.length ? card.reasons : card.genres.slice(0, 3)).map((r) => (
              <span key={r} className="tag">
                {r}
              </span>
            ))}
            {card.friends_saved_count > 0 && (
              <span className="tag green">
                👥 {card.friends_saved_count === 1 ? `${card.friends_saved[0]} saved this` : `${card.friends_saved_count} friends saved`}
              </span>
            )}
          </div>
        </div>
      )}

      {isTop && (
        <>
          <motion.div className="stamp yes" style={{ opacity: yes }}>
            Watch list
          </motion.div>
          <motion.div className="stamp no" style={{ opacity: no }}>
            Nope
          </motion.div>
          <motion.div className="stamp maybe" style={{ opacity: maybe }}>
            Maybe later
          </motion.div>
          <motion.div className="stamp watch" style={{ opacity: watch }}>
            Where to watch?
          </motion.div>
          {starred && <div className="stamp star">⭐ Must visit</div>}
          {seen && <div className="stamp seen">✓ Already watched</div>}
          {pressing && (
            <svg className="press-ring" viewBox="0 0 92 92">
              <motion.circle cx="46" cy="46" r="40" strokeDasharray="251" style={{ strokeDashoffset: ringOffset }} />
            </svg>
          )}
        </>
      )}
    </motion.div>
  );
}

type DeckProps = {
  cards: FeedCard[];
  blind?: boolean;
  loading?: boolean;
  empty?: ReactNode;
  onSwipe: (card: FeedCard, dir: Direction) => void;
  onTap: (card: FeedCard) => void;
};

export const SwipeDeck = forwardRef<DeckHandle, DeckProps>(function SwipeDeck(
  { cards, blind = false, loading, empty, onSwipe, onTap },
  ref,
) {
  const control = useRef<((dir: Direction) => void) | null>(null);
  const setControl = useCallback((fn: ((dir: Direction) => void) | null) => {
    control.current = fn;
  }, []);
  useImperativeHandle(ref, () => ({ swipe: (dir) => control.current?.(dir) }), []);

  const visible = cards.slice(0, 3);
  return (
    <div className="deck-wrap">
      <div className="deck">
        {visible.length === 0 &&
          (loading ? <div className="swipe-card skeleton" style={{ cursor: "default" }} /> : <div className="deck-empty">{empty}</div>)}
        {visible
          .map((card, i) => (
            <SwipeCard
              key={card.media_id}
              card={card}
              depth={i}
              blind={blind}
              onSwipe={(dir) => onSwipe(card, dir)}
              onTap={() => onTap(card)}
              controlRef={i === 0 ? setControl : undefined}
            />
          ))
          .reverse()}
      </div>
    </div>
  );
});

export function ActionBar({
  onAction,
  onUndo,
  canUndo,
  disabled,
}: {
  onAction: (dir: Direction) => void;
  onUndo?: () => void;
  canUndo?: boolean;
  disabled?: boolean;
}) {
  return (
    <div className="action-bar" role="toolbar" aria-label="Swipe actions">
      {onUndo && (
        <button className="action-btn sm undo" onClick={onUndo} disabled={!canUndo} aria-label="Undo last swipe (Z)" title="Undo (Z)">
          <Icon name="undo" size={18} />
        </button>
      )}
      <button className="action-btn lg no" onClick={() => onAction("left")} disabled={disabled} aria-label="Not for me (←)" title="Not for me (←)">
        <Icon name="x" size={28} strokeWidth={2.6} />
      </button>
      <button className="action-btn maybe" onClick={() => onAction("down")} disabled={disabled} aria-label="Maybe later (↓)" title="Maybe later (↓)">
        <Icon name="clock" size={22} />
      </button>
      <button className="action-btn star" onClick={() => onAction("star")} disabled={disabled} aria-label="Must visit (S or long-press)" title="Must visit (S / long-press)">
        <Icon name="star" size={22} solid />
      </button>
      <button className="action-btn watch" onClick={() => onAction("up")} disabled={disabled} aria-label="Where to watch (↑)" title="Where to watch (↑)">
        <Icon name="play" size={22} />
      </button>
      <button className="action-btn lg yes" onClick={() => onAction("seen")} disabled={disabled} aria-label="Already watched (W)" title="Already watched (W) — improves recommendations, not added to your Watch List">
        <Icon name="check" size={28} strokeWidth={2.8} />
      </button>
    </div>
  );
}

export const DIR_TO_ACTION = {
  right: "watchlist",
  seen: "watched",
  left: "rejected",
  down: "undecided",
  star: "must_visit",
  up: "watch_intent",
} as const;

export function useDeckKeys(handler: (key: Direction | "undo" | "info") => void, enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) return;
      if (document.querySelector(".sheet-backdrop")) return;
      const map: Record<string, Direction | "undo" | "info"> = {
        ArrowRight: "right",
        ArrowLeft: "left",
        ArrowUp: "up",
        ArrowDown: "down",
        s: "star",
        S: "star",
        w: "seen",
        W: "seen",
        z: "undo",
        Z: "undo",
        Backspace: "undo",
        " ": "info",
        Enter: "info",
      };
      const action = map[e.key];
      if (action) {
        e.preventDefault();
        handler(action);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handler, enabled]);
}
