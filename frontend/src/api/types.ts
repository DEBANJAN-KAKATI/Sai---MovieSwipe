export type MediaType = "movie" | "tv";
export type SwipeAction =
  | "watchlist"
  | "rejected"
  | "undecided"
  | "must_visit"
  | "liked"
  | "watched"
  | "watch_intent"
  | "impression_detail";
export type ListAction = "watchlist" | "must_visit" | "undecided" | "rejected" | "liked" | "watched" | "remove";

export interface Media {
  media_id: string;
  tmdb_id: number | null;
  title: string;
  type: MediaType;
  year: number | null;
  genres: string[];
  keywords: string[];
  overview: string;
  logline: string;
  tagline: string | null;
  poster_url: string | null;
  backdrop_url: string | null;
  logo_url: string | null;
  image_source: string | null;
  runtime_minutes: number | null;
  season_count: number | null;
  runtime_label: string;
  language: string;
  language_name: string;
  certification: string | null;
  content_flags: string[];
  cast: string[];
  creator: string | null;
  vote_average: number | null;
  providers: string[];
}

export interface FeedCard extends Media {
  match_percent: number | null;
  because: string | null;
  because_media_id?: string | null;
  reasons: string[];
  badges: string[];
  availability: string | null;
  friends_saved: string[];
  friends_saved_count: number;
  explore: boolean;
  resurfaced: boolean;
  group_fit?: number;
}

export interface FeedResponse {
  cards: FeedCard[];
  mode: string;
  mood: string | null;
  cold_start: boolean;
  personalization: number;
  remaining: number;
  exhausted: boolean;
}

export interface PublicUser {
  user_id: string;
  username: string;
  display_name: string;
  avatar: string;
  is_bot: boolean;
}

export interface Me extends PublicUser {
  email: string | null;
  is_guest: boolean;
  region: string;
  friend_code: string;
  onboarded: boolean;
  subscription_providers: string[];
  content_filters: { blocked_genres: string[]; blocked_flags: string[]; max_certification: string | null };
  preferences: { spoiler_shield: boolean; languages: string[]; haptics: boolean; blind_mode: boolean };
  privacy_settings: { share_activity: boolean; public_profile: boolean };
  created_at: string;
}

export interface Provider {
  name: string;
  type: string;
  link: string;
  on_your_plan: boolean;
}

export interface WatchInfo {
  google_url: string;
  providers: Provider[];
  on_your_services: string[];
  disclaimer: string;
}

export interface MediaDetail extends Media {
  qa: {
    about: string;
    format: string;
    cast: string[];
    creator: string | null;
    creator_label: string;
    trailer: { youtube_key: string | null; embed_url: string | null; search_url: string };
    content_notes: { flag: string; label: string }[];
    certification_label: string | null;
    where_to_watch: WatchInfo;
    match: {
      match_percent: number;
      because: string | null;
      because_media_id: string | null;
      reasons: string[];
      availability: string | null;
    } | null;
  };
  your_action: { action: string; rating: number | null } | null;
  friends_saved: string[];
  similar: (Media & { similarity_percent: number; your_action?: string })[];
}

export interface ListItemCard extends Media {
  action: string;
  rating: number | null;
  added_at: string;
  from_session: boolean;
  reasons?: string[];
}

export interface MatchInfo {
  match_id: string;
  media: Media;
  participants: string[];
  super_match: boolean;
  matched_at: string;
}

export interface SessionState {
  session_id: string;
  code: string;
  mode: "duo" | "group";
  min_votes: number | null;
  required_votes: number;
  status: string;
  filters: { mood?: string | null; type?: string; max_runtime?: number | null };
  host_id: string;
  is_host: boolean;
  expires_at: string;
  created_at: string;
  members: (PublicUser & { swiped: number; is_you: boolean })[];
  matches: MatchInfo[];
  join_path: string;
}

export interface SessionSummary {
  session_id: string;
  code: string;
  mode: string;
  status: string;
  created_at: string;
  members: PublicUser[];
  match_count: number;
  latest_match: MatchInfo | null;
}

export interface Friend extends PublicUser {
  friendship_id: string;
  since: string;
  compatibility?: number;
  shared_count?: number;
  shared_genres?: string[];
  tagline?: string | null;
}

export interface Meta {
  providers: { name: string; color: string; domain: string }[];
  moods: { key: string; label: string; emoji: string }[];
  genres: string[];
  languages: { code: string; name: string }[];
  content_flags: { key: string; label: string }[];
  certifications: { key: string; label: string }[];
  catalog_size: number;
  tmdb_enabled: boolean;
  disclaimers: string[];
}

export interface Badge {
  key: string;
  label: string;
  emoji: string;
  description: string;
  progress: number;
  target: number;
  earned: boolean;
}

export interface TasteSummary {
  archetype: { label: string; blurb: string } | null;
  top_genres: { name: string; score: number }[];
  top_keywords: { name: string; score: number }[];
  avoided_genres: string[];
  languages: { code: string; name: string; count: number }[];
  decades: { name: string; count: number }[];
  type_split: { movie: number; tv: number };
  counts: Record<string, number>;
  accept_rate: number | null;
  streak: { current: number; best: number };
  personalization: { signals: number; level: number };
  badges: Badge[];
  seeds: string[];
}

export interface CollabListT {
  list_id: string;
  name: string;
  description: string;
  emoji: string;
  is_public: boolean;
  owner_id: string;
  item_count: number;
  members: (PublicUser & { role: string })[];
  your_role?: string | null;
  invite_code?: string;
  preview_posters: { title: string; poster_url: string | null; genres: string[] }[];
  items?: (Media & { note: string; added_by: string; added_at: string })[];
}

export interface Party {
  party_id: string;
  code: string;
  media: Media | null;
  starts_at: string;
  duration_minutes: number;
  notes: string;
  host: PublicUser | null;
  is_host: boolean;
  rsvps: (PublicUser & { status: string })[];
  your_rsvp: string | null;
  watch_url: string | null;
  calendar_path: string;
  upcoming: boolean;
}

export interface TonightPick {
  source: string;
  pick: (Media & { reasons?: string[]; match_percent?: number | null }) | null;
  alternates: (Media & { reasons?: string[] })[];
  reasons: string[];
}
