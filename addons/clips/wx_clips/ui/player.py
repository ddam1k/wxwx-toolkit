"""Video playback (QtMultimedia) + the player view with its overlays."""
from __future__ import annotations

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoSink
from PySide6.QtWidgets import QWidget

from ..core.i18n import t
from .common import badge, text_w
from .theme import font, theme
from .widgets import animate


class Player(QObject):
    """QMediaPlayer + 'play only these ranges, one after another' + loop."""
    position = Signal(float)
    playing_changed = Signal(bool)
    frame = Signal(QImage)
    finished_ranges = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mp = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.9)
        self.mp.setAudioOutput(self.audio)
        self.sink = QVideoSink(self)
        self.mp.setVideoSink(self.sink)
        self.sink.videoFrameChanged.connect(self._on_frame)
        self.mp.playbackStateChanged.connect(lambda s: self.playing_changed.emit(s == QMediaPlayer.PlaybackState.PlayingState))
        self.mp.mediaStatusChanged.connect(self._status)
        self.ranges: list[tuple[float, float]] | None = None
        self.loop = False
        self.t = 0.0
        self.dur = 0.0
        self.path = ""
        self._timer = QTimer(self)
        self._timer.setInterval(25)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    @property
    def playing(self) -> bool:
        return self.mp.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def load(self, path: str, dur: float, at: float = 0.0) -> None:
        if path != self.path:
            self.path = path
            self.mp.setSource(QUrl.fromLocalFile(path))
        self.dur = dur
        self.ranges = None
        self.mp.pause()
        self.seek(at)

    def _on_frame(self, f):
        if f.isValid():
            img = f.toImage()
            if not img.isNull():
                self.frame.emit(img)

    def _status(self, s):
        if s == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.loop and not self.ranges:
                self.seek(0)
                self.mp.play()
            else:
                self.t = self.dur
                self.position.emit(self.t)

    def seek(self, s: float) -> None:
        self.t = max(0.0, min(self.dur or s, s))
        self.mp.setPosition(int(self.t * 1000))
        self.position.emit(self.t)

    def play(self) -> None:
        if not self.path:
            return
        if self.ranges:
            if not any(a <= self.t < b - 0.03 for a, b in self.ranges):
                nxt = next((a for a, b in self.ranges if a > self.t), self.ranges[0][0])
                self.seek(nxt)
        elif self.dur and self.t >= self.dur - 0.05:
            self.seek(0)
        self.mp.play()

    def pause(self) -> None:
        self.mp.pause()

    def toggle(self) -> None:
        self.pause() if self.playing else self.play()

    def play_ranges(self, ranges: list[tuple[float, float]]) -> None:
        self.ranges = sorted(ranges)
        self.seek(self.ranges[0][0])
        self.mp.play()

    def stop_ranges(self) -> None:
        self.ranges = None

    def _tick(self):
        if not self.playing:
            return
        self.t = self.mp.position() / 1000
        if self.ranges:
            if not any(a - 0.02 <= self.t < b for a, b in self.ranges):
                nxt = next((a for a, b in self.ranges if a > self.t), None)
                if nxt is not None:
                    self.seek(nxt)
                elif self.loop:
                    self.seek(self.ranges[0][0])
                else:
                    self.mp.pause()
                    self.seek(self.ranges[-1][1])
                    self.ranges = None
                    self.finished_ranges.emit()
        self.position.emit(self.t)

    def shutdown(self):
        self._timer.stop()
        self.mp.stop()
        self.mp.setSource(QUrl())


class PlayerView(QWidget):
    clicked = Signal()
    edit_done = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(160)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.img: QImage | None = None
        self.name = ""
        self.res = ""
        self.loop = False
        self.playing_label = ""
        self.edit_text = ""
        self.edit_color = QColor("#b8a8e2")
        self.loading = False
        self._flash = 0.0
        self._flash_play = True
        self._done_rect = QRectF()
        self._alpha = 1.0

    def set_image(self, img: QImage):
        first = self.img is None
        self.img = img
        self.loading = False
        if first:
            self._alpha = 0.0
            animate(self, 0, 1, 320, self._set_alpha)
        self.update()

    def _set_alpha(self, v):
        self._alpha = float(v)
        self.update()

    def clear(self):
        self.img = None
        self.update()

    def flash(self, playing: bool):
        self._flash_play = playing
        animate(self, 1, 0, 520, self._set_flash)

    def _set_flash(self, v):
        self._flash = float(v)
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        if self.edit_text and self._done_rect.contains(e.position()):
            self.edit_done.emit()
            return
        self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        from .common import rounded
        p.setClipPath(rounded(r, 14))
        p.fillRect(r, QColor("#050506"))
        if self.img is not None and not self.img.isNull():
            iw, ih = self.img.width(), self.img.height()
            k = min(r.width() / iw, r.height() / ih)
            w, h = iw * k, ih * k
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            p.setOpacity(self._alpha)
            k2 = 0.985 + 0.015 * self._alpha
            p.drawImage(QRectF(r.center().x() - w * k2 / 2, r.center().y() - h * k2 / 2, w * k2, h * k2), self.img)
            p.setOpacity(1)
        elif self.loading:
            p.setPen(QColor(255, 255, 255, 120))
            p.setFont(font(9.5, QFont.Weight.DemiBold))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, t("loading"))
        # hud
        x = 12.0
        for txt in (self.name, self.res):
            if txt:
                b = badge(p, QRectF(x, 10, 0, 0), txt, QColor(0, 0, 0, 150), QColor("#e9e7f0"), 7.6,
                          QFont.Weight.Bold, mono=True, radius=7)
                x = b.right() + 6
        if self.loop:
            f = font(7.8, QFont.Weight.ExtraBold)
            w = text_w(t("loop"), f) + 12
            badge(p, QRectF(r.right() - w - 12, 10, 0, 0), t("loop"), QColor(184, 168, 226, 220), QColor("#111"), 7.8,
                  QFont.Weight.ExtraBold, radius=7)
        if self.playing_label:
            badge(p, QRectF(12, r.bottom() - 32, 0, 0), self.playing_label, QColor(10, 10, 12, 170), QColor("#fff"), 8,
                  QFont.Weight.ExtraBold, radius=7)
        if self.edit_text:
            f = font(8.4, QFont.Weight.ExtraBold)
            done = t("edit_done")
            df = font(8, QFont.Weight.ExtraBold)
            dw = text_w(done, df) + 18
            w = text_w(self.edit_text, f) + 24 + dw + 8
            br = QRectF(r.center().x() - w / 2, 42, w, 30)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 90))
            p.drawRoundedRect(br.translated(0, 3), 10, 10)
            p.setBrush(self.edit_color)
            p.drawRoundedRect(br, 10, 10)
            p.setPen(QColor("#141416"))
            p.setFont(f)
            p.drawText(QRectF(br.left() + 12, br.top(), br.width() - dw - 20, br.height()), Qt.AlignmentFlag.AlignVCenter,
                       self.edit_text)
            self._done_rect = QRectF(br.right() - dw - 5, br.top() + 4, dw, br.height() - 8)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#141416"))
            p.drawRoundedRect(self._done_rect, 7, 7)
            p.setPen(QColor("#fff"))
            p.setFont(df)
            p.drawText(self._done_rect, Qt.AlignmentFlag.AlignCenter, done)
        if self._flash > 0.01:
            k = self._flash
            rad = 32 * (0.7 + 0.3 * (1 - k))
            c = r.center()
            p.setOpacity(k)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(17, 17, 19, 150))
            p.drawEllipse(c, rad, rad)
            p.setBrush(QColor("#fff"))
            if self._flash_play:
                from PySide6.QtGui import QPolygonF
                p.drawPolygon(QPolygonF([QPointF(c.x() - 8, c.y() - 12), QPointF(c.x() - 8, c.y() + 12), QPointF(c.x() + 13, c.y())]))
            else:
                p.drawRoundedRect(QRectF(c.x() - 10, c.y() - 11, 7, 22), 2, 2)
                p.drawRoundedRect(QRectF(c.x() + 3, c.y() - 11, 7, 22), 2, 2)
