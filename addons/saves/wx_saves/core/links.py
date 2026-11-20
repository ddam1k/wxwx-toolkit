"""What did the user paste? Links, their site, single video or playlist (no Qt here)."""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

_URL = re.compile(r"https?://[^\s<>\"']+", re.I)

SITES = (
    ("YouTube", ("youtube.com", "youtu.be", "youtube-nocookie.com")),
    ("Instagram", ("instagram.com", "instagr.am")),
    ("TikTok", ("tiktok.com",)),
)


def split(text: str) -> list[str]:
    """Every http(s) link in the pasted text, in order, without duplicates and trailing punctuation."""
    out: list[str] = []
    for m in _URL.finditer(text or ""):
        u = m.group(0).rstrip(".,;)]}»")
        if u not in out:
            out.append(u)
    return out


def host(url: str) -> str:
    try:
        h = (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""
    return h[4:] if h.startswith("www.") else h


def site(url: str) -> str:
    """"YouTube" | "Instagram" | "TikTok" | "site" (any other web page)."""
    h = host(url)
    for name, domains in SITES:
        if any(h == d or h.endswith("." + d) for d in domains):
            return name
    return "site"


def is_playlist(url: str) -> bool:
    """A YouTube playlist page. A video opened from a playlist (watch?v=…&list=…) is a single video."""
    if site(url) != "YouTube":
        return False
    u = urlparse(url)
    q = parse_qs(u.query)
    if u.path.rstrip("/") == "/playlist" and "list" in q:
        return True
    return "list" in q and "v" not in q and not u.path.startswith(("/watch", "/shorts"))


def video_id(url: str) -> str | None:
    """YouTube id from any of its URL shapes (for «уже качала» before the probe finishes)."""
    if site(url) != "YouTube":
        return None
    u = urlparse(url)
    if host(url) == "youtu.be":
        return u.path.strip("/").split("/")[0] or None
    q = parse_qs(u.query)
    if "v" in q:
        return q["v"][0]
    m = re.match(r"^/(shorts|live|embed)/([\w-]{6,})", u.path)
    return m.group(2) if m else None
