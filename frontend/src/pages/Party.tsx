import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { getApiBase, shareOrigin } from "../api/base";
import { copyText } from "../lib/clipboard";
import { api } from "../api/client";
import { Icon } from "../components/Icon";
import { Poster } from "../components/Poster";
import { toast } from "../store";

function countdown(iso: string) {
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return "Started";
  const h = Math.floor(ms / 3_600_000);
  const d = Math.floor(h / 24);
  if (d >= 1) return `in ${d} day${d > 1 ? "s" : ""}`;
  const m = Math.floor((ms % 3_600_000) / 60_000);
  return h ? `in ${h}h ${m}m` : `in ${m} min`;
}

export function PartyPage() {
  const { code } = useParams();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const q = useQuery({ queryKey: ["party", code], queryFn: () => api.party(code!), refetchInterval: 30_000 });
  const rsvp = useMutation({
    mutationFn: (s: "going" | "maybe" | "no") => api.rsvp(code!, s),
    onSuccess: (p) => {
      qc.setQueryData(["party", code], p);
      qc.invalidateQueries({ queryKey: ["parties"] });
    },
  });
  const p = q.data;
  if (q.isError) return <div className="page empty">Watch party not found.</div>;
  if (!p) return <div className="page narrow"><div className="skeleton" style={{ height: 300, borderRadius: 20 }} /></div>;
  const when = new Date(p.starts_at);
  const url = `${shareOrigin()}/party/${p.code}`;

  return (
    <div className="page narrow">
      <div className="page-header">
        <button className="icon-btn" onClick={() => navigate(-1)} aria-label="Back">
          <Icon name="back" size={20} />
        </button>
        <span className="tag gold">{countdown(p.starts_at)}</span>
      </div>
      <div className="stack lg">
        <div className="row" style={{ alignItems: "flex-start", gap: 16 }}>
          <div className="thumb" style={{ width: 110, height: 164, borderRadius: 16 }}>
            {p.media && <Poster media={p.media} fontSize={9} />}
          </div>
          <div className="grow">
            <div className="small muted">🎉 Watch party</div>
            <h1 className="h1" style={{ fontSize: 26 }}>
              {p.media?.title}
            </h1>
            <div className="small muted" style={{ marginTop: 6 }}>
              {when.toLocaleDateString([], { weekday: "long", day: "numeric", month: "long" })}
              <br />
              {when.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} · {p.duration_minutes} min
            </div>
            <div className="small" style={{ marginTop: 6 }}>
              Hosted by {p.host?.avatar} {p.host?.display_name}
            </div>
          </div>
        </div>
        {p.notes && <div className="panel">{p.notes}</div>}

        <div>
          <div className="h3">Are you in?</div>
          <div className="segmented">
            {(["going", "maybe", "no"] as const).map((s) => (
              <button key={s} className={p.your_rsvp === s ? "active" : ""} onClick={() => rsvp.mutate(s)}>
                {s === "going" ? "🙌 Going" : s === "maybe" ? "🤔 Maybe" : "😢 Can't"}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="h3">Who's coming</div>
          <div className="chips wrap">
            {p.rsvps.map((r) => (
              <span key={r.user_id} className="chip static">
                {r.avatar} {r.display_name} · {r.status}
              </span>
            ))}
          </div>
        </div>

        <div className="stack" style={{ gap: 8 }}>
          <a className="btn primary block" href={`${getApiBase()}${p.calendar_path}`} download target="_blank" rel="noreferrer">
            <Icon name="calendar" size={18} /> Add to calendar (.ics, 1-hour reminder)
          </a>
          {p.watch_url && (
            <a className="btn block" href={p.watch_url} target="_blank" rel="noreferrer noopener">
              <Icon name="play" size={18} /> Where to watch in India
            </a>
          )}
          <button
            className="btn block"
            onClick={async () => {
              const text = `Watch party: ${p.media?.title} on ${when.toLocaleString()} — RSVP: ${url}`;
              if (navigator.share) await navigator.share({ title: "Watch party", text, url }).catch(() => undefined);
              else {
                await copyText(text);
                toast("Invite copied");
              }
            }}
          >
            <Icon name="share" size={18} /> Share invite
          </button>
          {p.is_host && (
            <button
              className="btn ghost danger block"
              onClick={() =>
                confirm("Cancel this watch party?") &&
                api.cancelParty(p.code).then(() => {
                  qc.invalidateQueries({ queryKey: ["parties"] });
                  navigate("/social");
                })
              }
            >
              Cancel party
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
