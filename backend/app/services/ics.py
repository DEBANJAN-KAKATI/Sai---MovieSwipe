"""Minimal RFC 5545 calendar export for watch parties."""

from __future__ import annotations

import datetime as dt


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts, chunk = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(chunk) + len(b) > (75 if not parts else 74):
            parts.append(chunk.decode("utf-8"))
            chunk = b""
        chunk += b
    parts.append(chunk.decode("utf-8"))
    return "\r\n ".join(parts)


def _stamp(d: dt.datetime) -> str:
    return d.strftime("%Y%m%dT%H%M%SZ")


def party_ics(
    *,
    uid: str,
    title: str,
    starts_at: dt.datetime,
    duration_minutes: int,
    description: str,
    url: str | None = None,
) -> str:
    """starts_at must be naive UTC."""
    end = starts_at + dt.timedelta(minutes=duration_minutes)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//sai//Watch Party//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}@movieswipe",
        f"DTSTAMP:{_stamp(dt.datetime.now(dt.UTC).replace(tzinfo=None))}",
        f"DTSTART:{_stamp(starts_at)}",
        f"DTEND:{_stamp(end)}",
        f"SUMMARY:{_esc(title)}",
        f"DESCRIPTION:{_esc(description)}",
    ]
    if url:
        lines.append(f"URL:{url}")
    lines += [
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{_esc(title)} starts in 1 hour",
        "TRIGGER:-PT1H",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
