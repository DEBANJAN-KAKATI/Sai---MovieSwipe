import { useMutation, useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { useRef, useState } from "react";
import { getApiBase } from "../api/base";
import { api } from "../api/client";
import type { Media } from "../api/types";
import { BrandLogo } from "../components/BrandLogo";
import { Icon } from "../components/Icon";
import { Poster } from "../components/Poster";
import { toast, useAuth } from "../store";
import { LoginSheet } from "./Onboarding";

type Showcase = { posters: Media[]; catalog_size: number; language_count: number };

const GESTURES = [
  { icon: "check", color: "var(--yes)", title: "Swipe right", text: "Add it to your Watch List." },
  { icon: "x", color: "var(--no)", title: "Swipe left", text: "Not for me — you'll see less like it." },
  { icon: "clock", color: "var(--maybe)", title: "Swipe down", text: "Maybe later. It drifts back in a few days." },
  { icon: "play", color: "var(--watch)", title: "Swipe up", text: "Where can I watch this in India?" },
  { icon: "star", color: "var(--star)", title: "Long-press", text: "Must Visit — pinned to the top of your list." },
  { icon: "eye", color: "#c4b2ff", title: "✓ Already watched", text: "Teaches your taste without cluttering your list." },
];

const FEATURES = [
  { emoji: "✨", title: "Learns with every swipe", text: "Each card tells you why it's there — “Because you liked Sherlock” — and gets sharper the more you swipe." },
  { emoji: "💑", title: "Swipe together", text: "Start a duo or group session, everyone swipes the same stack, and it's a match when you agree." },
  { emoji: "🪔", title: "Made for India", text: "Bollywood to K-drama, Netflix to JioHotstar — filter by language and see what's on your subscriptions." },
  { emoji: "🎲", title: "Decide for me", text: "Tell it how much time you have and your mood; it picks from your Watch List with a slot-machine reveal." },
  { emoji: "🧬", title: "Your Taste DNA", text: "An archetype, the themes that hook you, streaks and badges — your viewing personality at a glance." },
  { emoji: "🎉", title: "Lists & watch parties", text: "Shared lists with friends, public links, and watch-party invites that drop straight into your calendar." },
];

async function getShowcase(): Promise<Showcase> {
  const res = await fetch(`${getApiBase()}/api/public/showcase`);
  if (!res.ok) throw new Error("showcase unavailable");
  return res.json();
}

function StartForm({ big = false }: { big?: boolean }) {
  const setSession = useAuth((s) => s.setSession);
  const [name, setName] = useState("");
  const start = useMutation({
    mutationFn: () => api.guest(name.trim() || undefined),
    onSuccess: (r) => setSession(r.token, r.user),
    onError: (e: Error) => toast(e.message),
  });
  return (
    <form
      className={`start-form${big ? " big" : ""}`}
      onSubmit={(e) => {
        e.preventDefault();
        start.mutate();
      }}
    >
      <input
        className="input"
        placeholder="Your first name"
        aria-label="Your first name"
        value={name}
        maxLength={40}
        onChange={(e) => setName(e.target.value)}
      />
      <button className="btn primary lg" disabled={start.isPending}>
        {start.isPending ? "Setting up…" : "Start swiping — free"}
      </button>
    </form>
  );
}

export function Landing() {
  const showcase = useQuery({ queryKey: ["showcase"], queryFn: getShowcase, staleTime: Infinity, retry: 1 });
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: Infinity });
  const [login, setLogin] = useState(false);
  const heroRef = useRef<HTMLDivElement>(null);
  const posters = showcase.data?.posters ?? [];
  const collage = posters.slice(0, 9);

  return (
    <div className="landing">
      <header className="landing-nav">
        <div className="brand">
          <BrandLogo height={46} />
        </div>
        <nav className="landing-links">
          <a href="#how">How it works</a>
          <a href="#features">Features</a>
          <a href="#together">Together</a>
        </nav>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn ghost" onClick={() => setLogin(true)}>
            Log in
          </button>
          <button
            className="btn primary nav-cta"
            onClick={() => {
              heroRef.current?.scrollIntoView({ behavior: "smooth" });
              heroRef.current?.querySelector("input")?.focus();
            }}
          >
            Get started
          </button>
        </div>
      </header>

      <section className="landing-hero" ref={heroRef}>
        <div className="hero-copy">
          <span className="eyebrow">Movies & series · built for India</span>
          <h1 className="display hero-title">
            Stop scrolling.
            <br />
            <em>Start swiping.</em>
          </h1>
          <p className="hero-sub">
            A deck of movies and shows that learns your taste with every swipe — and finds what you <b>both</b> actually
            want to watch tonight.
          </p>
          <StartForm big />
          <div className="hero-meta">
            <span>
              <Icon name="check" size={15} /> No sign-up needed
            </span>
            <span>
              <Icon name="check" size={15} /> {showcase.data?.catalog_size ?? "160+"} titles
            </span>
            <span>
              <Icon name="check" size={15} /> {showcase.data?.language_count ?? 10} languages
            </span>
            <button className="link-btn" onClick={() => setLogin(true)}>
              Already have an account? Log in
            </button>
          </div>
        </div>

        <div className="hero-art" aria-hidden>
          <div className="collage">
            {(collage.length ? collage : Array.from({ length: 9 }, () => null)).map((m, i) => (
              <motion.div
                key={m?.media_id ?? i}
                className="collage-item"
                initial={{ opacity: 0, y: 24 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.05 * i, duration: 0.5 }}
              >
                {m ? <Poster media={m} fontSize={10} eager /> : <div className="skeleton" style={{ position: "absolute", inset: 0 }} />}
              </motion.div>
            ))}
          </div>
          <motion.div className="float-pill pill-a" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.6 }}>
            <span className="ring" /> 94% match · Because you liked Dark
          </motion.div>
          <motion.div className="float-pill pill-b" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.8 }}>
            💞 It's a match! You & Aanya
          </motion.div>
        </div>
      </section>

      <section className="landing-section" id="how">
        <h2 className="section-title">Six gestures. Zero endless scrolling.</h2>
        <p className="section-sub">Every gesture has a button and a keyboard shortcut too.</p>
        <div className="gesture-grid">
          {GESTURES.map((g) => (
            <div key={g.title} className="gesture-card">
              <div className="gesture-icon" style={{ color: g.color }}>
                <Icon name={g.icon} size={22} solid />
              </div>
              <div className="h2">{g.title}</div>
              <p className="muted small" style={{ margin: "4px 0 0" }}>
                {g.text}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="landing-section" id="features">
        <h2 className="section-title">Everything you need to finally pick something.</h2>
        <div className="feature-grid">
          {FEATURES.map((f) => (
            <div key={f.title} className="feature-card">
              <div className="feature-emoji">{f.emoji}</div>
              <div className="h2">{f.title}</div>
              <p className="muted small" style={{ margin: "6px 0 0", lineHeight: 1.55 }}>
                {f.text}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="landing-section together-band" id="together">
        <div>
          <span className="eyebrow">Duo & group sessions</span>
          <h2 className="section-title" style={{ textAlign: "left" }}>
            “What do we watch?” — solved in five minutes.
          </h2>
          <ol className="steps">
            <li>Start a session and share the 7-letter code or QR.</li>
            <li>Everyone swipes the same stack, blended for all your tastes.</li>
            <li>The moment you agree, it's a match — with where to watch it.</li>
          </ol>
        </div>
        <div className="match-mock">
          <div className="match-posters">
            {posters.slice(9, 12).map((m, i) => (
              <div key={m.media_id} className="match-poster" style={{ transform: `rotate(${(i - 1) * 8}deg) translateX(${(i - 1) * 40}px)`, zIndex: i === 1 ? 2 : 1 }}>
                <Poster media={m} fontSize={9} eager />
              </div>
            ))}
          </div>
          <div className="match-title">It's a match!</div>
          <div className="muted small">You & Rohan both want to watch {posters[10]?.title ?? "this"}</div>
        </div>
      </section>

      {posters.length > 0 && (
        <section className="landing-section">
          <h2 className="section-title">Popular on sai</h2>
          <div className="poster-strip">
            {posters.map((m) => (
              <div key={m.media_id} className="strip-item">
                <div className="strip-poster">
                  <Poster media={m} fontSize={9} />
                </div>
                <div className="small" style={{ fontWeight: 600, marginTop: 6 }}>
                  {m.title}
                </div>
                <div className="tiny faint">
                  {m.year} · {m.type === "tv" ? "Series" : "Movie"}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="landing-section cta-band">
        <h2 className="section-title">Your next favourite is a few swipes away.</h2>
        <StartForm />
      </section>

      <footer className="landing-footer">
        <div className="brand" style={{ fontSize: 18 }}>
          <BrandLogo height={34} />
        </div>
        <div className="tiny faint stack" style={{ gap: 4 }}>
          {(meta.data?.disclaimers ?? []).map((d) => (
            <div key={d}>{d}</div>
          ))}
        </div>
      </footer>

      <LoginSheet open={login} onClose={() => setLogin(false)} />
    </div>
  );
}
