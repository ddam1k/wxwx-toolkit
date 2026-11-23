"""Reading and writing pictures. Qt does JPG / PNG / WebP in-process (fast enough to show real sizes while
the user moves the slider); ffmpeg reads HEIC & co and writes AVIF. QImage works in worker threads."""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QColor, QImage, QImageIOHandler, QImageReader, QImageWriter, QPainter

from . import exif, opts
from .opts import Opts


@dataclass
class Source:
    path: str
    w: int = 0
    h: int = 0
    size: int = 0
    alpha: bool = False
    gps: bool = False
    exif: bytes | None = None
    error: str = ""


def _writable() -> set[str]:
    return {bytes(f).decode().lower() for f in QImageWriter.supportedImageFormats()}


def info(path: str, ffmpeg: str | None = None) -> Source:
    """Size, transparency, camera data — without decoding the whole picture where Qt can avoid it."""
    s = Source(path)
    try:
        s.size = os.path.getsize(path)
    except OSError as e:
        s.error = str(e)
        return s
    if opts.needs_ffmpeg(path):
        img = load(path, ffmpeg)
        if img.isNull():
            s.error = "unreadable"
            return s
        s.w, s.h, s.alpha = img.width(), img.height(), img.hasAlphaChannel()
        return s
    r = QImageReader(path)
    r.setAutoTransform(True)
    sz = r.size()
    if not sz.isValid():
        s.error = r.errorString() or "unreadable"
        return s
    s.w, s.h = (sz.height(), sz.width()) if _transposed(r) else (sz.width(), sz.height())
    fmt = bytes(r.format()).decode().lower()
    s.alpha = fmt in ("png", "webp", "gif", "tif", "tiff") and _has_alpha(path)
    if fmt in ("jpg", "jpeg"):
        try:
            with open(path, "rb") as f:
                head = f.read(256 * 1024)
            s.exif = exif.jpeg_exif(head)
            s.gps = bool(s.exif) and exif.GPS_TAG in exif.tags(s.exif)
        except OSError:
            pass
    return s


def _transposed(r: QImageReader) -> bool:
    """size() is before the EXIF turn; a 90° / 270° turn swaps width and height."""
    try:
        return bool(r.transformation() & QImageIOHandler.Transformation.TransformationRotate90)
    except Exception:
        return False


def _has_alpha(path: str) -> bool:
    img = QImage(path)
    return not img.isNull() and img.hasAlphaChannel() and not _opaque(img)


def _opaque(img: QImage) -> bool:
    """An alpha channel that is fully opaque (common in PNG screenshots) is no transparency."""
    small = img.scaled(64, 64, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
    small = small.convertToFormat(QImage.Format.Format_ARGB32)
    for y in range(small.height()):
        for x in range(small.width()):
            if small.pixelColor(x, y).alpha() < 250:
                return False
    return True


def load(path: str, ffmpeg: str | None = None) -> QImage:
    if opts.needs_ffmpeg(path):
        if not ffmpeg:
            return QImage()
        with tempfile.TemporaryDirectory() as d:
            png = os.path.join(d, "in.png")
            r = opts.run(opts.decode_args(ffmpeg, path, png), timeout=120)
            return QImage(png) if r.returncode == 0 else QImage()
    rd = QImageReader(path)
    rd.setAutoTransform(True)              # phone photos: turn upright by their EXIF orientation
    return rd.read()


def _bytes(img: QImage, fmt: str, quality: int) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    w = QImageWriter(buf, fmt.encode())
    w.setQuality(quality)
    if fmt == "jpg":
        w.setOptimizedWrite(True)
        w.setProgressiveScanWrite(True)
    if not w.write(img):
        raise RuntimeError(w.errorString() or f"could not write {fmt}")
    return bytes(buf.data())


def flatten(img: QImage) -> QImage:
    """Transparency → white (JPG / AVIF have none)."""
    out = QImage(img.size(), QImage.Format.Format_RGB32)
    out.fill(QColor("#ffffff"))
    p = QPainter(out)
    p.drawImage(0, 0, img)
    p.end()
    return out


@dataclass
class Result:
    data: bytes
    w: int
    h: int
    fmt: str


def encode(src: Source, o: Opts, ffmpeg: str | None = None, img: QImage | None = None) -> Result:
    """The file as it will be written, in memory."""
    fmt = opts.out_fmt(src.path, o, src.alpha)
    w, h = opts.dims(src.w, src.h, o.long)
    same = fmt == opts.src_fmt(src.path) and (w, h) == (src.w, src.h) and not opts.needs_ffmpeg(src.path)
    if same and o.q >= 100 and fmt in ("jpg", "webp", "avif"):
        # «Без потерь»: the very same pixels; only camera data goes, if asked
        with open(src.path, "rb") as f:
            data = f.read()
        if fmt == "jpg" and o.strip:
            data = exif.strip_jpeg(data)
        return Result(data, w, h, fmt)
    if img is None:
        img = load(src.path, ffmpeg)
    if img.isNull():
        raise RuntimeError("could not read the picture")
    if (img.width(), img.height()) != (w, h):
        img = img.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    if fmt in ("jpg", "avif") and img.hasAlphaChannel():
        img = flatten(img)
    if fmt == "png":
        data = _bytes(img, "png", 0)          # 0 = strongest zlib compression; PNG is lossless anyway
        if same:
            with open(src.path, "rb") as f:
                orig = f.read()
            data = min(data, orig, key=len)          # a PNG re-packed bigger than it was: keep the original
        return Result(data, w, h, fmt)
    if fmt == "avif":
        if not ffmpeg:
            raise RuntimeError("AVIF needs ffmpeg")
        with tempfile.TemporaryDirectory() as d:
            png, out = os.path.join(d, "in.png"), os.path.join(d, "out.avif")
            img.save(png, "PNG", 100)
            r = opts.run(opts.avif_args(ffmpeg, png, out, o.q), timeout=300)
            if r.returncode != 0 or not os.path.isfile(out):
                raise RuntimeError(opts.ff_error(r))
            with open(out, "rb") as f:
                return Result(f.read(), w, h, fmt)
    if fmt == "webp" and "webp" not in _writable():
        return _webp_ffmpeg(img, o, ffmpeg, w, h)
    data = _bytes(img, fmt, o.q)
    if fmt == "jpg" and not o.strip and src.exif:
        data = exif.put_exif(data, src.exif)
    return Result(data, w, h, fmt)


def _webp_ffmpeg(img: QImage, o: Opts, ffmpeg: str | None, w: int, h: int) -> Result:
    if not ffmpeg:
        raise RuntimeError("WebP needs ffmpeg here")
    with tempfile.TemporaryDirectory() as d:
        png, out = os.path.join(d, "in.png"), os.path.join(d, "out.webp")
        img.save(png, "PNG", 100)
        r = opts.run([ffmpeg, "-y", "-v", "error", "-i", png, "-frames:v", "1", "-c:v", "libwebp",
                      "-quality", str(o.q), out], timeout=120)
        if r.returncode != 0:
            raise RuntimeError(opts.ff_error(r))
        with open(out, "rb") as f:
            return Result(f.read(), w, h, "webp")


def decode(res: Result, ffmpeg: str | None = None) -> QImage:
    """The encoded result as a picture again — for «было / стало»."""
    img = QImage.fromData(QByteArray(res.data))
    if not img.isNull() or res.fmt != "avif" or not ffmpeg:
        return img
    with tempfile.TemporaryDirectory() as d:
        src, png = os.path.join(d, "x.avif"), os.path.join(d, "x.png")
        with open(src, "wb") as f:
            f.write(res.data)
        r = opts.run(opts.decode_args(ffmpeg, src, png), timeout=60)
        return QImage(png) if r.returncode == 0 else QImage()
