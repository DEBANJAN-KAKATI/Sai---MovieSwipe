import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { MatchInfo, Media, Meta, TonightPick } from "../api/types";
import { Icon } from "./Icon";
import { Poster } from "./Poster";
import { Sheet } from "./Sheet";

export function RatingStars({ value, onChange }: { value: number | null; onChange: (v: number) => void }) {
  return (
    <div className="stars" role="radiogroup" aria-label="Rating">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          className={value && n <= value ? "on" : ""}
          onClick={() => onChange(n)}
          aria-label={`${n} star${n > 1 ? "s" : ""}`}
          role="radio"
          aria-checked={value === n}
        >
          ★
        </button>
      ))}
    </div>
  );
}

const CONFETTI_COLORS = ["#ff4f6d", "#ff8a3d", "#ffd166", "#2fdc95", "#4fa8ff", "#9d7bff"];

export function MatchCelebration({
  match,
  onClose,
  onWatch,
  onParty,
}: {
  match: MatchInfo | null;
  onClose: () => void;
  onWatch: (m: Media) => void;
  onParty: (m: Media) => void;
}) {
  const bits = useMemo(
    () =>
      Array.from({ length: 60 }, (_, i) => ({
        left: Math.random() * 100,
        delay: Math.random() * 0.6,
        dur: 2.2 + Math.random() * 1.6,
        color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
        rot: Math.random() * 720 - 360,
      })),
    [match?.match_id],
  );
  if (!match) return null;
  const m = match.media;
  return (
    <div className="celebrate" role="dialog" aria-label="It's a match" onClick={onClose}>
      {bits.map((b, i) => (
        <motion.div
          key={i}
          className="confetti"
          style={{ left: `${b.left}%`, background: b.color }}
          initial={{ y: -20, rotate: 0, opacity: 1 }}
          animate={{ y: "105vh", rotate: b.rot, opacity: [1, 1, 0.6] }}
          transition={{ duration: b.dur, delay: b.delay, ease: "easeIn" }}
        />
      ))}
      <motion.div
        className="celebrate-inner"
        initial={{ scale: 0.7, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: "spring", stiffness: 260, damping: 18 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="poster-stack">
          {[-1, 0, 1].map((k) => (
            <motion.div
              key={k}
              className="ps"
              initial={{ rotate: 0, x: 0 }}
              animate={{ rotate: k * 9, x: k * 46, y: Math.abs(k) * 10 }}
              transition={{ delay: 0.15, type: "spring", stiffness: 200, damping: 16 }}
              style={{ zIndex: k === 0 ? 3 : 1, fontSize: 11 }}
            >
              <Poster media={m} fontSize={11} />
            </motion.div>
          ))}
        </div>
        <h2>{match.super_match ? "Super match!" : "It's a match!"}</h2>
        <p className="muted" style={{ margin: "0 0 4px" }}>
          {match.participants.join(" & ")} {match.participants.length === 2 ? "both" : "all"} want to watch
        </p>
        <div className="h2" style={{ fontSize: 22, marginBottom: 18 }}>
          {m.title}
        </div>
        <div className="stack" style={{ gap: 8 }}>
          <button className="btn primary block lg" onClick={() => onWatch(m)}>
            <Icon name="play" size={18} /> Where to watch
          </button>
          <div className="row">
            <button className="btn grow" onClick={() => onParty(m)}>
              <Icon name="calendar" size={18} /> Plan watch party
            </button>
            <button className="btn grow" onClick={onClose}>
              Keep swiping
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

const TIME_OPTIONS = [
  { label: "45 min", value: 45 },
  { label: "1½ hrs", value: 90 },
  { label: "2 hrs", value: 120 },
  { label: "3 hrs", value: 180 },
  { label: "All night", value: 0 },
];

export function TonightPickSheet({
  open,
  onClose,
  sessionId,
  meta,
  onOpen,
}: {
  open: boolean;
  onClose: () => void;
  sessionId?: string | null;
  meta?: Meta;
  onOpen: (id: string) => void;
}) {
  const [minutes, setMinutes] = useState(120);
  const [mood, setMood] = useState<string | null>(null);
  const [spin, setSpin] = useState(0);
  const [rolling, setRolling] = useState(false);
  const [shown, setShown] = useState<string>("");
  const q = useQuery({
    queryKey: ["tonight", minutes, mood, sessionId, spin],
    queryFn: () => api.tonight({ minutes: minutes || null, mood, session_id: sessionId }),
    enabled: open && spin > 0,
  });
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (!open) {
      setSpin(0);
      setShown("");
    }
  }, [open]);

  // Slot-machine reveal: cycle through candidate titles before landing on the pick.
  useEffect(() => {
    const data: TonightPick | undefined = q.data;
    if (!data?.pick || spin === 0) return;
    const pool = [data.pick, ...data.alternates].map((m) => m.title);
    let i = 0;
    setRolling(true);
    const tick = () => {
      setShown(pool[i % pool.length]);
      i++;
      if (i < 14) timer.current = window.setTimeout(tick, 50 + i * 12);
      else {
        setShown(data.pick!.title);
        setRolling(false);
      }
    };
    tick();
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [q.data, spin]);

  const pick = q.data?.pick;
  return (
    <Sheet open={open} onClose={onClose} title="🎲 Decide for me">
      <div className="stack">
        <div>
          <span className="label">How much time have you got?</span>
          <div className="chips wrap">
            {TIME_OPTIONS.map((t) => (
              <button key={t.value} className={`chip${minutes === t.value ? " active" : ""}`} onClick={() => setMinutes(t.value)}>
                {t.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <span className="label">Mood (optional)</span>
          <div className="chips wrap">
            {meta?.moods.map((m) => (
              <button key={m.key} className={`chip${mood === m.key ? " active" : ""}`} onClick={() => setMood(mood === m.key ? null : m.key)}>
                {m.emoji} {m.label}
              </button>
            ))}
          </div>
        </div>
        <button className="btn primary block lg" onClick={() => setSpin((s) => s + 1)} disabled={rolling}>
          <Icon name="dice" size={20} /> {spin ? "Spin again" : `Pick from ${sessionId ? "our matches" : "my Watch List"}`}
        </button>
        {spin > 0 && (
          <div className="panel" style={{ textAlign: "center" }}>
            <div className="slot">{shown || "…"}</div>
            {!rolling && pick && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="stack" style={{ marginTop: 12 }}>
                <div className="row" style={{ justifyContent: "center" }}>
                  <div className="thumb" style={{ width: 90, height: 134 }} onClick={() => onOpen(pick.media_id)}>
                    <Poster media={pick} fontSize={8} />
                  </div>
                </div>
                <div className="small muted">
                  {pick.year} · {pick.runtime_label} · from {q.data?.source}
                </div>
                <div className="chips wrap" style={{ justifyContent: "center" }}>
                  {(q.data?.reasons ?? []).map((r) => (
                    <span key={r} className="chip static">
                      {r}
                    </span>
                  ))}
                </div>
                <button className="btn block" onClick={() => onOpen(pick.media_id)}>
                  <Icon name="info" size={18} /> Details & where to watch
                </button>
                {q.data!.alternates.length > 0 && (
                  <div className="small faint">Runners-up: {q.data!.alternates.map((a) => a.title).join(" · ")}</div>
                )}
              </motion.div>
            )}
            {!rolling && q.data && !pick && <p className="muted">Nothing to pick from yet — swipe right on a few titles first.</p>}
          </div>
        )}
      </div>
    </Sheet>
  );
}

export function SearchSheet({
  open,
  onClose,
  onPick,
  title = "Search titles, cast, keywords",
  actionLabel,
}: {
  open: boolean;
  onClose: () => void;
  onPick: (m: Media) => void;
  title?: string;
  actionLabel?: string;
}) {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 220);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => {
    if (!open) setQ("");
  }, [open]);
  const res = useQuery({
    queryKey: ["search", debounced],
    queryFn: () => api.search(debounced, 20),
    enabled: open && debounced.length > 0,
  });
  return (
    <Sheet open={open} onClose={onClose} title={title}>
      <div className="stack">
        <input
          className="input"
          autoFocus
          placeholder="Try “Mentalist”, “Tabu”, “heist”…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        {res.data?.results.map((m) => (
          <div key={m.media_id} className="list-row" style={{ cursor: "pointer" }} onClick={() => onPick(m)}>
            <div className="thumb" style={{ width: 46, height: 68 }}>
              <Poster media={m} fontSize={5} />
            </div>
            <div className="grow">
              <div className="title ellipsis">{m.title}</div>
              <div className="small muted ellipsis">
                {m.year} · {m.type === "tv" ? "Series" : "Movie"} · {m.genres.slice(0, 2).join(", ")}
              </div>
              {m.cast.length > 0 && <div className="tiny faint ellipsis">{m.cast.slice(0, 3).join(", ")}</div>}
            </div>
            {actionLabel ? <span className="btn sm">{actionLabel}</span> : <Icon name="chevron" size={18} />}
          </div>
        ))}
        {res.data && res.data.results.length === 0 && <div className="empty">No titles found for “{debounced}”.</div>}
      </div>
    </Sheet>
  );
}
