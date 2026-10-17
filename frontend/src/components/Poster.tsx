import { useState } from "react";
import { imgSrc } from "../api/base";
import type { Media } from "../api/types";

const GLYPHS: Record<string, string> = {
  Crime: "🔍",
  Mystery: "🕵️",
  Comedy: "😂",
  "Sci-Fi": "🪐",
  Drama: "🎭",
  Thriller: "⚡",
  Horror: "👻",
  Romance: "💘",
  Action: "💥",
  Animation: "✨",
  Documentary: "🌍",
  Fantasy: "🐉",
  History: "🏛️",
  Family: "🏡",
  Sports: "🏆",
  Music: "🎵",
  Adventure: "🧭",
  War: "🎖️",
};

function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export function posterTheme(title: string) {
  const h = hash(title);
  const hue1 = h % 360;
  const hue2 = (hue1 + 40 + ((h >> 9) % 100)) % 360;
  const angle = (h >> 3) % 360;
  return {
    background: `linear-gradient(${angle}deg, hsl(${hue1} 62% 26%) 0%, hsl(${hue2} 70% 42%) 100%)`,
    orb: `radial-gradient(circle, hsla(${(hue2 + 30) % 360} 90% 70% / 0.55), transparent 65%)`,
    orbPos: { left: `${(h >> 5) % 60}%`, top: `${(h >> 11) % 50}%` },
  };
}

type PosterMedia = Pick<Media, "title" | "genres" | "year" | "type"> &
  Partial<Pick<Media, "poster_url" | "backdrop_url" | "logo_url">>;

type Props = {
  media: PosterMedia;
  showTitle?: boolean;
  fontSize?: number;
  /**
   * Show the image framed over a blurred copy of itself instead of stretching it to fill:
   * "card" does this only for small source images (e.g. ~250px Wikipedia film posters), "hero" always
   * (a portrait poster in a wide header).
   */
  ambient?: "card" | "hero";
  /** Load immediately (above-the-fold images); default is lazy for long lists. */
  eager?: boolean;
};

const LOW_RES_WIDTH = 400;

/**
 * Best available artwork: a portrait poster, else a wide title card (cropped to fill), else the show's logo on a
 * plate over generated art, else fully generated art. Falls through to the next option if an image fails to load.
 */
export function Poster({ media, showTitle = true, fontSize = 14, ambient, eager = false }: Props) {
  const [failed, setFailed] = useState<Set<string>>(new Set());
  const [lowRes, setLowRes] = useState<Set<string>>(new Set());
  const fail = (url: string) => setFailed((f) => new Set(f).add(url));
  const cover = [media.poster_url, media.backdrop_url].find((u): u is string => !!u && !failed.has(u));
  const framed =
    cover && ambient && cover === media.poster_url && (ambient === "hero" || lowRes.has(cover));
  if (cover && framed) {
    return (
      <div className={`ambient-poster ${ambient}`}>
        <img className="ambient-bg" src={imgSrc(cover)} alt="" aria-hidden draggable={false} />
        <img
          className="ambient-fg"
          src={imgSrc(cover)}
          alt={`${media.title} poster`}
          draggable={false}
          onError={() => fail(cover)}
        />
      </div>
    );
  }
  if (cover) {
    return (
      <img
        src={imgSrc(cover)}
        alt={`${media.title} poster`}
        loading={ambient || eager ? "eager" : "lazy"}
        draggable={false}
        onError={() => fail(cover)}
        onLoad={(e) => {
          if (ambient && e.currentTarget.naturalWidth < LOW_RES_WIDTH) setLowRes((s) => new Set(s).add(cover));
        }}
        style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "center 30%" }}
      />
    );
  }
  const logo = media.logo_url && !failed.has(media.logo_url) ? media.logo_url : null;
  const theme = posterTheme(media.title);
  const glyph = GLYPHS[media.genres[0] ?? ""] ?? "🎬";
  return (
    <div className="gen-poster" style={{ background: theme.background, fontSize }} role="img" aria-label={media.title}>
      <div className="gp-orb" style={{ ...theme.orbPos, width: "90%", height: "70%", background: theme.orb }} />
      <div className="gp-noise" />
      {logo ? (
        <div className="logo-plate">
          <img src={imgSrc(logo)} alt={`${media.title} logo`} loading="lazy" draggable={false} onError={() => fail(logo)} />
        </div>
      ) : (
        <>
          {showTitle && <div className="gp-type">{media.type === "tv" ? "Series" : "Film"}</div>}
          <div style={showTitle ? { position: "relative" } : { position: "relative", margin: "auto", paddingBottom: "40%" }}>
            <div className="gp-glyph">{glyph}</div>
            {showTitle && (
              <>
                <div className="gp-title">{media.title}</div>
                {media.year && <div className="gp-year">{media.year}</div>}
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}
