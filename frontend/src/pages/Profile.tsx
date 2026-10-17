import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { isNative } from "../api/base";
import { api, downloadExport } from "../api/client";
import type { Me } from "../api/types";
import { Icon } from "../components/Icon";
import { ServerSettings } from "../components/ServerSettings";
import { Sheet } from "../components/Sheet";
import { toast, useAuth } from "../store";
import { LoginSheet } from "./Onboarding";

const AVATARS = ["🍿", "🎬", "🎞️", "📽️", "🌙", "🦊", "🐼", "🐙", "🦉", "🌶️", "🪐", "🎧", "🕵️", "🚀", "☕", "🐯"];

function Toggle({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return <button className={`toggle${on ? " on" : ""}`} aria-pressed={on} aria-label={label} onClick={() => onChange(!on)} />;
}

function TasteDNA() {
  const q = useQuery({ queryKey: ["taste"], queryFn: api.tasteSummary });
  const t = q.data;
  if (!t) return <div className="skeleton" style={{ height: 180, borderRadius: 20 }} />;
  const earned = t.badges.filter((b) => b.earned).length;
  return (
    <div className="stack lg">
      <div className="archetype">
        <div className="small muted">Your Taste DNA</div>
        <div className="name">{t.archetype?.label ?? "Still forming…"}</div>
        <div className="small muted">{t.archetype?.blurb ?? "Swipe a few titles and your taste profile will appear here."}</div>
        {t.seeds.length > 0 && <div className="tiny faint" style={{ marginTop: 10 }}>Anchored by {t.seeds.slice(0, 3).join(", ")}</div>}
        <div className="row small" style={{ marginTop: 12 }}>
          <span>Personalization</span>
          <div className="progress grow">
            <div style={{ width: `${t.personalization.level}%` }} />
          </div>
          <span className="faint">{t.personalization.signals} signals</span>
        </div>
      </div>

      <div className="stat-grid">
        <div className="stat">
          <div className="v">{t.counts.swipes}</div>
          <div className="k">Swipes</div>
        </div>
        <div className="stat">
          <div className="v">🔥 {t.streak.current}</div>
          <div className="k">Day streak (best {t.streak.best})</div>
        </div>
        <div className="stat">
          <div className="v">{t.counts.matches}</div>
          <div className="k">Matches</div>
        </div>
        <div className="stat">
          <div className="v">{(t.counts.watchlist ?? 0) + (t.counts.must_visit ?? 0)}</div>
          <div className="k">Queued</div>
        </div>
        <div className="stat">
          <div className="v">{t.counts.watched}</div>
          <div className="k">Watched</div>
        </div>
        <div className="stat">
          <div className="v">{t.accept_rate ?? "–"}{t.accept_rate != null && "%"}</div>
          <div className="k">Say-yes rate</div>
        </div>
      </div>

      {t.top_genres.length > 0 && (
        <div>
          <div className="h3">Genres you gravitate to</div>
          {t.top_genres.map((g) => (
            <div key={g.name} className="bar-row">
              <span>{g.name}</span>
              <div className="bar">
                <div style={{ width: `${g.score}%` }} />
              </div>
              <span className="faint tiny">{g.score}</span>
            </div>
          ))}
          {t.avoided_genres.length > 0 && <div className="small faint">Usually skip: {t.avoided_genres.join(", ")}</div>}
        </div>
      )}

      {t.top_keywords.length > 0 && (
        <div>
          <div className="h3">Themes that hook you</div>
          <div className="cloud">
            {t.top_keywords.map((k) => (
              <span key={k.name} style={{ fontSize: 12 + k.score / 10, opacity: 0.55 + k.score / 230 }}>
                {k.name}
              </span>
            ))}
          </div>
        </div>
      )}

      {(t.languages.length > 0 || t.decades.length > 0) && (
        <div className="row wrap" style={{ alignItems: "flex-start", gap: 24 }}>
          {t.languages.length > 0 && (
            <div>
              <div className="h3">Languages</div>
              <div className="chips wrap">
                {t.languages.map((l) => (
                  <span key={l.code} className="chip static">
                    {l.name} · {l.count}
                  </span>
                ))}
              </div>
            </div>
          )}
          {t.decades.length > 0 && (
            <div>
              <div className="h3">Eras</div>
              <div className="chips wrap">
                {t.decades.map((d) => (
                  <span key={d.name} className="chip static">
                    {d.name} · {d.count}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div>
        <div className="h3">
          Badges · {earned}/{t.badges.length}
        </div>
        <div className="badge-grid">
          {t.badges.map((b) => (
            <div key={b.key} className={`badge-tile${b.earned ? "" : " locked"}`} title={b.description}>
              <div className="e">{b.emoji}</div>
              <div className="l">{b.label}</div>
              <div className="tiny faint">{b.earned ? "Earned" : `${b.progress}/${b.target}`}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function AccountSheet({ open, onClose, me }: { open: boolean; onClose: () => void; me: Me }) {
  const setSession = useAuth((s) => s.setSession);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const m = useMutation({
    mutationFn: () => api.register({ username, password, email: email || undefined, display_name: me.display_name }),
    onSuccess: (r) => {
      setSession(r.token, r.user);
      toast("Account created — your swipes are safe 🎉");
      onClose();
    },
    onError: (e: Error) => toast(e.message),
  });
  return (
    <Sheet open={open} onClose={onClose} title="Save your account">
      <form
        className="stack"
        onSubmit={(e) => {
          e.preventDefault();
          m.mutate();
        }}
      >
        <p className="small muted" style={{ margin: 0 }}>
          Keep your lists, matches and taste profile, and log in from any device. Everything you've swiped so far comes with you.
        </p>
        <input className="input" placeholder="Username" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} />
        <input className="input" type="email" placeholder="Email (optional)" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input className="input" type="password" placeholder="Password (8+ characters)" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button className="btn primary block" disabled={username.length < 3 || password.length < 8 || m.isPending}>
          Create account
        </button>
      </form>
    </Sheet>
  );
}

export function Profile() {
  const qc = useQueryClient();
  const user = useAuth((s) => s.user);
  const setUser = useAuth((s) => s.setUser);
  const signOut = useAuth((s) => s.signOut);
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: Infinity });
  const [tab, setTab] = useState<"dna" | "settings">("dna");
  const [sheet, setSheet] = useState<null | "account" | "login" | "avatar" | "import">(null);
  const [importKind, setImportKind] = useState("auto");
  const [importResult, setImportResult] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const save = useMutation({
    mutationFn: api.updateMe,
    onSuccess: (me) => {
      setUser(me);
      qc.invalidateQueries({ queryKey: ["taste"] });
    },
    onError: (e: Error) => toast(e.message),
  });
  const imp = useMutation({
    mutationFn: (f: File) => api.importCsv(f, importKind),
    onSuccess: (r) => {
      setImportResult(
        `Matched ${r.matched} of ${r.rows} titles — ${r.added.liked} loved, ${r.added.watchlist} to watch, ${r.added.watched} watched, ${r.added.rejected} skipped.` +
          (r.unmatched_count ? ` ${r.unmatched_count} weren't in the catalog.` : ""),
      );
      qc.invalidateQueries();
    },
    onError: (e: Error) => setImportResult(e.message),
  });

  if (!user) return null;
  const toggleArr = (arr: string[], v: string) => (arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);
  const cf = user.content_filters;

  return (
    <div className="page narrow">
      <div className="row" style={{ marginBottom: 16, gap: 14 }}>
        <button className="avatar lg" onClick={() => setSheet("avatar")} aria-label="Change avatar" style={{ cursor: "pointer" }}>
          {user.avatar}
        </button>
        <div className="grow">
          <input
            className="input"
            style={{ fontWeight: 700, fontSize: 20, background: "transparent", border: "none", padding: "2px 0" }}
            defaultValue={user.display_name}
            aria-label="Display name"
            onBlur={(e) => e.target.value.trim() && e.target.value !== user.display_name && save.mutate({ display_name: e.target.value.trim() })}
          />
          <div className="small muted">
            {user.is_guest ? "Guest account" : `@${user.username}`} · {user.friend_code}
          </div>
        </div>
      </div>

      {user.is_guest && (
        <div className="panel row" style={{ marginBottom: 16, borderColor: "rgba(255,138,61,.35)" }}>
          <div className="grow">
            <div style={{ fontWeight: 700 }}>You're swiping as a guest</div>
            <div className="small muted">Create an account to keep your lists across devices.</div>
          </div>
          <button className="btn sm primary" onClick={() => setSheet("account")}>
            Save
          </button>
        </div>
      )}

      <div className="segmented" style={{ marginBottom: 18 }}>
        <button className={tab === "dna" ? "active" : ""} onClick={() => setTab("dna")}>
          🧬 Taste DNA
        </button>
        <button className={tab === "settings" ? "active" : ""} onClick={() => setTab("settings")}>
          ⚙️ Settings
        </button>
      </div>

      {tab === "dna" ? (
        <TasteDNA />
      ) : (
        <div className="stack lg">
          {isNative && <ServerSettings />}
          <div>
            <div className="h3">My subscriptions (India)</div>
            <div className="chips wrap">
              {meta.data?.providers.map((p) => (
                <button
                  key={p.name}
                  className={`chip${user.subscription_providers.includes(p.name) ? " active" : ""}`}
                  onClick={() => save.mutate({ subscription_providers: toggleArr(user.subscription_providers, p.name) })}
                >
                  <span style={{ width: 10, height: 10, borderRadius: 3, background: p.color, display: "inline-block" }} /> {p.name}
                </button>
              ))}
            </div>
          </div>

          <div>
            <div className="h3">Preferred languages</div>
            <div className="chips wrap">
              {meta.data?.languages.map((l) => (
                <button
                  key={l.code}
                  className={`chip${user.preferences.languages.includes(l.code) ? " active" : ""}`}
                  onClick={() => save.mutate({ preferences: { languages: toggleArr(user.preferences.languages, l.code) } })}
                >
                  {l.name}
                </button>
              ))}
            </div>
          </div>

          <div>
            <div className="h3">Content filters</div>
            <div className="stack" style={{ gap: 14 }}>
              <div>
                <span className="label">Never show these genres</span>
                <div className="chips wrap">
                  {meta.data?.genres.map((g) => (
                    <button
                      key={g}
                      className={`chip${cf.blocked_genres.includes(g) ? " active" : ""}`}
                      onClick={() => save.mutate({ content_filters: { blocked_genres: toggleArr(cf.blocked_genres, g) } })}
                    >
                      {g}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <span className="label">Hide titles with</span>
                <div className="chips wrap">
                  {meta.data?.content_flags.map((f) => (
                    <button
                      key={f.key}
                      className={`chip${cf.blocked_flags.includes(f.key) ? " active" : ""}`}
                      onClick={() => save.mutate({ content_filters: { blocked_flags: toggleArr(cf.blocked_flags, f.key) } })}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <span className="label">Maximum certification</span>
                <div className="segmented">
                  {[null, "UA", "U"].map((c) => (
                    <button key={String(c)} className={cf.max_certification === c ? "active" : ""} onClick={() => save.mutate({ content_filters: { max_certification: c } })}>
                      {c === null ? "Anything" : c === "UA" ? "Up to UA" : "U only"}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="panel stack" style={{ gap: 14 }}>
            <div className="row between">
              <div>
                <div style={{ fontWeight: 600 }}>Spoiler shield</div>
                <div className="tiny faint">Show only the logline until you've watched it</div>
              </div>
              <Toggle on={user.preferences.spoiler_shield} label="Spoiler shield" onChange={(v) => save.mutate({ preferences: { spoiler_shield: v } })} />
            </div>
            <div className="row between">
              <div>
                <div style={{ fontWeight: 600 }}>Share my activity with friends</div>
                <div className="tiny faint">Only titles you save — never what you reject</div>
              </div>
              <Toggle
                on={user.privacy_settings.share_activity}
                label="Share activity"
                onChange={(v) => save.mutate({ privacy_settings: { share_activity: v } })}
              />
            </div>
          </div>

          <div>
            <div className="h3">Your data</div>
            <div className="stack" style={{ gap: 8 }}>
              <button className="btn block" onClick={() => setSheet("import")}>
                <Icon name="upload" size={18} /> Import from Letterboxd / IMDb
              </button>
              <button className="btn block" onClick={() => downloadExport()}>
                <Icon name="download" size={18} /> Export my data (JSON)
              </button>
              {!user.is_guest ? (
                <button className="btn block" onClick={() => { signOut(); qc.clear(); }}>
                  <Icon name="logout" size={18} /> Sign out
                </button>
              ) : (
                <button className="btn block" onClick={() => setSheet("login")}>
                  <Icon name="user" size={18} /> Log in to another account
                </button>
              )}
              <button
                className="btn ghost danger block"
                onClick={async () => {
                  if (!confirm("Delete your account and all your data? This can't be undone.")) return;
                  await api.deleteAccount();
                  signOut();
                  qc.clear();
                }}
              >
                <Icon name="trash" size={18} /> Delete account
              </button>
            </div>
          </div>

          <div className="tiny faint stack" style={{ gap: 4 }}>
            {meta.data?.disclaimers.map((d) => (
              <div key={d}>{d}</div>
            ))}
            <div>{meta.data?.catalog_size} titles in catalog</div>
          </div>
        </div>
      )}

      <AccountSheet open={sheet === "account"} onClose={() => setSheet(null)} me={user} />
      <LoginSheet open={sheet === "login"} onClose={() => setSheet(null)} />
      <Sheet open={sheet === "avatar"} onClose={() => setSheet(null)} title="Pick an avatar">
        <div className="chips wrap">
          {AVATARS.map((a) => (
            <button
              key={a}
              className={`chip${user.avatar === a ? " active" : ""}`}
              style={{ fontSize: 24, padding: "8px 12px" }}
              onClick={() => {
                save.mutate({ avatar: a });
                setSheet(null);
              }}
            >
              {a}
            </button>
          ))}
        </div>
      </Sheet>
      <Sheet open={sheet === "import"} onClose={() => { setSheet(null); setImportResult(null); }} title="Import your history">
        <div className="stack">
          <p className="small muted" style={{ margin: 0 }}>
            Upload a CSV export from Letterboxd (ratings, watched, diary or watchlist) or IMDb. Ratings of 3.5★+ become loves, 2★ or less become skips.
          </p>
          <div className="segmented">
            {[
              ["auto", "Ratings / watched"],
              ["watchlist", "Watchlist"],
            ].map(([k, l]) => (
              <button key={k} className={importKind === k ? "active" : ""} onClick={() => setImportKind(k)}>
                {l}
              </button>
            ))}
          </div>
          <input ref={fileRef} type="file" accept=".csv,text/csv" hidden onChange={(e) => e.target.files?.[0] && imp.mutate(e.target.files[0])} />
          <button className="btn primary block" onClick={() => fileRef.current?.click()} disabled={imp.isPending}>
            <Icon name="upload" size={18} /> {imp.isPending ? "Importing…" : "Choose CSV file"}
          </button>
          {importResult && <div className="panel small">{importResult}</div>}
        </div>
      </Sheet>
    </div>
  );
}
