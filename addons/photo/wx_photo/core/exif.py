"""The bits of EXIF this add-on needs, in pure Python: is there a place (GPS) in the photo, and how to carry
the camera data over into a new JPEG when the user keeps it. Pixels are already turned upright by then,
so Orientation is reset to 1 — otherwise viewers would turn the photo a second time."""
from __future__ import annotations

import struct

GPS_TAG = 0x8825
ORIENTATION = 0x0112


def jpeg_exif(data: bytes) -> bytes | None:
    """The APP1 «Exif» payload (TIFF header onwards, without «Exif\\0\\0») of a JPEG, or None."""
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 4 <= len(data) and data[i] == 0xFF:
        marker = data[i + 1]
        if marker in (0xD9, 0xDA):        # end / start of scan — no more headers
            return None
        size = struct.unpack(">H", data[i + 2:i + 4])[0]
        seg = data[i + 4:i + 2 + size]
        if marker == 0xE1 and seg[:6] == b"Exif\x00\x00":
            return seg[6:]
        i += 2 + size
    return None


def _ifd0(tiff: bytes):
    if len(tiff) < 8 or tiff[:2] not in (b"II", b"MM"):
        return None
    e = "<" if tiff[:2] == b"II" else ">"
    off = struct.unpack(e + "I", tiff[4:8])[0]
    if off + 2 > len(tiff):
        return None
    n = struct.unpack(e + "H", tiff[off:off + 2])[0]
    return e, off + 2, n


def tags(tiff: bytes) -> dict[int, tuple[int, int]]:
    """IFD0 tag → (position of its 12-byte entry, the first value as a number)."""
    out: dict[int, tuple[int, int]] = {}
    head = _ifd0(tiff)
    if not head:
        return out
    e, pos, n = head
    for k in range(n):
        p = pos + 12 * k
        if p + 12 > len(tiff):
            break
        tag, typ, _cnt = struct.unpack(e + "HHI", tiff[p:p + 8])
        if typ == 3:                       # SHORT
            val = struct.unpack(e + "H", tiff[p + 8:p + 10])[0]
        else:
            val = struct.unpack(e + "I", tiff[p + 8:p + 12])[0]
        out[tag] = (p, val)
    return out


def has_gps(data: bytes) -> bool:
    t = jpeg_exif(data)
    return bool(t) and GPS_TAG in tags(t)


def upright(tiff: bytes) -> bytes:
    """Same EXIF with Orientation = 1."""
    t = tags(tiff)
    if ORIENTATION not in t:
        return tiff
    e = "<" if tiff[:2] == b"II" else ">"
    p = t[ORIENTATION][0]
    b = bytearray(tiff)
    b[p + 8:p + 10] = struct.pack(e + "H", 1)
    return bytes(b)


def put_exif(jpeg: bytes, tiff: bytes) -> bytes:
    """Insert an APP1 Exif segment right after SOI (dropping one the encoder may have written)."""
    if jpeg[:2] != b"\xff\xd8" or not tiff or len(tiff) > 65000:
        return jpeg
    body = jpeg[2:]
    head = b""
    if body[:2] == b"\xff\xe0":                # JFIF stays first
        n = 2 + struct.unpack(">H", body[2:4])[0]
        head, body = body[:n], body[n:]
    if body[:2] == b"\xff\xe1" and body[4:10] == b"Exif\x00\x00":
        body = body[2 + struct.unpack(">H", body[2:4])[0]:]
    payload = b"Exif\x00\x00" + upright(tiff)
    return b"\xff\xd8" + head + b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload + body


def strip_jpeg(data: bytes) -> bytes:
    """The same JPEG without camera / place data (APP1 Exif & XMP, APP13 IPTC, comments) — no re-encoding.
    Colour profiles (APP2) stay."""
    if data[:2] != b"\xff\xd8":
        return data
    out = bytearray(b"\xff\xd8")
    i = 2
    while i + 4 <= len(data) and data[i] == 0xFF:
        marker = data[i + 1]
        if marker == 0xDA:                   # start of scan: the rest is image data
            break
        size = struct.unpack(">H", data[i + 2:i + 4])[0]
        if marker not in (0xE1, 0xED, 0xFE):
            out += data[i:i + 2 + size]
        i += 2 + size
    out += data[i:]
    return bytes(out)
