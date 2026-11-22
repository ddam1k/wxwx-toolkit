"""Proxy for places where YouTube / Instagram are blocked: a local port of a VPN client (v2rayN, Hiddify…).

The user types «1234», «127.0.0.1:1234» or a full «socks5h://…» / «http://…» address.
Without a scheme we try SOCKS5 first, then HTTP, and keep the one that works.
SOCKS5 always becomes socks5h: site names are resolved by the proxy — blocking is often done in DNS."""
from __future__ import annotations

import os
import re
import shutil
import subprocess

TEST_URL = "https://www.youtube.com/generate_204"
SCHEMES = ("socks5h", "socks5", "socks4a", "socks4", "socks", "http", "https")
_FIX = {"socks5": "socks5h", "socks": "socks5h", "socks4": "socks4a"}
_ADDR = re.compile(r"^(?:(?P<auth>[^@/]+)@)?(?P<host>\[[0-9a-fA-F:]+\]|[A-Za-z0-9.\-]+):(?P<port>\d{1,5})/?$")


def split(text: str) -> tuple[str, str] | None:
    """(scheme or "", "[auth@]host:port") or None when it isn't an address."""
    s = (text or "").strip()
    if not s:
        return None
    scheme = ""
    if "://" in s:
        scheme, s = s.split("://", 1)
        scheme = scheme.lower()
        if scheme not in SCHEMES:
            return None
    if s.isdigit():
        s = "127.0.0.1:" + s
    m = _ADDR.match(s)
    if not m or not 0 < int(m["port"]) < 65536:
        return None
    return _FIX.get(scheme, scheme), s.rstrip("/")


def valid(text: str) -> bool:
    return not (text or "").strip() or split(text) is not None


def candidates(text: str) -> list[str]:
    """Full addresses to try, best guess first; [] for an empty field or a bad address."""
    p = split(text)
    if p is None:
        return []
    scheme, addr = p
    return [f"{scheme}://{addr}"] if scheme else [f"socks5h://{addr}", f"http://{addr}"]


def normalize(text: str) -> str:
    """What yt-dlp gets: «» (no proxy) or a full address."""
    c = candidates(text)
    return c[0] if c else ""


def curl() -> str | None:
    """curl.exe ships with Windows 10+; it speaks SOCKS5 and HTTP proxies."""
    sysdir = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "curl.exe")
    return shutil.which("curl") or (sysdir if os.path.isfile(sysdir) else None)


def _flags() -> int:
    return 0x08000000 if os.name == "nt" else 0        # no console window


def probe(url: str, exe: str, target: str = TEST_URL, timeout: int = 12) -> str:
    """ok | port (nobody listens) | proto (listens, but not this kind of proxy) | site (proxy ok, site not)."""
    try:
        r = subprocess.run([exe, "-s", "-o", os.devnull, "-w", "%{http_code}", "--connect-timeout", "5", "--max-time", str(timeout),
                            "--noproxy", "", "-x", url, target], capture_output=True, timeout=timeout + 5,
                           stdin=subprocess.DEVNULL, creationflags=_flags())
    except (OSError, subprocess.SubprocessError):
        return "site"
    code = r.stdout.decode("ascii", "replace").strip()
    if r.returncode == 0 and code[:1] in "23":
        return "ok"
    if r.returncode == 7:
        return "port"
    if r.returncode in (5, 52, 56, 35, 97, 8):          # wrong protocol: SOCKS talking to HTTP or the other way round
        return "proto"
    return "site"


def check(text: str, exe: str | None = None, target: str = TEST_URL) -> tuple[str, str]:
    """(result, address that worked or the first tried). result: ok/port/proto/site/bad/nocurl/off."""
    if not (text or "").strip():
        return "off", ""
    tries = candidates(text)
    if not tries:
        return "bad", ""
    exe = exe or curl()
    if not exe:
        return "nocurl", tries[0]
    seen = []
    for u in tries:
        res = probe(u, exe, target)
        if res == "ok":
            return "ok", u
        if res == "port":                    # same port for every scheme — no point trying the next one
            return "port", u
        seen.append(res)
    # «site» = some scheme got through to the proxy, only the site didn't answer; otherwise it's the wrong kind of port
    return ("site" if "site" in seen else "proto"), tries[0]


def fetch(url: str, dest: str, proxy: str, exe: str | None = None, timeout: int = 15) -> bool:
    """Download a small file (a thumbnail) through the proxy with curl."""
    exe = exe or curl()
    if not exe:
        return False
    try:
        r = subprocess.run([exe, "-sfL", "--max-time", str(timeout), "--max-filesize", "6000000", "--noproxy", "", "-x", proxy,
                            "-A", "Mozilla/5.0", "-o", dest, url], capture_output=True, timeout=timeout + 5,
                           stdin=subprocess.DEVNULL, creationflags=_flags())
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and os.path.isfile(dest) and os.path.getsize(dest) > 0
