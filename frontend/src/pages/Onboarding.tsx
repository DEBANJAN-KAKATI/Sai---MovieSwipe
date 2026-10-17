import { useMutation, useQuery } from "@tanstack/react-query";
import { BrandLogo } from "../components/BrandLogo";
import { motion } from "framer-motion";
import { useState } from "react";
import { isNative } from "../api/base";
import { api } from "../api/client";
import type { Media } from "../api/types";
import { SearchSheet } from "../components/Extras";
import { Icon } from "../components/Icon";
import { Poster } from "../components/Poster";
import { ServerSettings } from "../components/ServerSettings";
import { Sheet } from "../components/Sheet";
import { toast, useAuth } from "../store";

const FAN = ["The Mentalist", "Panchayat", "Interstellar", "3 Idiots", "Dark"];

export function Welcome() {
  const setSession = useAuth((s) => s.setSession);
  const [name, setName] = useState("");
  const [loginOpen, setLoginOpen] = useState(false);
  const start = useMutation({
    mutationFn: () => api.guest(name.trim() || undefined),
    onSuccess: (r) => setSession(r.token, r.user),
    onError: (e: Error) => toast(e.message),
  });
  return (
    <div className="welcome">
      <div className="brand">
        <BrandLogo height={48} />
      </div>
      <div className="welcome-hero" aria-hidden>
        {FAN.map((t, i) => (
          <motion.div
            key={t}
            className="fan"
            initial={{ opacity: 0, y: 30, rotate: 0 }}
            animate={{ opacity: 1, y: Math.abs(i - 2) * 14, rotate: (i - 2) * 9 }}
            transition={{ delay: 0.1 + i * 0.07, type: "spring", stiffness: 160, damping: 16 }}
            style={{ zIndex: 5 - Math.abs(i - 2), left: `calc(50% - 85px + ${(i - 2) * 58}px)` }}
          >
            <Poster media={{ title: t, poster_url: null, genres: [["Crime", "Comedy", "Sci-Fi", "Comedy", "Mystery"][i]], year: null, type: "movie" }} fontSize={12} />
          </motion.div>
        ))}
      </div>
      <div>
        <h1 className="display">
          Stop scrolling.
          <br />
          <em>Start swiping.</em>
        </h1>
        <p className="muted" style={{ fontSize: 16, lineHeight: 1.5, margin: "0 0 20px" }}>
          A deck of movies & shows that learns your taste with every swipe — and finds what you <b>both</b> want to watch tonight.
        </p>
        <div className="stack">
          {isNative && <ServerSettings />}
          <input className="input" placeholder="What should we call you?" value={name} maxLength={40} onChange={(e) => setName(e.target.value)} />
          <button className="btn primary block lg" onClick={() => start.mutate()} disabled={start.isPending}>
            Get started — no sign-up needed
          </button>
          <button className="btn ghost block" onClick={() => setLoginOpen(true)}>
            I already have an account
          </button>
        </div>
      </div>
      <LoginSheet open={loginOpen} onClose={() => setLoginOpen(false)} />
    </div>
  );
}

export function LoginSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const setSession = useAuth((s) => s.setSession);
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const m = useMutation({
    mutationFn: () => api.login(login, password),
    onSuccess: (r) => {
      setSession(r.token, r.user);
      onClose();
      toast(`Welcome back, ${r.user.display_name}`);
    },
    onError: (e: Error) => toast(e.message),
  });
  return (
    <Sheet open={open} onClose={onClose} title="Log in">
      <form
        className="stack"
        onSubmit={(e) => {
          e.preventDefault();
          m.mutate();
        }}
      >
        <input className="input" placeholder="Username or email" autoComplete="username" value={login} onChange={(e) => setLogin(e.target.value)} />
        <input className="input" type="password" placeholder="Password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button className="btn primary block" disabled={!login || !password || m.isPending}>
          Log in
        </button>
      </form>
    </Sheet>
  );
}

export function Onboarding({ onDone }: { onDone: () => void }) {
  const user = useAuth((s) => s.user);
  const setUser = useAuth((s) => s.setUser);
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: Infinity });
  const tiles = useQuery({ queryKey: ["tiles"], queryFn: api.tiles, staleTime: Infinity });
  const [step, setStep] = useState(0);
  const [picked, setPicked] = useState<Media[]>([]);
  const [subs, setSubs] = useState<string[]>([]);
  const [langs, setLangs] = useState<string[]>([]);
  const [flags, setFlags] = useState<string[]>([]);
  const [maxCert, setMaxCert] = useState<string | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);

  const toggle = <T,>(arr: T[], v: T) => (arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);
  const isPicked = (id: string) => picked.some((p) => p.media_id === id);

  const finish = useMutation({
    mutationFn: async () => {
      await api.onboard({
        liked_ids: picked.map((p) => p.media_id),
        subscriptions: subs,
        languages: langs,
        content_filters: { blocked_flags: flags, max_certification: maxCert },
      });
      return api.me();
    },
    onSuccess: (me) => {
      setUser(me);
      onDone();
    },
    onError: (e: Error) => toast(e.message),
  });

  const extraPicked = picked.filter((p) => !tiles.data?.tiles.some((t) => t.media_id === p.media_id));

  return (
    <div className="page narrow onboarding" style={{ minHeight: "100dvh" }}>
      <div className="step-dots" style={{ margin: "6px 0 18px" }}>
        {[0, 1, 2].map((i) => (
          <span key={i} className={i === step ? "on" : ""} />
        ))}
      </div>

      {step === 0 && (
        <div>
          <h1 className="h1">Hi {user?.display_name ?? "there"} 👋 Pick a few you love</h1>
          <p className="muted">Choose at least 3. This seeds your taste profile so the first deck already feels like you.</p>
          <button className="btn block" style={{ margin: "6px 0 14px" }} onClick={() => setSearchOpen(true)}>
            <Icon name="search" size={18} /> Search for shows you love
          </button>
          {extraPicked.length > 0 && (
            <div className="chips wrap" style={{ marginBottom: 12 }}>
              {extraPicked.map((p) => (
                <button key={p.media_id} className="chip active" onClick={() => setPicked(picked.filter((x) => x.media_id !== p.media_id))}>
                  {p.title} ✕
                </button>
              ))}
            </div>
          )}
          <div className="tile-grid">
            {(tiles.data?.tiles ?? Array.from({ length: 12 }, () => null)).map((t, i) =>
              t ? (
                <button
                  key={t.media_id}
                  className={`tile${isPicked(t.media_id) ? " on" : ""}`}
                  onClick={() => setPicked(isPicked(t.media_id) ? picked.filter((p) => p.media_id !== t.media_id) : [...picked, t])}
                  aria-pressed={isPicked(t.media_id)}
                  aria-label={t.title}
                >
                  <Poster media={t} showTitle={false} fontSize={9} />
                  <div className="tile-label">{t.title}</div>
                  {isPicked(t.media_id) && <div className="check">✓</div>}
                </button>
              ) : (
                <div key={i} className="tile skeleton" />
              ),
            )}
          </div>
          <div className="sticky-footer">
            <button className="btn primary block lg" disabled={picked.length < 3} onClick={() => setStep(1)}>
              {picked.length < 3 ? `Pick ${3 - picked.length} more` : `Continue with ${picked.length}`}
            </button>
          </div>
        </div>
      )}

      {step === 1 && (
        <div className="stack lg">
          <div>
            <h1 className="h1">Where do you watch?</h1>
            <p className="muted">We'll flag titles that are on your services in India.</p>
          </div>
          <div className="chips wrap">
            {meta.data?.providers.map((p) => (
              <button key={p.name} className={`chip${subs.includes(p.name) ? " active" : ""}`} onClick={() => setSubs(toggle(subs, p.name))}>
                <span style={{ width: 10, height: 10, borderRadius: 3, background: p.color, display: "inline-block" }} /> {p.name}
              </button>
            ))}
          </div>
          <div>
            <div className="h3">Languages you enjoy (optional)</div>
            <div className="chips wrap">
              {meta.data?.languages.map((l) => (
                <button key={l.code} className={`chip${langs.includes(l.code) ? " active" : ""}`} onClick={() => setLangs(toggle(langs, l.code))}>
                  {l.name}
                </button>
              ))}
            </div>
          </div>
          <div className="row">
            <button className="btn" onClick={() => setStep(0)}>
              Back
            </button>
            <button className="btn primary grow" onClick={() => setStep(2)}>
              Continue
            </button>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="stack lg">
          <div>
            <h1 className="h1">Anything to keep out?</h1>
            <p className="muted">Optional. You can change these any time in your profile.</p>
          </div>
          <div>
            <div className="h3">Hide titles with</div>
            <div className="chips wrap">
              {meta.data?.content_flags.map((f) => (
                <button key={f.key} className={`chip${flags.includes(f.key) ? " active" : ""}`} onClick={() => setFlags(toggle(flags, f.key))}>
                  {f.label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <div className="h3">Maximum certification</div>
            <div className="segmented">
              {[null, "UA", "U"].map((c) => (
                <button key={String(c)} className={maxCert === c ? "active" : ""} onClick={() => setMaxCert(c)}>
                  {c === null ? "Anything" : c === "UA" ? "Up to UA 13+" : "U only"}
                </button>
              ))}
            </div>
          </div>
          <div className="row">
            <button className="btn" onClick={() => setStep(1)}>
              Back
            </button>
            <button className="btn primary grow lg" onClick={() => finish.mutate()} disabled={finish.isPending}>
              {finish.isPending ? "Building your deck…" : "Build my deck 🍿"}
            </button>
          </div>
        </div>
      )}

      <SearchSheet
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        title="Shows & movies you love"
        actionLabel="Add"
        onPick={(m) => {
          if (!isPicked(m.media_id)) setPicked([...picked, m]);
          toast(`Added ${m.title}`);
        }}
      />
    </div>
  );
}
