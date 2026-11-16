"""Encode settings, codec tables and built-in presets (no Qt here)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields

FPS_STEPS: list[int | None] = [None, 60, 50, 30, 25, 24, 15, 12, 10]
RESOLUTIONS: list[tuple[int | None, str]] = [
    (None, "Исходное"), (1080, "1080p"), (720, "720p"), (480, "480p"), (360, "360p"),
]

FORMATS = [("mp4", "MP4", ""), ("webm", "WebM", ""), ("gif", "GIF", "")]
CODECS: dict[str, list[tuple[str, str, str]]] = {
    "mp4": [("h264", "H.264", "везде"), ("h265", "H.265", "−40%"), ("av1", "AV1", "−55%")],
    "webm": [("vp9", "VP9", "браузеры"), ("av1", "AV1", "−55%")],
    "gif": [("gif", "GIF", "палитра")],
}
ENCODER_KINDS = [("cpu", "Процессор", "меньше файл"), ("gpu", "Видеокарта", "NVENC · быстро")]
MODES = [("quality", "Качество", ""), ("size", "Размер", ""), ("ratio", "В N раз", "")]
AUDIO = [("keep", "Как есть", ""), ("compress", "Сжать", "128k"), ("none", "Без звука", "")]

CPU_ENCODERS = {"h264": "libx264", "h265": "libx265", "av1": "libsvtav1", "vp9": "libvpx-vp9"}
GPU_ENCODERS = {"h264": "h264_nvenc", "h265": "hevc_nvenc", "av1": "av1_nvenc"}
# rough size multiplier vs H.264 at the same visual quality
EFFICIENCY = {"h264": 1.0, "h265": 0.62, "av1": 0.48, "vp9": 0.66}


@dataclass
class EncodeSettings:
    format: str = "mp4"
    codec: str = "h264"
    encoder: str = "cpu"        # cpu | gpu
    mode: str = "quality"       # quality | size | ratio
    quality: int = 62           # 0..100, higher = better picture
    size_mb: int = 10
    ratio: float = 3.0
    res: int | None = 1080      # target short side, None = source
    fps_idx: int = 0            # index into FPS_STEPS
    audio: str = "compress"     # keep | compress | none
    colors: int = 128           # GIF palette size

    @property
    def fps_target(self) -> int | None:
        return FPS_STEPS[max(0, min(self.fps_idx, len(FPS_STEPS) - 1))]

    @property
    def is_gif(self) -> bool:
        return self.format == "gif"

    def copy(self) -> "EncodeSettings":
        return EncodeSettings(**asdict(self))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "EncodeSettings":
        names = {f.name for f in fields(cls)}
        s = cls(**{k: v for k, v in (data or {}).items() if k in names})
        s.normalize()
        return s

    def normalize(self) -> None:
        if self.format not in CODECS:
            self.format = "mp4"
        ids = [c[0] for c in CODECS[self.format]]
        if self.codec not in ids:
            self.codec = ids[0]
        if self.encoder == "gpu" and self.codec not in GPU_ENCODERS:
            self.encoder = "cpu"
        if self.mode not in ("quality", "size", "ratio"):
            self.mode = "quality"
        if self.audio not in ("keep", "compress", "none"):
            self.audio = "compress"
        self.quality = int(max(0, min(100, self.quality)))
        self.size_mb = int(max(1, min(4000, self.size_mb)))
        self.ratio = float(max(1.5, min(10.0, self.ratio)))
        self.colors = int(max(16, min(256, self.colors)))
        self.fps_idx = int(max(0, min(len(FPS_STEPS) - 1, self.fps_idx)))
        if self.res is not None:
            self.res = int(self.res)


@dataclass
class Preset:
    id: str
    title: str
    values: dict

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "values": self.values}

    @classmethod
    def from_dict(cls, d: dict) -> "Preset":
        return cls(d["id"], d["title"], dict(d.get("values", {})))


BUILTIN_PRESETS = [
    Preset("discord", "Discord 10 МБ", dict(format="mp4", codec="h264", mode="size", size_mb=10,
                                             res=720, fps_idx=3, audio="compress")),
    Preset("telegram", "Telegram", dict(format="mp4", codec="h264", mode="quality", quality=62,
                                        res=1080, fps_idx=0, audio="compress")),
    Preset("web", "Для веба", dict(format="webm", codec="vp9", mode="quality", quality=55,
                                   res=1080, fps_idx=3, audio="compress")),
    Preset("archive", "Архив", dict(format="mp4", codec="h265", mode="quality", quality=88,
                                    res=None, fps_idx=0, audio="keep")),
    Preset("gif", "GIF-превью", dict(format="gif", codec="gif", res=480, fps_idx=6, colors=128)),
]


def apply_preset(current: EncodeSettings, preset: Preset) -> EncodeSettings:
    data = current.to_dict()
    data.update(preset.values)
    return EncodeSettings.from_dict(data)
