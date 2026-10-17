import { useAuth } from "../store";
import { getApiBase } from "./base";
import type {
  CollabListT,
  FeedResponse,
  Friend,
  ListAction,
  ListItemCard,
  MatchInfo,
  Me,
  Media,
  MediaDetail,
  Meta,
  Party,
  PublicUser,
  SessionState,
  SessionSummary,
  SwipeAction,
  TasteSummary,
  TonightPick,
  WatchInfo,
  FeedCard,
} from "./types";

/**
 * Random id for idempotency keys. crypto.randomUUID only exists on secure origins (https / localhost), and the
 * live preview on a phone is plain http://<PC-IP>, so fall back to getRandomValues, which works everywhere.
 */
function newId(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = useAuth.getState().token;
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const res = await fetch(`${getApiBase()}/api${path}`, { ...init, headers });
  if (res.status === 401 && token) {
    useAuth.getState().signOut();
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* not json */
    }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

const get = <T,>(p: string) => request<T>(p);
const post = <T,>(p: string, body?: unknown) =>
  request<T>(p, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
const patch = <T,>(p: string, body: unknown) => request<T>(p, { method: "PATCH", body: JSON.stringify(body) });
const del = <T,>(p: string) => request<T>(p, { method: "DELETE" });

const qs = (params: Record<string, string | number | undefined | null>) => {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") s.set(k, String(v));
  const str = s.toString();
  return str ? `?${str}` : "";
};

export type AuthResult = { token: string; user: Me };

export const api = {
  // auth
  guest: (display_name?: string) => post<AuthResult>("/auth/guest", { display_name }),
  register: (body: { username: string; password: string; email?: string; display_name?: string }) =>
    post<AuthResult>("/auth/register", body),
  login: (login: string, password: string) => post<AuthResult>("/auth/login", { login, password }),

  // meta & profile
  meta: () => get<Meta>("/meta"),
  me: () => get<Me>("/users/me"),
  updateMe: (body: Partial<Pick<Me, "display_name" | "avatar" | "subscription_providers">> & {
    content_filters?: Partial<Me["content_filters"]>;
    preferences?: Partial<Me["preferences"]>;
    privacy_settings?: Partial<Me["privacy_settings"]>;
  }) => patch<Me>("/users/me", body),
  tasteSummary: () => get<TasteSummary>("/users/me/taste-summary"),
  deleteAccount: () => del<{ ok: boolean }>("/users/me"),
  importCsv: (file: File, list_kind: string) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("list_kind", list_kind);
    return request<{
      source: string;
      rows: number;
      matched: number;
      unmatched: string[];
      unmatched_count: number;
      added: Record<string, number>;
    }>("/import/letterboxd", { method: "POST", body: fd });
  },

  // onboarding & feed
  tiles: () => get<{ tiles: Media[] }>("/onboarding/tiles"),
  onboard: (body: {
    liked_ids: string[];
    display_name?: string;
    subscriptions?: string[];
    languages?: string[];
    content_filters?: Record<string, unknown>;
  }) => post<{ ok: boolean }>("/onboarding/taste", body),
  feed: (p: { limit?: number; mode?: string; mood?: string | null; type?: string; language?: string; max_runtime?: number | null; exclude?: string[] }) =>
    get<FeedResponse>(
      `/feed${qs({ ...p, exclude: p.exclude?.join(",") })}`,
    ),
  swipe: (media_id: string, action: SwipeAction, session_id?: string | null) =>
    post<{ ok: boolean; duplicate: boolean; action: string; match: MatchInfo | null }>("/swipe", {
      media_id,
      action,
      session_id: session_id ?? null,
      idempotency_key: newId(),
    }),
  undo: () =>
    post<{ undone_action: string; restored_action: string | null; card: Media | null; session_id: string | null }>(
      "/swipe/undo",
    ),
  tonight: (p: { minutes?: number | null; mood?: string | null; session_id?: string | null }) =>
    get<TonightPick>(`/picks/tonight${qs(p)}`),

  // media
  media: (id: string, log = true) => get<MediaDetail>(`/media/${id}${log ? "" : "?log=false"}`),
  search: (q: string, limit = 12) =>
    get<{ results: Media[]; imported_from_tmdb: number }>(`/media/search${qs({ q, limit })}`),
  watchInIndia: (id: string) => get<WatchInfo & { title: string }>(`/media/${id}/watch-in-india`),

  // lists
  watchlist: (sort: string) =>
    get<{ must_visit: ListItemCard[]; watchlist: ListItemCard[]; movie_minutes_total: number }>(
      `/lists/watchlist${qs({ sort })}`,
    ),
  undecided: () => get<{ items: ListItemCard[] }>("/lists/undecided"),
  history: (kind: string) => get<{ items: ListItemCard[] }>(`/lists/history${qs({ kind })}`),
  counts: () => get<Record<string, number>>("/lists/counts"),
  setListAction: (media_id: string, action: ListAction, rating?: number) =>
    patch<{ ok: boolean }>(`/lists/items/${media_id}`, { action, rating }),

  // sessions
  createSession: (body: { mode: "duo" | "group"; min_votes?: number | null; mood?: string | null; type?: string; max_runtime?: number | null }) =>
    post<SessionState>("/sessions", body),
  joinSession: (code: string) => post<SessionState>("/sessions/join", { code }),
  sessions: () => get<{ sessions: SessionSummary[] }>("/sessions"),
  session: (id: string) => get<SessionState>(`/sessions/${id}`),
  sessionFeed: (id: string, limit = 10) => get<{ cards: FeedCard[] }>(`/sessions/${id}/feed${qs({ limit })}`),
  addBot: (id: string) => post<SessionState>(`/sessions/${id}/bot`),
  closeSession: (id: string) => post<SessionState>(`/sessions/${id}/close`),

  // social
  friends: () => get<{ friends: Friend[]; incoming: Friend[]; outgoing: Friend[]; your_code: string }>("/friends"),
  requestFriend: (friend_code: string) =>
    post<{ status: string; friend: PublicUser }>("/friends/request", { friend_code }),
  acceptFriend: (id: string) => post(`/friends/${id}/accept`),
  declineFriend: (id: string) => post(`/friends/${id}/decline`),
  demoFriends: () => post<{ added: PublicUser[] }>("/friends/demo"),
  compare: (id: string) =>
    get<{
      friend: PublicUser & { tagline?: string | null };
      compatibility: number;
      shared_genres: string[];
      shared: Media[];
      their_top_genres: string[];
      you_havent_seen: Media[];
    }>(`/friends/${id}/compare`),
  recommend: (to_user_id: string, media_id: string, message: string) =>
    post("/recommendations/send", { to_user_id, media_id, message }),
  inbox: () =>
    get<{
      items: {
        recommendation_id: string;
        from: PublicUser;
        media: Media;
        message: string;
        response: string | null;
        created_at: string;
        seen: boolean;
      }[];
      unseen: number;
    }>("/recommendations/inbox"),
  respondRec: (id: string, action: "watchlist" | "must_visit" | "dismiss") =>
    post(`/recommendations/${id}/respond`, { action }),
  markRecsSeen: () => post("/recommendations/mark-seen"),
  demoIncoming: () => post<{ sent: number }>("/recommendations/demo-incoming"),
  activity: () => get<{ items: { media: Media; count: number; names: string[]; text: string }[] }>("/social/activity"),

  // collaborative lists
  collabLists: () => get<{ lists: CollabListT[] }>("/collab-lists"),
  createCollabList: (body: { name: string; description?: string; emoji?: string; is_public?: boolean }) =>
    post<CollabListT>("/collab-lists", body),
  joinCollabList: (code: string) => post<CollabListT>("/collab-lists/join", { code }),
  collabList: (id: string) => get<CollabListT>(`/collab-lists/${id}`),
  updateCollabList: (id: string, body: Partial<Pick<CollabListT, "name" | "description" | "emoji" | "is_public">>) =>
    patch<CollabListT>(`/collab-lists/${id}`, body),
  deleteCollabList: (id: string) => del(`/collab-lists/${id}`),
  addToCollabList: (id: string, media_id: string, note = "") =>
    post<CollabListT>(`/collab-lists/${id}/items`, { media_id, note }),
  removeFromCollabList: (id: string, media_id: string) => del<CollabListT>(`/collab-lists/${id}/items/${media_id}`),
  publicList: (id: string) => get<CollabListT>(`/public/lists/${id}`),

  // watch parties
  createParty: (body: { media_id: string; starts_at: string; notes?: string; session_id?: string | null }) =>
    post<Party>("/parties", body),
  parties: () => get<{ parties: Party[] }>("/parties"),
  party: (code: string) => get<Party>(`/parties/${code}`),
  rsvp: (code: string, status: "going" | "maybe" | "no") => post<Party>(`/parties/${code}/rsvp`, { status }),
  cancelParty: (code: string) => del(`/parties/${code}`),
};

export function sessionSocketUrl(sessionId: string): string {
  const token = useAuth.getState().token ?? "";
  const origin = getApiBase() || location.origin;
  const wsOrigin = origin.replace(/^http/i, "ws");
  return `${wsOrigin}/api/ws/sessions/${sessionId}?token=${encodeURIComponent(token)}`;
}

export async function downloadExport(): Promise<void> {
  const token = useAuth.getState().token;
  const res = await fetch(`${getApiBase()}/api/users/me/export`, { headers: { Authorization: `Bearer ${token}` } });
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "sai-export.json";
  a.click();
  URL.revokeObjectURL(url);
}
